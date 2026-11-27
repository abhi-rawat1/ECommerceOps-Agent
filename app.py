import json
import os
from urllib import error, request
import uuid

import pandas as pd
import streamlit as st

API_BASE_URL = os.getenv("CUSTOMER_SUPPORT_API_URL", "http://localhost:8000")
API_REQUEST_TIMEOUT_SECONDS = int(os.getenv("API_REQUEST_TIMEOUT_SECONDS", "180"))


def api_request(method: str, path: str, payload: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    api_url = f"{API_BASE_URL}{path}"
    req = request.Request(api_url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=API_REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", "Request failed")
        except Exception:
            detail = str(exc)
        raise ValueError(f"API error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise ValueError(f"Cannot reach ECommerceOps-Agent API at {API_BASE_URL}: {exc.reason}") from exc
    except Exception as exc:
        raise ValueError(f"API request failed: {exc}") from exc


def login_support_user(username: str, password: str):
    response = api_request("POST", "/login", {"username": username, "password": password})
    if response and "user" in response and "access_token" in response:
        user = response["user"]
        user["token"] = response["access_token"]
        return user
    raise ValueError("Unable to authenticate. Verify the API service and credentials.")


def list_pending_approvals_for_ui():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/approvals/pending", token=token)
    return response.get("approvals", []) if response else []


def list_all_approvals_for_ui():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/approvals", token=token)
    return response.get("approvals", []) if response else []


def create_approval_request_for_ui(order_id: str, action_type: str, reason: str, requested_by: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/approvals",
        {"order_id": order_id, "action_type": action_type, "reason": reason, "requested_by": requested_by},
        token=token,
    )
    if not response:
        raise ValueError("Approval service API did not return a response")
    return response


def approve_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request("POST", "/approvals/decision", {"request_id": request_id, "approved_by": approved_by, "decision": "approved", "comments": comments}, token=token)
    if not response:
        raise ValueError("Approval service API did not return a response")
    return response


def reject_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request("POST", "/approvals/decision", {"request_id": request_id, "approved_by": approved_by, "decision": "rejected", "comments": comments}, token=token)
    if not response:
        raise ValueError("Approval service API did not return a response")
    return response


def cancel_request_for_ui(request_id: str, approved_by: str, comments: str):
    token = st.session_state.get("access_token")
    response = api_request("POST", "/approvals/decision", {"request_id": request_id, "approved_by": approved_by, "decision": "cancelled", "comments": comments}, token=token)
    if not response:
        raise ValueError("Approval service API did not return a response")
    return response


def process_support_request_via_api(message: str):
    token = st.session_state.get("access_token")
    response = api_request("POST", "/support/request", {
        "message": message,
        "conversation_id": st.session_state.conversation_id,
    }, token=token)
    if not response:
        raise ValueError("Support workflow API did not return a response")
    return response


def resume_support_request_via_api(answer: str, pending_state: dict):
    token = st.session_state.get("access_token")
    response = api_request("POST", "/support/follow-up", {
        "answer": answer,
        "pending_state": pending_state,
        "conversation_id": st.session_state.conversation_id,
    }, token=token)
    if not response:
        raise ValueError("Support workflow API did not return a response")
    return response


def metric_lookup_via_api(metric_name: str):
    token = st.session_state.get("access_token")
    response = api_request("GET", f"/metrics/{metric_name}", token=token)
    print('Metric lookup response: *************')
    print(response)

    if not response:
        raise ValueError("Metrics API did not return a response")
    return response


def audit_events_via_api():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/audit", token=token)
    return response.get("events", []) if response else []


def render_query_result(response: dict):
    rows = response.get("rows", [])
    presentation = response.get("presentation")
    sql = response.get("sql")

    if sql:
        with st.expander("Generated SQL"):
            st.code(sql, language="sql")

    if not rows:
        st.info(response.get("answer", "No results found."))
        return

    df = pd.DataFrame(rows)
    if not presentation:
        st.dataframe(df, use_container_width=True)
        return

    output_format = presentation.get("format", "table")
    title = presentation.get("title")
    if title:
        st.subheader(title)

    x_field = presentation.get("x_field")
    y_field = presentation.get("y_field")

    if output_format == "summary":
        summary_text = presentation.get("summary_text") or ""
        bullets = presentation.get("bullets") or []
        if summary_text:
            st.markdown(f"<div class='summary-card'><p>{summary_text}</p></div>", unsafe_allow_html=True)
        for bullet in bullets:
            st.markdown(f"- {bullet}")
    elif output_format == "table":
        st.dataframe(df, use_container_width=True)
    elif output_format == "line_chart" and x_field in df.columns and y_field in df.columns:
        st.line_chart(df.set_index(x_field)[y_field])
    elif output_format == "bar_chart" and x_field in df.columns and y_field in df.columns:
        st.bar_chart(df.set_index(x_field)[y_field])
    elif output_format == "metric" and len(df.columns) == 1:
        st.metric(title or "Metric", df.iloc[0, 0])
    else:
        st.dataframe(df, use_container_width=True)


def render_workflow_response(result: dict):
    response = result.get("response", {}) if isinstance(result, dict) else {}
    status = response.get("status")
    st.subheader("Result")

    if status == "awaiting_follow_up":
        st.warning(response.get("answer"))
        missing = response.get("missing_fields", [])
        if missing:
            st.caption("Missing information: " + ", ".join(missing))
    elif status == "awaiting_human_approval":
        st.warning(response.get("answer"))
        if response.get("approval_request"):
            st.json(response["approval_request"])
    elif status in {"ok", "blocked"} and (response.get("rows") or response.get("presentation") or response.get("sql")):
        render_query_result(response)
    elif status == "action_completed":
        st.success(response.get("answer"))
    elif status == "no_action_needed":
        st.info(response.get("answer"))
    elif status == "not_found":
        st.error(response.get("answer"))
    else:
        st.info(response.get("answer", "No result available."))


st.set_page_config(page_title="ECommerceOps-Agent", page_icon="🛍️", layout="wide")

st.markdown("""
<style>
:root { --csa-primary: #5B8DEF; --csa-bg: #F4F7FB; --csa-card: #FFFFFF; --csa-border: #E7ECF3; }
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg, #F8FAFE 0%, #F1F5FA 100%); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #0E1B2E; }
[data-testid="stSidebar"] * { color: #EAF1FB !important; }
[data-testid="stSidebar"] .stTextInput input { background: #172840; color: #FFFFFF !important; }
.block-container { max-width: 1180px; padding-top: 2rem; }
h1, h2, h3 { letter-spacing: -0.02em; color: #10233F; }
[data-testid="stMetric"] { background: var(--csa-card); border: 1px solid var(--csa-border); border-radius: 14px; padding: 18px; box-shadow: 0 8px 24px rgba(31,45,61,.06); }
[data-testid="stDataFrame"] { border: 1px solid var(--csa-border); border-radius: 12px; overflow: hidden; box-shadow: 0 6px 18px rgba(31,45,61,.05); }
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; background: #EDF2F8; padding: 10px 18px; }
.stTabs [aria-selected="true"] { background: #FFFFFF; border-bottom: 3px solid var(--csa-primary); }
.stButton > button, [data-testid="stFormSubmitButton"] > button { border-radius: 10px; border: none; background: linear-gradient(135deg, #5B8DEF, #4F6EE8); color: white; font-weight: 650; padding: 0.55rem 1.1rem; box-shadow: 0 6px 16px rgba(79,110,232,.22); }
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius: 10px; }
.summary-card { background: linear-gradient(135deg, #FFFFFF, #F7F9FF); border: 1px solid #DFE7F5; border-left: 5px solid #5B8DEF; border-radius: 14px; padding: 18px 20px; margin: 8px 0 14px 0; box-shadow: 0 8px 24px rgba(31,45,61,.06); }
.summary-card p { color: #24364B; line-height: 1.65; margin: 0; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stExpander"] { border: 1px solid var(--csa-border); border-radius: 12px; background: white; }
</style>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_workflow" not in st.session_state:
    st.session_state.pending_workflow = None
if "last_workflow_result" not in st.session_state:
    st.session_state.last_workflow_result = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if st.session_state.user is None:
    st.title("CustomerSupportAssist")
    st.caption("Internal support operations portal")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                user = login_support_user(username, password)
                st.session_state.user = user
                st.session_state.access_token = user.get("token")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.stop()

user = st.session_state.user
st.title(f"ECommerceOps-Agent | {user['name']}")
st.caption("E-commerce support operations dashboard")

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("Support controls")
    approved_action = st.toggle("Approval mode enabled", value=False, help="Allow risky actions like refund and return execution.")
    st.caption("Default policy: read-only mode unless explicitly approved.")

    st.markdown("---")
    st.subheader("Account")
    st.write(f"User: {user['name']}")
    st.write(f"Role: {user['role']}")
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.access_token = None
        st.session_state.conversation_id = str(uuid.uuid4())
        st.rerun()

    st.markdown("---")
    st.subheader("Quick actions")
    st.button("For the Order # 2, show order total, payment status, and shipping status. Also, show the products bought under this order")
    st.button("total_revenue daily trend for Oct-2026 month")
    st.button("Inventory risk summary")

query_examples = [
    "Display the order count daily trend for Oct-2026 month",
    "Show the last 5 orders for customer 457",
    "Check inventory for SKU-123 and tell me if stock is low",
    "What is the return rate over the last 30 days?",
    "Initiate a return for order 10021",
]



metrics = [
    "total_revenue",
    "orders_count",
    "return_rate",
    "avg_order_value",
    "refund_resolution_time_days",
]

with st.container():
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Revenue (30d)", "$42.5K")
    with kpi2:
        st.metric("Orders", "1,284")
    with kpi3:
        st.metric("Return rate", "2.8%")
    with kpi4:
        st.metric("Inventory health", "94%")


tabs = st.tabs(["Operations", "Approval Center", "Metrics", "Audit Log"])

with tabs[0]:
    prompt = st.text_area("Ask a customer support question", value=query_examples[0], height=120)
    if st.button("Run support workflow"):
        try:
            with st.spinner("Analyzing support request..."):
                result = process_support_request_via_api(prompt)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        response = result.get("response", {})
        st.session_state.pending_workflow = response.get("pending_state")
        st.session_state.last_workflow_result = result
        st.session_state.history.append({"prompt": prompt, "result": result})

    if st.session_state.last_workflow_result:
        render_workflow_response(st.session_state.last_workflow_result)

        if st.session_state.last_workflow_result.get("trace"):
            with st.expander("Workflow trace"):
                st.json(st.session_state.last_workflow_result["trace"])

    if st.session_state.pending_workflow:
        pending = st.session_state.pending_workflow
        with st.form("workflow_follow_up", clear_on_submit=True):
            st.caption("Complete the requested information to continue this workflow.")
            follow_up_answer = st.text_input("Your answer")
            resume_clicked = st.form_submit_button("Continue workflow")

        if resume_clicked:
            if not follow_up_answer.strip():
                st.error("Please provide the missing information.")
            else:
                try:
                    resumed = resume_support_request_via_api(follow_up_answer.strip(), pending)
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()

                resumed_response = resumed.get("response", {})
                st.session_state.pending_workflow = resumed_response.get("pending_state")
                st.session_state.last_workflow_result = resumed
                st.session_state.history.append({"prompt": follow_up_answer, "result": resumed})
                st.rerun()

    if st.session_state.history:
        st.subheader("Recent interactions")
        for item in reversed(st.session_state.history[-5:]):
            st.markdown(f"**Q:** {item['prompt']}")
            st.json(item["result"].get("response", {}))

with tabs[1]:
    st.subheader("Create approval request")
    col1, col2 = st.columns(2)
    with col1:
        order_id = st.text_input("Order ID", "10021")
        action_type = st.selectbox("Action", ["refund_order", "create_return", "cancel_order", "update_inventory"])
    with col2:
        reason = st.text_input("Reason", "Damaged item received")
        requested_by = st.text_input("Requested by", user["username"])

    if st.button("Submit approval request"):
        payload = create_approval_request_for_ui(order_id, action_type, reason, requested_by)
        st.success(f"Approval request created: {payload['request_id']}")
        st.json(payload)

    st.markdown("---")
    st.subheader("Pending approvals")
    pending = list_pending_approvals_for_ui()
    if pending:
        pending_df = pd.DataFrame(pending)
        st.dataframe(pending_df, use_container_width=True)
        for _, row in pending_df.iterrows():
            with st.container():
                st.markdown(f"### {row['request_id']}")
                st.write(row.to_dict())
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button(f"Approve {row['request_id']}", key=f"approve-{row['request_id']}"):
                        approve_request_for_ui(row["request_id"], user["username"], "Approved by internal ops review")
                        st.success(f"Approved request {row['request_id']}")
                        st.rerun()
                with col_b:
                    if st.button(f"Reject {row['request_id']}", key=f"reject-{row['request_id']}"):
                        reject_request_for_ui(row["request_id"], user["username"], "Rejected by internal ops review")
                        st.warning(f"Rejected request {row['request_id']}")
                        st.rerun()
                with col_c:
                    if st.button(f"Cancel {row['request_id']}", key=f"cancel-{row['request_id']}"):
                        cancel_request_for_ui(row["request_id"], user["username"], "Cancelled by requestor or ops")
                        st.info(f"Cancelled request {row['request_id']}")
                        st.rerun()
    else:
        st.info("No pending approvals.")

    st.subheader("Approval history")
    history = list_all_approvals_for_ui()
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True)

with tabs[2]:
    st.subheader("Semantic metrics")
    metric_name = st.selectbox("Metric", metrics)
    if st.button("Refresh metric"):
        metric = metric_lookup_via_api(metric_name)
        st.json(metric)
    '''
    st.markdown("---")
    st.subheader("Analytics")
    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "Revenue": [48, 52, 55, 60, 58, 62],
        "Returns": [5, 6, 7, 5, 4, 3],
        "Inventory Health": [88, 90, 92, 94, 93, 95],
    }
    df = pd.DataFrame(data)
    st.line_chart(df.set_index("Month")["Revenue"])
    st.bar_chart(df.set_index("Month")["Returns"])
    st.line_chart(df.set_index("Month")["Inventory Health"])
    '''

with tabs[3]:
    st.subheader("Audit trail")
    events = audit_events_via_api()
    if events:
        st.json(events)
    else:
        st.info("No audit events found.")

st.markdown("---")
st.markdown(
    """
    Supported workflows:
    - Order status and order history lookups
    - Customer support summaries
    - Inventory checks
    - Return and refund approval gates
    - DBT-style metric reporting
    """
)
