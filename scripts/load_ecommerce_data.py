import os
from pathlib import Path

from sqlalchemy import text

from services.db import engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = PROJECT_ROOT / "sql" / "seed_ecommerce_large.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def ensure_schema_and_seed():
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ecommerce;"))

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with engine.begin() as conn:
        for migration in migration_files:
            conn.execute(text(migration.read_text(encoding="utf-8")))

    seed_script = SQL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(seed_script))
    print("E-commerce schema, migrations, and seed data loaded successfully.")


if __name__ == "__main__":
    ensure_schema_and_seed()
