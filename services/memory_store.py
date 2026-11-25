from __future__ import annotations

import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from services.db import engine


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_session(session_id: str, user_id: str, ttl_hours: int = 24) -> dict[str, Any]:
    now = _utc_now()
    expires_at = now + timedelta(hours=ttl_hours)
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, user_id, status, expires_at
            FROM ecommerce.agent_sessions
            WHERE id = :session_id
        """), {"session_id": session_id}).mappings().first()

        if row:
            if row["user_id"] != user_id:
                raise PermissionError("Conversation session belongs to another user")
            if row["status"] != "active" or (row["expires_at"] and row["expires_at"] <= now):
                raise ValueError("Conversation session is inactive or expired")
            conn.execute(text("""
                UPDATE ecommerce.agent_sessions
                SET updated_at = :now, expires_at = :expires_at
                WHERE id = :session_id AND user_id = :user_id
            """), {"now": now, "expires_at": expires_at, "session_id": session_id, "user_id": user_id})
            return {"session_id": session_id, "user_id": user_id, "status": "active"}

        conn.execute(text("""
            INSERT INTO ecommerce.agent_sessions
                (id, user_id, status, created_at, updated_at, expires_at, metadata)
            VALUES
                (:id, :user_id, 'active', :now, :now, :expires_at, '{}'::jsonb)
        """), {"id": session_id, "user_id": user_id, "now": now, "expires_at": expires_at})
    return {"session_id": session_id, "user_id": user_id, "status": "active"}


def save_conversation_turn(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    ensure_session(session_id, user_id)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ecommerce.agent_conversation_turns
                (id, session_id, user_id, role, content, metadata, created_at)
            VALUES
                (:id, :session_id, :user_id, :role, :content, CAST(:metadata AS jsonb), :now)
        """), {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": json.dumps(metadata or {}),
            "now": _utc_now(),
        })


def load_recent_turns(session_id: str, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    ensure_session(session_id, user_id)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT role, content, metadata, created_at
            FROM ecommerce.agent_conversation_turns
            WHERE session_id = :session_id AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"session_id": session_id, "user_id": user_id, "limit": limit}).mappings()
        result = [dict(row) for row in rows]
    result.reverse()
    return result


def save_workflow_state(
    session_id: str,
    user_id: str,
    request_id: str,
    status: str,
    state: dict[str, Any],
    ttl_hours: int = 24,
) -> None:
    ensure_session(session_id, user_id, ttl_hours=ttl_hours)
    now = _utc_now()
    expires_at = now + timedelta(hours=ttl_hours)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ecommerce.agent_workflow_state
                (session_id, user_id, request_id, state, status, created_at, updated_at, expires_at)
            VALUES
                (:session_id, :user_id, :request_id, CAST(:state AS jsonb), :status, :now, :now, :expires_at)
            ON CONFLICT (session_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                request_id = EXCLUDED.request_id,
                state = EXCLUDED.state,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at,
                expires_at = EXCLUDED.expires_at
        """), {
            "session_id": session_id,
            "user_id": user_id,
            "request_id": request_id,
            "state": json.dumps(state, default=str),
            "status": status,
            "now": now,
            "expires_at": expires_at,
        })


def load_workflow_state(session_id: str, user_id: str) -> dict[str, Any] | None:
    ensure_session(session_id, user_id)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT state, status, request_id, expires_at
            FROM ecommerce.agent_workflow_state
            WHERE session_id = :session_id AND user_id = :user_id
        """), {"session_id": session_id, "user_id": user_id}).mappings().first()
    if not row:
        return None
    if row["expires_at"] and row["expires_at"] <= _utc_now():
        return None
    return dict(row)


def save_memory(
    owner_id: str,
    memory_type: str,
    memory_key: str,
    memory_value: dict[str, Any] | Any,
    scope: str = "user",
    source_request_id: str | None = None,
    confidence: float | None = None,
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    if scope not in {"user", "role", "global"}:
        raise ValueError("Invalid memory scope")
    now = _utc_now()
    expires_at = now + timedelta(hours=ttl_hours) if ttl_hours else None
    memory_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ecommerce.agent_memories
                (id, scope, owner_id, memory_type, memory_key, memory_value,
                 source_request_id, confidence, expires_at, created_at, updated_at)
            VALUES
                (:id, :scope, :owner_id, :memory_type, :memory_key, CAST(:memory_value AS jsonb),
                 :source_request_id, :confidence, :expires_at, :now, :now)
            ON CONFLICT (scope, owner_id, memory_type, memory_key) DO UPDATE SET
                memory_value = EXCLUDED.memory_value,
                source_request_id = EXCLUDED.source_request_id,
                confidence = EXCLUDED.confidence,
                expires_at = EXCLUDED.expires_at,
                updated_at = EXCLUDED.updated_at
        """), {
            "id": memory_id,
            "scope": scope,
            "owner_id": owner_id,
            "memory_type": memory_type,
            "memory_key": memory_key,
            "memory_value": json.dumps(memory_value, default=str),
            "source_request_id": source_request_id,
            "confidence": confidence,
            "expires_at": expires_at,
            "now": now,
        })
    return {"scope": scope, "owner_id": owner_id, "memory_type": memory_type,
            "memory_key": memory_key, "memory_value": memory_value}


def list_memories(owner_id: str, scope: str = "user") -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, scope, owner_id, memory_type, memory_key, memory_value,
                   source_request_id, confidence, expires_at, created_at, updated_at
            FROM ecommerce.agent_memories
            WHERE scope = :scope AND owner_id = :owner_id
              AND (expires_at IS NULL OR expires_at > :now)
            ORDER BY updated_at DESC
        """), {"scope": scope, "owner_id": owner_id, "now": _utc_now()}).mappings()
        return [dict(row) for row in rows]


def delete_memory(owner_id: str, memory_id: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(text("""
            DELETE FROM ecommerce.agent_memories
            WHERE id = :memory_id AND owner_id = :owner_id
        """), {"memory_id": memory_id, "owner_id": owner_id})
        return result.rowcount > 0
