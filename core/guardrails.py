from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import sqlglot
from sqlglot import exp
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from config import settings


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    sanitized_sql: str | None = None
    action_name: str | None = None


class IntentDecision(BaseModel):
    intent: Literal[
        "general_query",
        "lookup_order",
        "lookup_customer_orders",
        "inventory_check",
        "metric_query",
        "initiate_refund",
        "refund_status",
        "initiate_return",
        "cancel_item",
        "cancel_order",
        "unknown",
    ] = Field(description="Canonical support intent")
    confidence: float = Field(ge=0.0, le=1.0)
    entities: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    approval_required: bool = False
    follow_up_question: str | None = None
    summary: str = ""
    metric_name: str | None = Field(default=None, description="Canonical semantic metric name when a metric is requested")


_INTENT_SYSTEM_PROMPT = """
You are the intent and entity extraction component for an e-commerce customer support agent.

Your task is to classify the full user message and extract entities needed for the next workflow step.
Never execute SQL or perform an action. Return only the structured fields defined by the schema.

CANONICAL INTENTS
- lookup_order: The user wants details or status for one order, including order total, payment status, shipping status, tracking, or a specific order number.
- lookup_customer_orders: The user wants order history or multiple orders for a customer.
- inventory_check: The user asks for stock, inventory, availability, low stock, or SKU quantity.
- metric_query: The user asks for a KPI or aggregate such as revenue, return rate, average order value, refund time, or order count.
- refund_status: The user asks whether or when a refund or refund request was completed. This is read-only.
- initiate_refund: The user asks to issue, process, initiate, or request a refund.
- initiate_return: The user asks to return an order or start a return.
- cancel_item: The user asks to cancel one product/item line, not the complete order.
- cancel_order: The user asks to cancel the whole order.
- general_query: A support question that does not fit another intent or needs an ordinary answer.
- unknown: Use only when the message is genuinely unintelligible or ambiguous between unrelated intents.

ENTITY EXTRACTION
- order_id: Extract an order identifier exactly as the numeric or string value, without "order", "#", or punctuation.
  Examples: "Order #2" -> "2"; "order 10021" -> "10021".
- refund_id: Extract a refund identifier when explicitly present.
- customer_id: Extract a customer identifier when explicitly present.
- product_sku: Extract a SKU when explicitly present.
- item_id: Extract an item/line identifier when explicitly present.
- reason: Extract only an explicitly stated reason.
- return_reason: Extract only an explicitly stated reason for a return.
- status: Extract only an explicitly requested status category.
- metric_name: Extract the named metric when clearly identifiable.
- date_range: Extract only an explicitly stated date range.

ROUTING RULES
1. Questions about an order's total, payment, shipping, tracking, status, or details are lookup_order when an order_id is present.
2. "Show order total, payment status, and shipping status for Order #2" is lookup_order with entities.order_id="2", missing_fields=[], approval_required=false.
3. Messages about a refund's status are refund_status, not initiate_refund.
4. Commands to issue, process, initiate, or request a refund are initiate_refund and require human approval.
5. Commands to return merchandise or initiate a return are initiate_return and require human approval.
6. Commands to cancel an item are cancel_item; commands to cancel the whole order are cancel_order. Both require human approval.
7. Do not infer missing IDs from outside the current message and the supplied conversation context. Add missing_fields and a concise follow_up_question instead.
8. lookup_order requires order_id. lookup_customer_orders requires customer_id. refund_status requires order_id or refund_id. initiate_refund requires order_id and reason. initiate_return requires order_id and return_reason. cancel_item requires order_id and item_id. cancel_order requires order_id.
9. When conversation context is supplied, use it only to resolve references in the current message, such as "that order", "the same customer", "show it again", or "what about last month".
10. Copy order_id, customer_id, product_sku, metric_name, or date_range from conversation context only when the current message depends on them.
11. Do not repeat a prior refund, return, or cancellation unless the current message itself asks for that action.

Output confidence from 0.0 to 1.0. Use high confidence for clear examples and lower confidence for genuinely ambiguous messages.
Do not emit explanatory prose outside the structured result.
"""


def validate_sql_query(sql: str) -> GuardrailResult:
    normalized = sql.strip()
    if not normalized:
        return GuardrailResult(False, "Empty SQL query.")

    if len(normalized) > 20000:
        return GuardrailResult(False, "SQL is too large.")

    try:
        statements = sqlglot.parse(normalized, dialect="postgres")
    except Exception as exc:
        return GuardrailResult(False, f"SQL parse failed: {exc}")

    if not statements:
        return GuardrailResult(False, "No SQL statement was provided.")

    forbidden_types = tuple(
        node
        for node in (
            getattr(exp, "Insert", None),
            getattr(exp, "Update", None),
            getattr(exp, "Delete", None),
            getattr(exp, "Drop", None),
            getattr(exp, "Create", None),
            getattr(exp, "Alter", None),
            getattr(exp, "TruncateTable", None),
            getattr(exp, "Merge", None),
            getattr(exp, "Copy", None),
            getattr(exp, "Command", None),
        )
        if node is not None
    )

    allowed_roots = (exp.Select, exp.With, exp.Union, exp.Except, exp.Intersect)

    for statement in statements:
        if statement is None:
            continue
        if not isinstance(statement, allowed_roots):
            return GuardrailResult(False, f"Forbidden SQL statement type: {statement.key if hasattr(statement, 'key') else type(statement).__name__}.")
        if forbidden_types:
            for forbidden_type in forbidden_types:
                if statement.find(forbidden_type) is not None:
                    return GuardrailResult(False, "Forbidden SQL mutation or DDL statement.")

        cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
        table_names: list[str] = []
        for table in statement.find_all(exp.Table):
            name = table.name
            if name and name.lower() not in cte_names:
                table_names.append(name)

        allowed = {table.lower() for table in settings.allowed_tables}
        for table_name in table_names:
            if table_name.lower() not in allowed:
                return GuardrailResult(False, f"Table '{table_name}' is not allowed by policy.")

    sanitized = "; ".join(statement.sql(dialect="postgres") for statement in statements if statement is not None)
    return GuardrailResult(True, None, sanitized, None)


def require_action_approval(action_name: str, approved: bool) -> GuardrailResult:
    if action_name in settings.approval_required_actions and not approved:
        return GuardrailResult(False, f"Action '{action_name}' requires approval before execution.")
    return GuardrailResult(True, None, None, action_name)


def detect_support_intent(message: str, conversation_context: str | None = None) -> IntentDecision:
    if not settings.openai_api_key:
        return IntentDecision(
            intent="general_query",
            confidence=0.0,
            entities={},
            missing_fields=[],
            approval_required=False,
            follow_up_question="The LLM service is not configured. Please configure OPENAI_API_KEY.",
            summary="LLM intent service unavailable.",
        )

    llm = ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )
    classifier = llm.with_structured_output(IntentDecision, method="function_calling", strict=False)
    try:
        from core.tracing import get_langfuse_langchain_handler

        handler = get_langfuse_langchain_handler()
        invoke_kwargs = {"callbacks": [handler]} if handler is not None else None
        human_message = message
        if conversation_context and conversation_context.strip():
            human_message = (
                "Conversation context:\n"
                f"{conversation_context.strip()}\n\n"
                "Current message:\n"
                f"{message}"
            )
        if invoke_kwargs:
            return classifier.invoke(
                [("system", _INTENT_SYSTEM_PROMPT), ("human", human_message)],
                config=invoke_kwargs,
            )
        return classifier.invoke([("system", _INTENT_SYSTEM_PROMPT), ("human", human_message)])
    except Exception as exc:
        try:
            from core.tracing import trace_request_step

            trace_request_step(
                "intent_classification_failed",
                "unknown",
                {"error_type": type(exc).__name__, "error": str(exc)[:500]},
            )
        except Exception:
            pass
        return IntentDecision(
            intent="unknown",
            confidence=0.0,
            entities={},
            missing_fields=["clarification"],
            approval_required=False,
            follow_up_question="I could not reliably determine the request. Please clarify whether you are asking for an order lookup or want to initiate a refund, return, or cancellation.",
            summary="Intent classification failed safely.",
        )


def detect_action_intent(message: str) -> str:
    """LLM-only action/read intent detection for backward compatibility."""
    return detect_support_intent(message).intent
