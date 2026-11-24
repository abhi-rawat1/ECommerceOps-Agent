from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

APP_ENV = os.getenv("APP_ENV", "dev").lower()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "480"))

if APP_ENV != "dev" and not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY must be configured when APP_ENV is not dev.")

if APP_ENV == "dev" and not JWT_SECRET_KEY:
    JWT_SECRET_KEY = "local-development-only-secret-32chars!"


def create_access_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
