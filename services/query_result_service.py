from __future__ import annotations

from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import settings
from core.guardrails import validate_sql_query
from services.db import execute_read_query, fetch_table_schema


class PresentationDecision(BaseModel):
    format: Literal["table", "line_chart", "bar_chart", "metric", "text", "summary"]
    title: str
    x_field: str | None = None
    y_field: str | None = None
    summary_text: str = ""
    bullets: list[str] = Field(default_factory=list)
    reason: str = ""


def determine_presentation(rows: list[dict[str, Any]], question: str) -> PresentationDecision:
    llm = ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds, max_retries=1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You decide how to display customer-support query results.
Use table for detailed records or 2 or more columns of unordered records.
Use line_chart for time-series/trend data.
Use bar_chart for category counts or comparisons.
Use metric for exactly one numeric aggregate with no category/time dimension.
Use text when data is not suitable for table or chart.
Use summary for narrative answers, recommendations, status explanations, or results that should be communicated as a paragraph with bullet highlights.
For summary format, populate summary_text with a concise paragraph and bullets with 2-5 key facts.
Set x_field and y_field to actual keys present in the sample rows.
Return only structured output.
"""),
        ("human", "Question: {question}\nRow count: {row_count}\nColumns: {columns}\nSample rows: {sample}"),
    ])
    structured = llm.with_structured_output(PresentationDecision, method="function_calling", strict=False)
    columns = sorted({key for row in rows for key in row.keys()}) if rows else []
    sample = rows[:5]
    return (prompt | structured).invoke({
        "question": question,
        "row_count": len(rows),
        "columns": ", ".join(columns),
        "sample": sample,
    })


def generate_and_execute_query(question: str, semantic_metric: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = fetch_table_schema()
    metric_context = semantic_metric or {}
    llm = ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds, max_retries=1)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are a PostgreSQL SQL generation expert for ECommerceOps-Agent.
Generate exactly one read-only PostgreSQL SELECT statement.
Use only allowed tables and the supplied schema.
Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, MERGE, COPY, or mutations.
Use table aliases and valid PostgreSQL syntax.
If a semantic metric definition is supplied, generate SQL based on that definition rather than inventing a metric.
Return only the SQL statement, without markdown or prose.
"""),
        ("human", "Question: {question}\nSchema: {schema}\nSemantic metric definition: {metric_context}"),
    ])

    sql = str((prompt | llm).invoke({
        "question": question,
        "schema": schema,
        "metric_context": metric_context,
    }).content).strip()
    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    guard = validate_sql_query(sql)
    if not guard.allowed:
        return {"status": "blocked", "answer": guard.reason, "sql": sql, "rows": [], "presentation": None}

    rows = execute_read_query(guard.sanitized_sql)
    if not isinstance(rows, list):
        rows = []

    presentation = determine_presentation(rows, question)
    return {
        "status": "ok",
        "answer": "Query completed successfully.",
        "sql": guard.sanitized_sql,
        "rows": rows,
        "presentation": presentation.model_dump(),
    }
