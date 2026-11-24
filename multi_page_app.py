import json
import os
from urllib import error, request

import streamlit as st

API_BASE_URL = os.getenv("CUSTOMER_SUPPORT_API_URL", "http://localhost:8000")
API_REQUEST_TIMEOUT_SECONDS = int(os.getenv("API_REQUEST_TIMEOUT_SECONDS", "180"))


def api_request(method: str, path: str, payload: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(f"{API_BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=API_REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(str(exc))


st.set_page_config(page_title="ECommerceOps-Agent Ops", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None

if st.session_state.user is None:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                response = api_request("POST", "/login", {"username": username, "password": password})
                st.session_state.user = response["user"]
                st.session_state.access_token = response["access_token"]
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.stop()

user = st.session_state.user
role = user["role"]
allowed = {
    "support_agent": ["Operations", "Approval Center", "Audit Log"],
    "operations_manager": ["Operations", "Approval Center", "Metrics", "Audit Log"],
    "finance_analyst": ["Metrics", "Audit Log"],
}
page_name = st.sidebar.selectbox("Navigate", allowed.get(role, ["Operations"]))

if page_name == "Operations":
    st.title("Operations")
    st.info("Use the main CustomerSupportAssist dashboard for support workflows.")
elif page_name == "Approval Center":
    st.title("Approval Center")
    response = api_request("GET", "/approvals/pending", token=st.session_state.access_token)
    st.write(response.get("approvals", []))
elif page_name == "Metrics":
    st.title("Metrics")
    st.info("Select and refresh semantic metrics in the main dashboard.")
elif page_name == "Audit Log":
    st.title("Audit Log")
    response = api_request("GET", "/audit", token=st.session_state.access_token)
    st.write(response.get("events", []))
