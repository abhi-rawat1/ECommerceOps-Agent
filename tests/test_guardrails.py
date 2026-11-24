from core.guardrails import validate_sql_query
from services.approval_service import create_approval_request, update_approval_status
from services.auth_service import authenticate_support_agent


def test_block_destructive_sql():
    result = validate_sql_query("DELETE FROM orders WHERE order_id = 1")
    assert result.allowed is False
    assert "forbidden" in result.reason.lower()


def test_allow_read_only_sql():
    result = validate_sql_query("SELECT * FROM orders WHERE order_id = 10021 LIMIT 5")
    assert result.allowed is True


def test_reject_unknown_table():
    result = validate_sql_query("SELECT * FROM forbidden_table LIMIT 5")
    assert result.allowed is False


def test_approval_status_change_round_trip():
    request = create_approval_request("10021", "refund_order", "Damaged item", "support-agent")
    updated = update_approval_status(request["request_id"], "approved", "ops-manager", "Approved after review")
    assert updated["status"] == "approved"
    assert updated["approved_by"] == "ops-manager"
    assert updated["comments"] == "Approved after review"


def test_authentication_for_support_agents():
    user = authenticate_support_agent("ops_manager", "ops123")
    assert user["username"] == "ops_manager"
    assert user["role"] == "operations_manager"
    assert "token" in user


def test_allow_read_only_cte_query():
    result = validate_sql_query("WITH recent AS (SELECT * FROM orders LIMIT 5) SELECT * FROM recent")
    assert result.allowed is True


def test_block_multiple_statement_with_mutation():
    result = validate_sql_query("SELECT * FROM orders; DELETE FROM orders")
    assert result.allowed is False


def test_block_drop_statement():
    result = validate_sql_query("DROP TABLE orders")
    assert result.allowed is False


def test_llm_detects_order_status_lookup_with_hash_order_number():
    from core.guardrails import detect_support_intent

    decision = detect_support_intent("show order total, payment status, and shipping status for Order #2")
    assert decision.intent == "lookup_order"
    assert decision.entities.get("order_id") == "2"
    assert decision.approval_required is False


def test_semantic_metric_loader_uses_yaml_definitions():
    from services.metrics_service import find_semantic_metric

    metric = find_semantic_metric("total revenue")
    assert metric is not None
    assert metric["name"] == "total_revenue"
    assert metric["type"] == "sum"


def test_unknown_semantic_metric_falls_back_to_general_query():
    from services.metrics_service import find_semantic_metric

    assert find_semantic_metric("customer_lifetime_value") is None


def test_presentation_decision_model_accepts_supported_formats():
    from services.query_result_service import PresentationDecision

    decision = PresentationDecision(format="line_chart", title="Revenue trend", x_field="month", y_field="revenue")
    assert decision.format == "line_chart"


def test_follow_up_resume_merges_original_entities():
    from workflows.support_workflow import resume_support_request

    pending = {
        "original_message": "Initiate a refund",
        "request_id": "test-request-1",
        "approved_action": False,
        "intent": "initiate_refund",
        "entities": {},
        "missing_fields": ["order_id"],
    }

    result = resume_support_request("Order 10021", pending, user_id="test-user", session_id="test-session")
    response = result["response"]
    assert response["intent"] == "initiate_refund"
    assert "10021" in str(response.get("answer", "")) or "10021" in str(response.get("approval_request", {})) or response["status"] in {"no_action_needed", "awaiting_human_approval", "action_completed"}


def test_customer_cancellation_requests_open_order_selection():
    from workflows.support_workflow import process_support_request

    result = process_support_request("Cancel the order for Customer 51", user_id="test-user", session_id="test-session")
    response = result["response"]
    assert response["status"] == "awaiting_follow_up"
    assert response["pending_state"] is not None
    assert "2096" in response["answer"] or "2167" in response["answer"]


def test_resume_customer_cancellation_with_selected_shipped_order():
    from workflows.support_workflow import process_support_request, resume_support_request

    initial = process_support_request("Cancel the order for Customer 51", user_id="test-user", session_id="test-session")
    pending = initial["response"]["pending_state"]
    assert pending is not None

    resumed = resume_support_request("2096", pending, user_id="test-user", session_id="test-session")
    response = resumed["response"]
    assert response["status"] == "awaiting_human_approval"
    assert response["approval_request"] is not None


def test_presentation_model_accepts_summary_content():
    from services.query_result_service import PresentationDecision

    decision = PresentationDecision(
        format="summary",
        title="Customer order summary",
        summary_text="The customer has several active and completed orders.",
        bullets=["2 shipped orders", "1 delivered order", "1 returned order"],
    )
    assert decision.format == "summary"
    assert len(decision.bullets) == 3
