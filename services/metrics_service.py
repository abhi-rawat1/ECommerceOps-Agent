from pathlib import Path
from typing import Any

import yaml

METRIC_MODEL_PATH = Path(__file__).resolve().parents[1] / "dbt" / "semantic_models" / "customer_support_metrics.yml"


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
