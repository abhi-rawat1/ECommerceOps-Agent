from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from core.guardrails import validate_sql_query
from services.db import execute_read_query

METRIC_MODEL_PATH = Path(__file__).resolve().parents[1] / "dbt" / "semantic_models" / "customer_support_metrics.yml"

# Read-only SQL derived from the semantic metric definitions.
# Series queries return period + value so the dashboard can chart one metric at a time.
_METRIC_SQL: dict[str, dict[str, str]] = {
    "total_revenue": {
        "summary": "SELECT ROUND(SUM(total_amount), 2) AS value FROM orders",
        "series": """
            SELECT date_trunc('month', order_date)::date AS period,
                   ROUND(SUM(total_amount), 2) AS value
            FROM orders
            GROUP BY 1
            ORDER BY 1
        """,
    },
    "orders_count": {
        "summary": "SELECT COUNT(order_id) AS value FROM orders",
        "series": """
            SELECT date_trunc('month', order_date)::date AS period,
                   COUNT(order_id) AS value
            FROM orders
            GROUP BY 1
            ORDER BY 1
        """,
    },
    "return_rate": {
        "summary": """
            SELECT ROUND(
                100.0 * COUNT(DISTINCT r.return_id) / NULLIF(COUNT(DISTINCT o.order_id), 0),
                2
            ) AS value
            FROM orders o
            LEFT JOIN returns r ON r.order_id = o.order_id
        """,
        "series": """
            SELECT date_trunc('month', o.order_date)::date AS period,
                   ROUND(
                       100.0 * COUNT(DISTINCT r.return_id) / NULLIF(COUNT(DISTINCT o.order_id), 0),
                       2
                   ) AS value
            FROM orders o
            LEFT JOIN returns r ON r.order_id = o.order_id
            GROUP BY 1
            ORDER BY 1
        """,
    },
    "avg_order_value": {
        "summary": "SELECT ROUND(AVG(total_amount), 2) AS value FROM orders",
        "series": """
            SELECT date_trunc('month', order_date)::date AS period,
                   ROUND(AVG(total_amount), 2) AS value
            FROM orders
            GROUP BY 1
            ORDER BY 1
        """,
    },
    "refund_resolution_time_days": {
        "summary": """
            SELECT ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 86400.0), 2) AS value
            FROM refunds
            WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL
        """,
        "series": """
            SELECT date_trunc('month', created_at)::date AS period,
                   ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 86400.0), 2) AS value
            FROM refunds
            WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """,
    },
    "fulfillment_delay_days": {
        "summary": """
            SELECT ROUND(AVG(EXTRACT(EPOCH FROM (s.shipped_at - o.created_at)) / 86400.0), 2) AS value
            FROM shipments s
            JOIN orders o ON o.order_id = s.order_id
            WHERE s.shipped_at IS NOT NULL AND o.created_at IS NOT NULL
        """,
        "series": """
            SELECT date_trunc('month', s.shipped_at)::date AS period,
                   ROUND(AVG(EXTRACT(EPOCH FROM (s.shipped_at - o.created_at)) / 86400.0), 2) AS value
            FROM shipments s
            JOIN orders o ON o.order_id = s.order_id
            WHERE s.shipped_at IS NOT NULL AND o.created_at IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """,
    },
}


def load_semantic_metric_definitions() -> dict[str, dict[str, Any]]:
    with METRIC_MODEL_PATH.open("r", encoding="utf-8") as handle:
        model = yaml.safe_load(handle) or {}
    metrics: dict[str, dict[str, Any]] = {}
    for model_entry in model.get("models", []):
        for metric in model_entry.get("metrics", []):
            metrics[str(metric["name"])] = metric
    return metrics


def find_semantic_metric(metric_name: str | None) -> dict[str, Any] | None:
    if not metric_name:
        return None
    normalized = metric_name.strip().lower().replace(" ", "_").replace("-", "_")
    definitions = load_semantic_metric_definitions()
    if normalized in definitions:
        return definitions[normalized]
    for name, definition in definitions.items():
        label = str(definition.get("label", "")).lower().replace(" ", "_")
        if normalized in label:
            return definition
    return None


def get_semantic_metric(metric_name: str) -> dict[str, Any]:
    definition = find_semantic_metric(metric_name)
    if definition is None:
        raise ValueError(f"Unsupported semantic metric: {metric_name}")
    return {"metric_name": metric_name, "definition": definition}


def metric_lookup(metric_name: str) -> dict[str, Any]:
    return get_semantic_metric(metric_name)


def metric_sql(metric_name: str) -> dict[str, str]:
    definition = find_semantic_metric(metric_name)
    if definition is None:
        raise ValueError(f"Unsupported semantic metric: {metric_name}")
    sql = _METRIC_SQL.get(definition["name"])
    if sql is None:
        raise ValueError(f"No executable query is defined for metric: {definition['name']}")
    return sql


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _run_metric_sql(sql: str) -> list[dict[str, Any]]:
    guard = validate_sql_query(sql)
    if not guard.allowed or not guard.sanitized_sql:
        raise ValueError(guard.reason or "Metric SQL was rejected by guardrails.")
    rows = execute_read_query(guard.sanitized_sql)
    if not isinstance(rows, list):
        return []
    return [{key: _json_ready(item) for key, item in row.items()} for row in rows]


def execute_semantic_metric(metric_name: str) -> dict[str, Any]:
    definition = get_semantic_metric(metric_name)["definition"]
    canonical_name = str(definition["name"])
    sql = metric_sql(canonical_name)
    summary_rows = _run_metric_sql(sql["summary"])
    series_rows = _run_metric_sql(sql["series"])
    summary_value = summary_rows[0].get("value") if summary_rows else None
    return {
        "metric_name": canonical_name,
        "definition": definition,
        "summary_value": summary_value,
        "rows": series_rows,
    }
