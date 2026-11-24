from __future__ import annotations

from typing import Any

from services.approval_store import approval_store

VALID_APPROVAL_STATUSES = {"pending", "approved", "rejected", "cancelled"}


def create_approval_request(order_id: str, action_type: str, reason: str, requested_by: str, status: str = "pending") -> dict[str, Any]:
    if status not in VALID_APPROVAL_STATUSES:
        status = "pending"
    return approval_store.create_request(order_id, action_type, reason, requested_by, status=status)


def list_pending_approvals() -> list[dict[str, Any]]:
    return approval_store.list_pending()


def list_all_approvals() -> list[dict[str, Any]]:
    return approval_store.list_all()


def update_approval_status(request_id: str, status: str, approved_by: str | None = None, comments: str | None = None) -> dict[str, Any]:
    if status not in VALID_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported approval status: {status}")
    return approval_store.update_status(request_id, status, approved_by, comments)


def approve_request(request_id: str, approved_by: str, comments: str | None = None) -> dict[str, Any]:
    return update_approval_status(request_id, "approved", approved_by, comments)


def reject_request(request_id: str, approved_by: str, comments: str | None = None) -> dict[str, Any]:
    return update_approval_status(request_id, "rejected", approved_by, comments)


def cancel_request(request_id: str, approved_by: str | None = None, comments: str | None = None) -> dict[str, Any]:
    return update_approval_status(request_id, "cancelled", approved_by, comments)
