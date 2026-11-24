from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Any

from services.approval_service import (
    approve_request,
    cancel_request,
    create_approval_request,
    list_all_approvals,
    list_pending_approvals,
    reject_request,
)
from services.auth_service import authenticate_support_agent, create_support_user, list_support_users
from services.jwt_service import decode_access_token
from services.metrics_service import get_semantic_metric
from workflows.support_workflow import process_support_request, resume_support_request

app = FastAPI(title="ECommerceOps-Agent API", version="1.0.0")


class ApprovalRequest(BaseModel):
    order_id: str
    action_type: str
    reason: str
    requested_by: str


class ApprovalDecision(BaseModel):
    request_id: str
    approved_by: str
    decision: str = "approved"
    comments: str | None = None


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class SupportRequest(BaseModel):
    message: str


class SupportFollowUpRequest(BaseModel):
    answer: str
    pending_state: dict[str, Any]


def require_user(authorization: str = Header(default=None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        return {
            "username": payload.get("sub"),
            "role": payload.get("role"),
            "authenticated": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def require_role(required_roles: set[str]):
    def wrapper(current_user=Depends(require_user)):
        if current_user.get("role") not in required_roles:
            raise HTTPException(status_code=403, detail="Access denied for this role")
        return current_user

    return wrapper


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/login")
def login(payload: LoginRequest):
    try:
        user = authenticate_support_agent(payload.username, payload.password)
        return {"user": user, "access_token": user["token"]}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/users")
def get_users(current_user=Depends(require_role({"operations_manager", "support_agent"}))):
    return {"users": list_support_users(), "current_user": current_user}


@app.post("/users")
def create_user(payload: UserCreateRequest, current_user=Depends(require_role({"operations_manager"}))):
    try:
        return create_support_user(payload.username, payload.password, payload.role, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/approvals")
def submit_approval(payload: ApprovalRequest, current_user=Depends(require_role({"support_agent", "operations_manager"}))):
    return create_approval_request(
        order_id=payload.order_id,
        action_type=payload.action_type,
        reason=payload.reason,
        requested_by=payload.requested_by,
    )


@app.get("/approvals/pending")
def get_pending_approvals(current_user=Depends(require_role({"operations_manager", "support_agent"}))):
    return {"approvals": list_pending_approvals()}


@app.get("/approvals")
def get_all_approvals(current_user=Depends(require_role({"operations_manager", "finance_analyst"}))):
    return {"approvals": list_all_approvals()}


@app.post("/approvals/decision")
def decide_approval(payload: ApprovalDecision, current_user=Depends(require_role({"operations_manager"}))):
    try:
        if payload.decision.lower() == "approved":
            return approve_request(payload.request_id, payload.approved_by, payload.comments)
        if payload.decision.lower() == "rejected":
            return reject_request(payload.request_id, payload.approved_by, payload.comments)
        if payload.decision.lower() == "cancelled":
            return cancel_request(payload.request_id, payload.approved_by, payload.comments)
        raise ValueError("Decision must be one of: approved, rejected, cancelled")
    except (ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/support/request")
def submit_support_request(payload: SupportRequest, current_user=Depends(require_role({"support_agent", "operations_manager", "finance_analyst"}))):
    return process_support_request(
        payload.message,
        user_id=current_user.get("username"),
        session_id=current_user.get("username"),
    )


@app.post("/support/follow-up")
def submit_support_follow_up(payload: SupportFollowUpRequest, current_user=Depends(require_role({"support_agent", "operations_manager", "finance_analyst"}))):
    return resume_support_request(
        payload.answer,
        payload.pending_state,
        user_id=current_user.get("username"),
        session_id=current_user.get("username"),
    )


@app.get("/metrics/{metric_name}")
def get_metric(metric_name: str, current_user=Depends(require_role({"support_agent", "operations_manager", "finance_analyst"}))):
    try:
        return get_semantic_metric(metric_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/audit")
def get_audit_events(current_user=Depends(require_role({"support_agent", "operations_manager", "finance_analyst"}))):
    from pathlib import Path
    import json

    log_file = Path("logs/support_audit.jsonl")
    if not log_file.exists():
        return {"events": []}
    lines = [line.strip() for line in log_file.open("r", encoding="utf-8") if line.strip()]
    events = [json.loads(line) for line in lines[-100:]]
    return {"events": events}
