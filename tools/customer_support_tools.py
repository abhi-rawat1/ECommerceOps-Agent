from langchain.tools import tool

from core.guardrails import validate_sql_query
from services.db import execute_read_query, fetch_table_schema

@tool
def execute_read_query_tool(sql: str):
    """Execute a read-only SQL query and return the results."""
    guard = validate_sql_query(sql)
    if not guard.allowed:
        return {"error": guard.reason}
    return execute_read_query(guard.sanitized_sql)

@tool
def get_support_schema():
    """Return the supported ecommerce schema for the support agent."""
    return fetch_table_schema()


@tool
def get_metric(metric_name: str):
    """Return a semantic metric defined in the DBT model layer."""
    from services.metrics_service import metric_lookup

    return metric_lookup(metric_name)
