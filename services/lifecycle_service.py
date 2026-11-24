from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from services.approval_service import create_approval_request
from services.db import engine


DELIVERED_RETURN_WINDOW_DAYS = 30
REFUND_AUTO_LIMIT = 100.0


def get_customer_cancellation_candidates(customer_id: str) -> list[dict[str, Any]]:
    sql = text("""
        SELECT o.order_id, o.status, o.total_amount, o.shipping_status
        FROM orders o
        WHERE o.customer_id = :customer_id
          AND LOWER(o.status) IN ('processing', 'shipped')
        ORDER BY o.order_date DESC, o.order_id DESC
    """)
    with engine.connect() as connection:
        rows = connection.execute(sql, {"customer_id": int(customer_id)}).mappings().all()
    return [dict(row) for row in rows]


def get_order_lifecycle(order_id: str) -> dict[str, Any]:
    sql = text("""
        SELECT o.order_id, o.status, o.total_amount, o.payment_status,
               o.shipping_status, s.delivered_at, s.shipped_at, s.status AS shipment_status
        FROM orders o
        LEFT JOIN shipments s ON s.order_id = o.order_id
        WHERE o.order_id = :order_id
        ORDER BY s.shipment_id DESC
        LIMIT 1
    """)
    with engine.connect() as connection:
        row = connection.execute(sql, {"order_id": int(order_id)}).mappings().first()
    return dict(row) if row else {}


def _update_order_status(order_id: str, status: str, shipping_status: str | None = None) -> None:
    sql = text("""
        UPDATE orders
        SET status = :status,
            shipping_status = COALESCE(:shipping_status, shipping_status)
        WHERE order_id = :order_id
    """)
    with engine.begin() as connection:
        connection.execute(sql, {
            "order_id": int(order_id),
            "status": status,
            "shipping_status": shipping_status,
        })


def process_cancel_or_return(order_id: str, intent: str, reason: str, requested_by: str, customer_id: str | None = None) -> dict[str, Any]:
    if not order_id and customer_id:
        candidates = get_customer_cancellation_candidates(customer_id)
        if not candidates:
            return {
                "status": "no_action_needed",
                "answer": f"Customer {customer_id} has no processing or shipped orders that can be cancelled.",
            }
        if len(candidates) == 1:
            order_id = str(candidates[0]["order_id"])
        else:
            choices = ", ".join(f"{row['order_id']} ({row['status']})" for row in candidates)
            return {
                "status": "awaiting_follow_up",
                "answer": f"Customer {customer_id} has multiple cancellable orders: {choices}. Please provide the exact order ID.",
                "missing_fields": ["order_id"],
            }

    lifecycle = get_order_lifecycle(order_id)
    if not lifecycle:
        return {"status": "not_found", "answer": f"Order {order_id} was not found."}

    order_status = str(lifecycle.get("status") or "").lower()
    if order_status in {"refunded", "returned", "cancelled", "canceled"}:
        return {
            "status": "no_action_needed",
            "answer": f"Order {order_id} is already {order_status}; no further cancellation or return action is needed.",
        }

    if order_status == "processing":
        if intent in {"cancel_item", "cancel_order"}:
            _update_order_status(order_id, "cancelled", "cancelled")
            return {"status": "action_completed", "answer": f"Order {order_id} was cancelled because it is still processing.", "lifecycle_status": "cancelled"}
        return {
            "status": "no_action_needed",
            "answer": f"Order {order_id} is still processing. It cannot be marked returned until it is shipped and delivered.",
        }

    if order_status == "shipped":
        action_type = "cancel_order" if intent in {"cancel_item", "cancel_order"} else "create_return"
        approval = create_approval_request(order_id, action_type, reason, requested_by)
        return {
            "status": "awaiting_human_approval",
            "answer": f"Order {order_id} has shipped. Approval is required before cancellation or return.",
            "approval_request": approval,
        }

    if order_status == "delivered":
        delivered_at = lifecycle.get("delivered_at")
        if isinstance(delivered_at, str):
            delivered_at = datetime.fromisoformat(delivered_at)
        within_window = False
        if delivered_at:
            if delivered_at.tzinfo is not None:
                delivered_at = delivered_at.replace(tzinfo=None)
            within_window = (datetime.utcnow() - delivered_at).days <= DELIVERED_RETURN_WINDOW_DAYS
        if within_window:
            _update_order_status(order_id, "returned", "returned")
            return {"status": "action_completed", "answer": f"Order {order_id} was changed to returned because it was delivered within the {DELIVERED_RETURN_WINDOW_DAYS}-day window.", "lifecycle_status": "returned"}
        approval = create_approval_request(order_id, "create_return", reason, requested_by)
        return {
            "status": "awaiting_human_approval",
            "answer": f"Order {order_id} was delivered beyond the {DELIVERED_RETURN_WINDOW_DAYS}-day return window. Approval is required.",
            "approval_request": approval,
        }

    return {"status": "no_action_needed", "answer": f"No supported action is available for order {order_id} in status '{order_status}'."}


def process_refund(order_id: str, reason: str, requested_by: str) -> dict[str, Any]:
    lifecycle = get_order_lifecycle(order_id)
    if not lifecycle:
        return {"status": "not_found", "answer": f"Order {order_id} was not found."}

    order_status = str(lifecycle.get("status") or "").lower()
    if order_status in {"refunded", "returned"}:
        if order_status == "refunded":
            return {"status": "no_action_needed", "answer": f"Order {order_id} is already refunded; no further action is needed."}

        amount = float(lifecycle.get("total_amount") or 0)
        if amount < REFUND_AUTO_LIMIT:
            _update_order_status(order_id, "refunded", "refunded")
            return {"status": "action_completed", "answer": f"Order {order_id} was refunded because it is returned and its amount (${amount:.2f}) is below $100.", "lifecycle_status": "refunded"}

        approval = create_approval_request(order_id, "refund_order", reason or "Refund requested for a returned order", requested_by)
        return {
            "status": "awaiting_human_approval",
            "answer": f"Order {order_id} is returned and totals ${amount:.2f}. Refund approval is required because the amount is $100 or more.",
            "approval_request": approval,
        }

    return {
        "status": "no_action_needed",
        "answer": f"Refunds can be initiated only after an order is returned. Order {order_id} is currently '{order_status}'.",
    }
