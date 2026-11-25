---
name: langgraph-support-workflow
description: "Build, review, and modify the ECommerceOps-Agent LangGraph support workflow. Use for support_workflow.py, StateGraph nodes, intent routing, follow-up state, read queries, semantic metrics, lifecycle actions, approvals, tracing, and architecture updates."
argument-hint: "Describe the workflow change, review, test, or architecture update"
user-invocable: true
disable-model-invocation: false
---

# LangGraph Support Workflow

## Project Purpose

Use this skill for all changes to the support workflow and its graph branches.

Primary implementation:

- `workflows/support_workflow.py`
- `core/guardrails.py`
- `core/tracing.py`
- `services/sql_agent.py`
- `services/query_result_service.py`
- `services/metrics_service.py`
- `services/lifecycle_service.py`
- `services/approval_service.py`
- `docs/architecture.md`
- `tests/`

Read the existing implementation before changing routing or state. Preserve the project’s response and tracing conventions unless the request explicitly changes them.

## When to Use

- Adding or changing an intent
- Adding a LangGraph node or route
- Fixing follow-up or entity-merging behavior
- Adding read, metric, or lifecycle actions
- Updating approval handling
- Adding trace or Langfuse events
- Updating architecture documentation or Mermaid diagrams
- Debugging workflow state and graph branches
- Writing workflow tests

Do not use this skill as a substitute for reviewing SQL, lifecycle, or approval safety code. Those concerns belong in their respective services and guardrails.

## Existing Graph Contract

The workflow is compiled with `StateGraph(SupportWorkflowState)` in `build_support_workflow()`.

Entry point:

1. `_intent_node`
2. `_route_node`
3. Exactly one routed terminal or follow-up node

Node responsibilities:

- `_intent_node`: detect intent, extract entities, calculate missing fields, and set classified status.
- `_route_node`: select `awaiting_follow_up`, `metric_query`, `lifecycle_action`, `read_query`, or `clarification`.
- `_read_query_node`: generate and execute an approved read-only query.
- `_metric_query_node`: resolve a semantic metric, fall back to a general read query, and return query presentation data.
- `_lifecycle_action_node`: process refund, return, or cancellation through lifecycle services.
- `_follow_up_node`: ask for missing fields and end the turn with `awaiting_follow_up`.
- `_clarification_node`: ask for intent clarification and end the turn with `awaiting_clarification`.
- `_human_approval_node`: create an approval request, but verify whether it is reachable; the current `_route_node` routes lifecycle intents to `_lifecycle_action_node`, not `_human_approval_node`.

Every terminal branch must add an edge to `END` unless the graph intentionally introduces a new resumable state.

## State Rules

Keep `SupportWorkflowState` compatible with `TypedDict(total=False)`.

Important state fields:

- `user_message`
- `request_id`
- `approved_action`
- `intent`
- `confidence`
- `entities`
- `missing_fields`
- `follow_up_question`
- `status`
- `answer`
- `approval_request`
- `rows`
- `presentation`
- `sql`
- `original_message`
- `follow_up_answer`
- `trace`

When adding state fields:

1. Add the field to `SupportWorkflowState`.
2. Initialize it in `process_support_request()` if it is required for a first-turn invocation.
3. Initialize or merge it in `resume_support_request()` if follow-up resumption depends on it.
4. Return it from the affected node.
5. Include it in API or trace output only if intentionally part of the contract.

Preserve pending state only for `awaiting_follow_up`. It must contain the original request, request ID, approved action, intent, merged entities, and missing fields.

## Routing Rules

In `_required_missing()` and `_route_node()`:

- Missing required fields route to `awaiting_follow_up` before intent-specific nodes.
- `cancel_item` and `cancel_order` accept either `order_id` or `customer_id`.
- `metric_query` requires `metric_name`.
- `refund_status` accepts either `order_id` or `refund_id`.
- `lookup_order` requires `order_id`.
- `_ACTION_TYPES` maps lifecycle intents to approval action types:
  - `initiate_refund` → `refund_order`
  - `cancel_item` / `cancel_order` → `cancel_order`
  - `initiate_return` → `create_return`

Read intents are:

- `refund_status`
- `general_query`
- `lookup_order`
- `lookup_customer_orders`
- `inventory_check`

Metric queries take precedence over read-query routing.

Unknown intents should preserve clarification behavior rather than silently executing an action or SQL.

## Follow-Up Rules

A follow-up turn must:

1. Use `pending_state` from the previous response when present.
2. Preserve `original_message`.
3. Merge previous entities with entities extracted from the follow-up answer.
4. Recalculate missing fields.
5. Reuse or assign a `request_id` consistently.
6. Trace `follow_up_received`.
7. Invoke the graph with the merged state.
8. Return pending state again only if the result is still `awaiting_follow_up`.

Do not overwrite previously extracted entities with empty values.

## Read and Metric Rules

- Read-only SQL is the default.
- Route SQL through `generate_and_execute_query()` and existing guardrails.
- Restrict execution to allowlisted tables and safe statements.
- Do not add destructive SQL support to a support read branch.
- Semantic metrics should come from `find_semantic_metric()`.
- If no semantic metric is defined, fall back to `_read_query_node()` with `general_query`.
- Trace SQL and presentation data only according to existing data-sensitivity conventions.

## Lifecycle and Approval Rules

Sensitive operations must not execute directly from natural-language classification alone.

The lifecycle service is responsible for interpreting the detected action and obtaining or creating approval evidence. Preserve role checks and human approval requirements at the API/lifecycle boundary.

When modifying lifecycle behavior:

1. Define the supported intent.
2. Add or verify `_ACTION_TYPES` mapping if the action creates an approval.
3. Add required entity handling.
4. Verify missing-field behavior before execution.
5. Use `process_refund()` or `process_cancel_or_return()` appropriately.
6. Return approval request data without pretending the action was executed.
7. Trace the intent, order/customer identifier, and resulting status.

Do not expose approval IDs or sensitive payloads unnecessarily in logs or public responses.

## Tracing and Langfuse Rules

Wrap turns in `langfuse_workflow_trace()` and flush Langfuse after graph completion.

Use `trace_request_step()` for meaningful workflow events, such as:

- `workflow_started`
- `follow_up_received`
- `llm_intent_detected`
- `follow_up_required`
- `metric_query_executed`
- `read_query_started`
- `lifecycle_action_evaluated`
- `human_approval_requested`
- `workflow_completed`

Keep event names stable and specific. Update root-span output with status and answer metadata when appropriate.

## Implementation Procedure

1. Read `support_workflow.py` and the services used by the target branch.
2. Identify the state fields and route affected.
3. Implement the smallest node or routing change.
4. Update `_required_missing()` if entity requirements change.
5. Add or update routing maps and graph edges.
6. Preserve or update trace events.
7. Update lifecycle/approval or SQL service calls when required.
8. Update `docs/architecture.md` so its Mermaid flow matches the executable graph.
9. Add or update tests.
10. Run focused tests, then broader validation.

## Validation Checklist

- Every route in `_route_node` has a matching graph edge.
- Every graph edge targets a real node or `END`.
- Every node returns a complete response shape where required.
- Missing fields route to follow-up before service execution.
- Read branches use SQL guardrails and approved tables.
- Metric branches handle missing semantic definitions safely.
- Lifecycle branches handle missing order/customer IDs safely.
- Sensitive actions require approval and never claim execution before approval.
- Follow-up entity merging does not lose prior entities.
- `process_support_request()` and `resume_support_request()` return consistent status and pending-state fields.
- Traces include a request ID and meaningful status.
- The Mermaid diagram reflects reachable graph behavior rather than aspirational or nonexistent routes.

## Architecture Documentation

The architecture diagram should show:

- FastAPI entry points
- `process_support_request()` and `resume_support_request()`
- `_intent_node`
- `_route_node`
- Read, metric, lifecycle, follow-up, and clarification branches
- SQL guardrails and PostgreSQL
- Semantic metrics
- Lifecycle/approval services
- Approval records and audit logs
- Langfuse and trace events
- Terminal `END` behavior

Distinguish current executable edges from optional or unused nodes. Do not add a direct edge to `_human_approval_node` unless `_route_node` or graph construction is also updated.

## Tests

Run focused tests with:

```powershell
python -m pytest tests/test_guardrails.py
python -m pytest
```

For workflow changes, add tests that verify:

- Classification and routing
- Missing-field follow-up
- Follow-up resumption and entity merging
- Read-query behavior
- Metric fallback behavior
- Lifecycle approval creation
- Terminal graph status
- Response shape
- Trace event inclusion

After editing Python, run the relevant test and check for compile or lint errors.
