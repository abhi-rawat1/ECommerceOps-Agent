from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import declarative_base, sessionmaker

from services.db import engine
from services.jwt_service import create_access_token
from config import settings

Base = declarative_base()


class UserModel(Base):
    __tablename__ = "support_users"

    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

DEFAULT_USERS = {
    "support_agent": {"password": "support123", "role": "support_agent", "name": "Support Agent"},
    "ops_manager": {"password": "ops123", "role": "operations_manager", "name": "Operations Manager"},
    "finance_analyst": {"password": "finance123", "role": "finance_analyst", "name": "Finance Analyst"},
}


class UserStore:
    def __init__(self) -> None:
        self._seed_default_users()

    def _seed_default_users(self) -> None:
        if settings.app_env.lower() != "dev":
            return
        session = SessionLocal()
        for username, user in DEFAULT_USERS.items():
            existing = session.query(UserModel).filter(UserModel.username == username).first()
            if existing is None:
                record = UserModel(
                    id=f"usr-{username}",
                    username=username,
                    password=user["password"],
                    role=user["role"],
                    name=user["name"],
                    is_active=True,
                )
                session.add(record)
        session.commit()
        session.close()

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        session = SessionLocal()
        user = session.query(UserModel).filter(UserModel.username == username, UserModel.is_active.is_(True)).first()
        session.close()
        if user is None:
            return None
        if user.password != password:
            return None
        payload = {
            "username": user.username,
            "role": user.role,
            "name": user.name,
            "authenticated": True,
        }
        payload["token"] = create_access_token(user.username, user.role)
        return payload

    def create_user(self, username: str, password: str, role: str, name: str) -> dict[str, Any]:
        session = SessionLocal()
        existing = session.query(UserModel).filter(UserModel.username == username).first()
        if existing:
            session.close()
            raise ValueError(f"User '{username}' already exists")
        record = UserModel(id=f"usr-{username}", username=username, password=password, role=role, name=name, is_active=True)
        session.add(record)
        session.commit()
        session.refresh(record)
        session.close()
        return {
            "username": record.username,
            "role": record.role,
            "name": record.name,
            "authenticated": True,
        }

    def list_users(self) -> list[dict[str, Any]]:
        session = SessionLocal()
        rows = session.query(UserModel).filter(UserModel.is_active.is_(True)).all()
        session.close()
        return [{"username": row.username, "role": row.role, "name": row.name} for row in rows]


user_store = UserStore()


def authenticate_support_agent(username: str, password: str) -> dict[str, Any]:
    user = user_store.authenticate(username, password)
    if user is None:
        raise ValueError("Invalid username or password")
    return user


def create_support_user(username: str, password: str, role: str, name: str) -> dict[str, Any]:
    return user_store.create_user(username, password, role, name)


def list_support_users() -> list[dict[str, Any]]:
    return user_store.list_users()


def list_roles() -> list[str]:
    return sorted({user["role"] for user in list_support_users()})
