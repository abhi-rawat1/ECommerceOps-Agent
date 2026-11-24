from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from services.db import engine

Base = declarative_base()


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True)
    request_id = Column(String, unique=True, nullable=False)
    order_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    requested_by = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    approved_by = Column(String, nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


class ApprovalStore:
    def create_request(self, order_id: str, action_type: str, reason: str, requested_by: str, status: str = "pending") -> dict[str, Any]:
        session = SessionLocal()
        request_id = f"apr-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash((order_id, action_type, requested_by))) % 10000}"
        model = ApprovalRequestModel(
            id=request_id,
            request_id=request_id,
            order_id=order_id,
            action_type=action_type,
            reason=reason,
            requested_by=requested_by,
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        session.close()
        return self._to_dict(model)

    def list_pending(self) -> list[dict[str, Any]]:
        session = SessionLocal()
        rows = session.query(ApprovalRequestModel).filter(ApprovalRequestModel.status == "pending").all()
        session.close()
        return [self._to_dict(row) for row in rows]

    def list_all(self) -> list[dict[str, Any]]:
        session = SessionLocal()
        rows = session.query(ApprovalRequestModel).all()
        session.close()
        return [self._to_dict(row) for row in rows]

    def update_status(self, request_id: str, status: str, approved_by: str | None = None, comments: str | None = None) -> dict[str, Any]:
        session = SessionLocal()
        record = session.query(ApprovalRequestModel).filter(ApprovalRequestModel.request_id == request_id).first()
        if record is None:
            session.close()
            raise ValueError(f"Request ID not found: {request_id}")
        record.status = status
        record.approved_by = approved_by
        record.comments = comments
        record.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(record)
        session.close()
        return self._to_dict(record)

    @staticmethod
    def _to_dict(model: ApprovalRequestModel) -> dict[str, Any]:
        return {
            "id": model.id,
            "request_id": model.request_id,
            "order_id": model.order_id,
            "action_type": model.action_type,
            "reason": model.reason,
            "requested_by": model.requested_by,
            "status": model.status,
            "approved_by": model.approved_by,
            "comments": model.comments,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }


approval_store = ApprovalStore()
