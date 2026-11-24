from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

from config import settings

LOG_PATH = Path(settings.log_dir) / "support_audit.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_langfuse_client = None
_langfuse_init_attempted = False

_PII_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"),
)


def mask_sensitive_text(value: Any) -> Any:
    if isinstance(value, str):
        masked = value
        masked = _PII_PATTERNS[0].sub("[email]", masked)
        masked = _PII_PATTERNS[1].sub("[payment-card]", masked)
        return masked
    if isinstance(value, dict):
        return {key: mask_sensitive_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_sensitive_text(item) for item in value]
    return value


def _get_langfuse_client():
    global _langfuse_client, _langfuse_init_attempted
    if _langfuse_init_attempted:
        return _langfuse_client
    _langfuse_init_attempted = True

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            environment=os.getenv("APP_ENV", "development"),
            release=os.getenv("APP_VERSION", "0.1.0"),
            mask=lambda data, *_: mask_sensitive_text(data),
        )
    except Exception:
        _langfuse_client = None
    return _langfuse_client


def get_langfuse_langchain_handler():
    client = _get_langfuse_client()
    if client is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:
        return None


@contextmanager
def langfuse_workflow_trace(
    name: str,
    input_payload: dict[str, Any],
    request_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Iterator[Any | None]:
    client = _get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        from langfuse import propagate_attributes

        masked_input = mask_sensitive_text(input_payload)
        attributes = propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=["customer-support", "agentic-workflow"],
            metadata={
                "request_id": request_id,
                "application": "customer-support-assist",
                "feature": "support-workflow",
            },
        )
        observation = client.start_as_current_observation(
            as_type="span",
            name=name,
            input=masked_input,
            metadata={
                "request_id": request_id,
                "application": "customer-support-assist",
            },
        )
    except Exception:
        yield None
        return

    with attributes:
        with observation as root:
            yield root


def write_audit_event(event_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": request_id or "unknown",
        "payload": mask_sensitive_text(payload),
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, default=str) + "\n")
    return event


def trace_request_step(step_name: str, request_id: str, details: dict[str, Any]) -> dict[str, Any]:
    return write_audit_event(step_name, details, request_id=request_id)


def record_langfuse_score(
    trace_name: str,
    score_name: str,
    value: float,
    comment: str | None = None,
) -> None:
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        with client.start_as_current_observation(
            as_type="span",
            name=trace_name,
        ) as span:
            span.score_trace(name=score_name, value=value, comment=comment)
    except Exception:
        pass


def flush_langfuse() -> None:
    client = _get_langfuse_client()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass


def shutdown_langfuse() -> None:
    client = _get_langfuse_client()
    if client is not None:
        try:
            client.shutdown()
        except Exception:
            pass
