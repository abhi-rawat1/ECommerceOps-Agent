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
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            raise ValueError(payload.get("detail", "Request failed")) from exc
        except Exception:
            raise ValueError(str(exc)) from exc
    except Exception:
        return None


def login_admin_user(username: str, password: str):
    response = api_request("POST", "/login", {"username": username, "password": password})
    if response and "user" in response and "access_token" in response:
        user = response["user"]
        user["token"] = response["access_token"]
        return user
    raise ValueError("Invalid username or password")


def create_user_via_api(username: str, password: str, role: str, name: str):
    token = st.session_state.get("access_token")
    response = api_request(
        "POST",
        "/users",
        {"username": username, "password": password, "role": role, "name": name},
        token=token,
    )
    if response:
        return response
    return None


def list_users_via_api():
    token = st.session_state.get("access_token")
    response = api_request("GET", "/users", token=token)
    if response and "users" in response:
        return response["users"]
    return None


st.set_page_config(page_title="ECommerceOps-Agent Admin", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None

if st.session_state.user is None:
    with st.form("admin_login"):
        username = st.text_input("Admin username")
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            try:
                user = login_admin_user(username, password)
                if user["role"] != "operations_manager":
                    st.error("Only operations managers can access the admin panel.")
                    st.stop()
                st.session_state.user = user
                st.session_state.access_token = user.get("token")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.stop()

st.title("Admin Portal")
st.caption(f"Signed in as {st.session_state.user['name']} ({st.session_state.user['role']})")

with st.sidebar:
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.access_token = None
        st.rerun()

st.subheader("Create user")
with st.form("create_user"):
    new_username = st.text_input("Username")
    new_password = st.text_input("Password", type="password")
    new_name = st.text_input("Full name")
    new_role = st.selectbox("Role", ["support_agent", "operations_manager", "finance_analyst"])
    create_clicked = st.form_submit_button("Create user")
    if create_clicked:
        try:
            created = create_user_via_api(new_username, new_password, new_role, new_name)
            st.success(f"Created user {created['username']} with role {created['role']}")
        except ValueError as exc:
            st.error(str(exc))

st.subheader("Existing users")
users = list_users_via_api()
if users:
    st.dataframe(users)
else:
    st.info("No users found.")
