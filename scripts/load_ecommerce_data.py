import os
from pathlib import Path

from sqlalchemy import text

from services.db import engine

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "seed_ecommerce_large.sql"


def ensure_schema_and_seed():
    script = SQL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ecommerce;"))
        conn.execute(text(script))
    print("E-commerce schema and seed data loaded successfully.")


if __name__ == "__main__":
    ensure_schema_and_seed()
