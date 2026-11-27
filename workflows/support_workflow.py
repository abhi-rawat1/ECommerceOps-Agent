from __future__ import annotations

import uuid
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from core.guardrails import detect_support_intent
from core.tracing import (
    flush_langfuse,
    get_langfuse_langchain_handler,
    langfuse_workflow_trace,
    mask_sensitive_text,
    trace_request_step,
)
from services.approval_service import create_approval_request
from services.checkpoint_store import build_checkpoint_saver
from services.memory_store import (
    ensure_session,
    list_memories,
    load_recent_turns,
    load_workflow_state,
    save_conversation_turn,
    save_workflow_state,
)
from services.sql_agent import build_sql_agent


class SupportWorkflowState(TypedDict, total=False):
    user_message: str
    request_id: str
    approved_action: bool
    intent: str
    confidence: float
    entities: dict[str, Any]
    missing_fields: list[str]
    follow_up_question: str | None
    status: str
    answer: str
    approval_request: dict[str, Any] | None
    rows: list[dict[str, Any]]
    presentation: dict[str, Any] | None
    sql: str | None
    original_message: str
    follow_up_answer: str | None
    trace: list[dict[str, Any]]
    conversation_id: str | None
    recent_turns: list[dict[str, Any]]
    conversation_context: str


_ACTION_TYPES = {
    "initiate_refund": "refund_order",
    "cancel_item": "cancel_order",
    "cancel_order": "cancel_order",
    "initiate_return": "create_return",
}

_REQUIRED_FIELDS = {
    "initiate_refund": ("order_id",),
    "cancel_item": ("order_id",),
    "cancel_order": ("order_id",),
    "initiate_return": ("order_id",),
    "refund_status": ("order_id", "refund_id"),
    "lookup_order": ("order_id",),
}


def _required_missing(intent: str, entities: dict[str, Any]) -> list[str]:
    if intent in {"cancel_item", "cancel_order"}:
        if entities.get("order_id") or entities.get("customer_id"):
            return []
        return ["order_id or customer_id"]

    if intent == "metric_query" and not entities.get("metric_name"):
        return ["metric_name"]

    required = _REQUIRED_FIELDS.get(intent, ())
    if intent == "refund_status":
        if entities.get("order_id") or entities.get("refund_id"):
            return []
        return ["order_id or refund_id"]
    missing: list[str] = []
    for field in required:
        if not entities.get(field):
            missing.append(field)
    return missing


_REFERENCE_HINTS = (
    "that",
    "those",
    "same",
    "previous",
    "again",
    "last one",
    "this order",
    "this customer",
    "the order",
    "the customer",
)


def _turn_metadata(turn: dict[str, Any]) -> dict[str, Any]:
    metadata = turn.get("metadata") or {}
    if isinstance(metadata, str):
        import json

        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
    return metadata if isinstance(metadata, dict) else {}


def _format_conversation_context(turns: list[dict[str, Any]], memories: list[dict[str, Any]] | None = None) -> str:
    blocked_keys = ("password", "secret", "token", "credential", "card", "authorization")
    lines: list[str] = []
    for memory in (memories or [])[:5]:
        key = str(memory.get("memory_key") or "")
        if any(word in key.lower() for word in blocked_keys):
            continue
        value = mask_sensitive_text(memory.get("memory_value"))
        lines.append(f"memory {key}: {value}")
    for turn in turns[-8:]:
        role = str(turn.get("role") or "user")
        content = mask_sensitive_text(str(turn.get("content") or ""))
        entities = _turn_metadata(turn).get("entities")
        suffix = f" entities={entities}" if entities else ""
        lines.append(f"{role}: {content}{suffix}")
    return "\n".join(lines)


def _merge_referenced_entities(message: str, entities: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill empty entities from the latest prior turn when the message refers to it."""
    text = message.lower()
    if not any(hint in text for hint in _REFERENCE_HINTS):
        return entities
    prior: dict[str, Any] = {}
    for turn in reversed(turns):
        candidate = _turn_metadata(turn).get("entities")
        if isinstance(candidate, dict) and candidate:
            prior = candidate
            break
    if not prior:
        return entities
    merged = dict(prior)
    for key, value in entities.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _prompt_context(state: SupportWorkflowState) -> str:
    return str(state.get("conversation_context") or "")


def _persisted_workflow_state(state: dict[str, Any]) -> dict[str, Any]:
    skipped = {"recent_turns", "conversation_context"}
    return {key: value for key, value in state.items() if key not in skipped}


def _intent_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    trace_request_step("request_received", request_id, {"user_message": state["user_message"]})
    decision = detect_support_intent(state["user_message"], conversation_context=_prompt_context(state))
    entities = _merge_referenced_entities(
        state["user_message"],
        decision.entities or {},
        state.get("recent_turns") or [],
    )
    if getattr(decision, "metric_name", None):
        entities = {**entities, "metric_name": decision.metric_name}
    missing = _required_missing(decision.intent, entities)

    payload = decision.model_dump()
    trace_request_step("llm_intent_detected", request_id, payload)

    return {
        **state,
        "intent": decision.intent,
        "confidence": decision.confidence,
        "entities": entities,
        "missing_fields": missing,
        "follow_up_question": decision.follow_up_question,
        "status": "classified",
    }


def _route_node(state: SupportWorkflowState) -> str:
    intent = state.get("intent", "unknown")
    if state.get("missing_fields"):
        return "awaiting_follow_up"
    if intent == "metric_query":
        return "metric_query"
    if intent in _ACTION_TYPES:
        return "lifecycle_action"
    if intent in {"refund_status", "general_query", "lookup_order", "lookup_customer_orders", "inventory_check"}:
        return "read_query"
    return "clarification"


def _read_query_node(state: SupportWorkflowState) -> SupportWorkflowState:
    from services.query_result_service import generate_and_execute_query

    request_id = state["request_id"]
    trace_request_step("read_query_started", request_id, {"intent": state["intent"]})
    query_result = generate_and_execute_query(
        state["user_message"],
        conversation_context=_prompt_context(state),
    )
    trace_request_step("final_response", request_id, {
        "sql": query_result.get("sql"),
        "row_count": len(query_result.get("rows", [])),
        "presentation": query_result.get("presentation"),
    })
    return {
        **state,
        "status": query_result["status"],
        "answer": query_result["answer"],
        "rows": query_result.get("rows", []),
        "presentation": query_result.get("presentation"),
        "sql": query_result.get("sql"),
        "approval_request": None,
    }


def _human_approval_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    intent = state["intent"]
    entities = state.get("entities", {})
    action_type = _ACTION_TYPES[intent]
    order_id = str(entities.get("order_id") or entities.get("item_id") or "unknown")
    reason = str(entities.get("reason") or entities.get("return_reason") or f"Human approval requested for {intent}")

    approval = create_approval_request(
        order_id=order_id,
        action_type=action_type,
        reason=reason,
        requested_by="support-agent",
    )
    trace_request_step(
        "human_approval_requested",
        request_id,
        {"intent": intent, "request_id": approval["request_id"]},
    )
    return {
        **state,
        "status": "awaiting_human_approval",
        "answer": "This action requires human approval before execution.",
        "approval_request": approval,
    }


def _follow_up_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    missing = state.get("missing_fields", [])
    question = state.get("follow_up_question")
    if not question:
        question = "Please provide the missing information: " + ", ".join(missing) + "."
    trace_request_step("follow_up_required", request_id, {"missing_fields": missing, "question": question})
    return {
        **state,
        "status": "awaiting_follow_up",
        "answer": question,
        "approval_request": None,
    }


def _clarification_node(state: SupportWorkflowState) -> SupportWorkflowState:
    request_id = state["request_id"]
    answer = state.get("follow_up_question") or "Please clarify whether you need an order lookup or want to initiate a refund, return, or cancellation."
    trace_request_step("clarification_required", request_id, {"intent": state.get("intent")})
    return {**state, "status": "awaiting_clarification", "answer": answer, "approval_request": None}


def _metric_query_node(state: SupportWorkflowState) -> SupportWorkflowState:
    from services.metrics_service import find_semantic_metric
    from services.query_result_service import generate_and_execute_query

    entities = state.get("entities", {})
    metric_name = entities.get("metric_name")
    metric = find_semantic_metric(metric_name)

    if metric is None:
        trace_request_step("metric_not_defined", state["request_id"], {"metric_name": metric_name})
        return _read_query_node({**state, "intent": "general_query"})

    metric_payload = {"metric_name": metric_name, "definition": metric}
    query_result = generate_and_execute_query(
        state["user_message"],
        semantic_metric=metric_payload,
        conversation_context=_prompt_context(state),
    )
    trace_request_step("metric_query_executed", state["request_id"], {
        "metric_name": metric_name,
        "sql": query_result.get("sql"),
    })
    return {
        **state,
        "status": query_result["status"],
        "answer": query_result["answer"],
        "rows": query_result.get("rows", []),
        "presentation": query_result.get("presentation"),
        "sql": query_result.get("sql"),
        "approval_request": None,
    }


def _lifecycle_action_node(state: SupportWorkflowState) -> SupportWorkflowState:
    from services.lifecycle_service import process_cancel_or_return, process_refund

    intent = state["intent"]
    entities = state.get("entities", {})
    order_id = str(entities.get("order_id") or "")
    customer_id = str(entities.get("customer_id") or "") or None
    reason = str(entities.get("reason") or entities.get("return_reason") or f"Approval requested for {intent}")

    if not order_id and not customer_id:
        return {**state, "status": "awaiting_follow_up", "answer": "Please provide the order ID or customer ID.", "missing_fields": ["order_id or customer_id"]}

    if intent == "initiate_refund":
        result = process_refund(order_id, reason, "support-agent")
    else:
        result = process_cancel_or_return(order_id, intent, reason, "support-agent", customer_id=customer_id)

    trace_request_step("lifecycle_action_evaluated", state["request_id"], {"intent": intent, "order_id": order_id, "status": result["status"]})
    return {
        **state,
        "status": result["status"],
        "answer": result["answer"],
        "approval_request": result.get("approval_request"),
        "missing_fields": result.get("missing_fields", state.get("missing_fields", [])),
        "follow_up_question": result.get("answer") if result["status"] == "awaiting_follow_up" else state.get("follow_up_question"),
        "rows": [],
        "presentation": None,
        "sql": None,
    }


def build_support_workflow(checkpointer=None):
    graph = StateGraph(SupportWorkflowState)
    graph.add_node("intent", _intent_node)
    graph.add_node("read_query", _read_query_node)
    graph.add_node("human_approval", _human_approval_node)
    graph.add_node("awaiting_follow_up", _follow_up_node)
    graph.add_node("clarification", _clarification_node)
    graph.add_node("metric_query", _metric_query_node)
    graph.add_node("lifecycle_action", _lifecycle_action_node)

    graph.set_entry_point("intent")
    graph.add_conditional_edges(
        "intent",
        _route_node,
        {
            "read_query": "read_query",
            "human_approval": "human_approval",
            "awaiting_follow_up": "awaiting_follow_up",
            "clarification": "clarification",
            "metric_query": "metric_query",
            "lifecycle_action": "lifecycle_action",
        },
    )
    graph.add_edge("read_query", END)
    graph.add_edge("human_approval", END)
    graph.add_edge("awaiting_follow_up", END)
    graph.add_edge("clarification", END)
    graph.add_edge("metric_query", END)
    graph.add_edge("lifecycle_action", END)
    return graph.compile(checkpointer=checkpointer)


_support_workflow = build_support_workflow(build_checkpoint_saver())


def resume_support_request(
    follow_up_answer: str,
    pending_state: dict[str, Any],
    user_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Merge a user's answer into pending state and continue graph execution."""
    if not pending_state:
        return process_support_request(
            follow_up_answer,
            user_id=user_id,
            session_id=session_id,
            conversation_id=conversation_id,
        )

    conversation_id = conversation_id or str(pending_state.get("conversation_id") or uuid.uuid4())
    if user_id:
        ensure_session(conversation_id, user_id)
        persisted = load_workflow_state(conversation_id, user_id)
        if persisted:
            pending_state = {**persisted.get("state", {}), **pending_state}

    original_message = str(pending_state.get("original_message") or pending_state.get("user_message") or "")
    previous_entities = dict(pending_state.get("entities") or {})
    combined_message = f"{original_message}\nFollow-up answer: {follow_up_answer}"

    recent_turns = load_recent_turns(conversation_id, user_id, limit=10) if user_id else []
    memories = list_memories(user_id, "user") if user_id else []
    conversation_context = _format_conversation_context(recent_turns, memories)
    decision = detect_support_intent(combined_message, conversation_context=conversation_context)
    merged_entities = {**previous_entities, **(decision.entities or {})}
    if getattr(decision, "metric_name", None):
        merged_entities["metric_name"] = decision.metric_name

    intent = pending_state.get("intent") or decision.intent
    missing = _required_missing(intent, merged_entities)
    if not missing:
        missing = _required_missing(decision.intent, merged_entities)

    request_id = str(pending_state.get("request_id") or uuid.uuid4())
    state: SupportWorkflowState = {
        "user_message": combined_message,
        "original_message": original_message,
        "follow_up_answer": follow_up_answer,
        "request_id": request_id,
        "approved_action": bool(pending_state.get("approved_action")),
        "intent": intent,
        "confidence": decision.confidence,
        "entities": merged_entities,
        "missing_fields": missing,
        "follow_up_question": decision.follow_up_question,
        "status": "classified",
        "rows": [],
        "presentation": None,
        "sql": None,
        "trace": [],
        "conversation_id": conversation_id,
        "recent_turns": recent_turns,
        "conversation_context": conversation_context,
    }

    trace_request_step("follow_up_received", request_id, {"follow_up_answer": follow_up_answer})
    thread_config = {"configurable": {"thread_id": conversation_id}}
    final_state = _support_workflow.invoke(state, thread_config)
    trace_request_step("workflow_resumed", request_id, {"status": final_state["status"], "intent": intent})

    pending_state_output = None
    if final_state["status"] == "awaiting_follow_up":
        pending_state_output = {
            "original_message": original_message,
            "request_id": request_id,
            "approved_action": state["approved_action"],
            "intent": intent,
            "entities": merged_entities,
            "missing_fields": final_state.get("missing_fields", missing),
            "conversation_id": conversation_id,
        }

    if user_id:
        save_conversation_turn(
            conversation_id,
            user_id,
            "user",
            str(mask_sensitive_text(follow_up_answer)),
            {
                "request_id": request_id,
                "kind": "follow_up",
                "intent": final_state.get("intent"),
                "entities": final_state.get("entities") or {},
            },
        )
        save_conversation_turn(
            conversation_id,
            user_id,
            "assistant",
            str(mask_sensitive_text(final_state.get("answer") or "")),
            {"request_id": request_id, "status": final_state["status"]},
        )
        save_workflow_state(
            conversation_id,
            user_id,
            request_id,
            final_state["status"],
            _persisted_workflow_state(final_state),
        )

    return {
        "conversation_id": conversation_id,
        "response": {
            "status": final_state["status"],
            "intent": final_state.get("intent"),
            "confidence": final_state.get("confidence"),
            "answer": final_state.get("answer"),
            "missing_fields": final_state.get("missing_fields", []),
            "approval_request": final_state.get("approval_request"),
            "rows": final_state.get("rows", []),
            "presentation": final_state.get("presentation"),
            "sql": final_state.get("sql"),
            "pending_state": pending_state_output,
        },
        "trace": [{"event": "workflow_resumed", "request_id": request_id, "payload": {"status": final_state["status"]}}],
    }


def process_support_request(
    user_message: str,
    approved_action: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    conversation_id = conversation_id or str(uuid.uuid4())
    recent_turns: list[dict[str, Any]] = []
    memories: list[dict[str, Any]] = []
    if user_id:
        ensure_session(conversation_id, user_id)
        recent_turns = load_recent_turns(conversation_id, user_id, limit=10)
        memories = list_memories(user_id, "user")

    initial_state: SupportWorkflowState = {
        "user_message": user_message,
        "request_id": request_id,
        "approved_action": approved_action,
        "original_message": user_message,
        "follow_up_answer": None,
        "entities": {},
        "missing_fields": [],
        "rows": [],
        "presentation": None,
        "sql": None,
        "trace": [],
        "conversation_id": conversation_id,
        "recent_turns": recent_turns,
        "conversation_context": _format_conversation_context(recent_turns, memories),
    }
    trace_request_step(
        "workflow_started",
        request_id,
        {"user_id": user_id, "session_id": session_id, "user_message": user_message},
    )

    thread_config = {"configurable": {"thread_id": conversation_id}}
    with langfuse_workflow_trace(
        name="support-workflow-turn",
        input_payload={"user_message": user_message},
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
    ) as root_span:
        final_state = _support_workflow.invoke(initial_state, thread_config)
        trace_request_step("workflow_completed", request_id, {"status": final_state["status"]})
        if root_span is not None:
            root_span.update(
                input={"user_message": user_message},
                output={"status": final_state["status"], "answer": final_state.get("answer")},
                metadata={
                    "intent": final_state.get("intent"),
                    "confidence": final_state.get("confidence"),
                    "request_id": request_id,
                },
            )

    flush_langfuse()

    if user_id:
        save_conversation_turn(
            conversation_id,
            user_id,
            "user",
            str(mask_sensitive_text(user_message)),
            {
                "request_id": request_id,
                "kind": "initial",
                "intent": final_state.get("intent"),
                "entities": final_state.get("entities") or {},
            },
        )
        save_conversation_turn(
            conversation_id,
            user_id,
            "assistant",
            str(mask_sensitive_text(final_state.get("answer") or "")),
            {"request_id": request_id, "status": final_state["status"]},
        )
        save_workflow_state(
            conversation_id,
            user_id,
            request_id,
            final_state["status"],
            _persisted_workflow_state(final_state),
        )

    return {
        "conversation_id": conversation_id,
        "response": {
            "status": final_state["status"],
            "intent": final_state.get("intent"),
            "confidence": final_state.get("confidence"),
            "answer": final_state.get("answer"),
            "missing_fields": final_state.get("missing_fields", []),
            "approval_request": final_state.get("approval_request"),
            "rows": final_state.get("rows", []),
            "presentation": final_state.get("presentation"),
            "sql": final_state.get("sql"),
            "pending_state": {
                "original_message": user_message,
                "request_id": request_id,
                "approved_action": approved_action,
                "intent": final_state.get("intent"),
                "entities": final_state.get("entities", {}),
                "missing_fields": final_state.get("missing_fields", []),
                "conversation_id": conversation_id,
            } if final_state["status"] == "awaiting_follow_up" else None,
        },
        "trace": [
            {"event": "workflow_completed", "request_id": request_id, "payload": {"status": final_state["status"]}},
        ],
    }
