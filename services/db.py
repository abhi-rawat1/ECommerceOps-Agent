from sqlalchemy import create_engine, text

from config import settings

engine = create_engine(
    settings.postgres_url,
    connect_args={"options": f"-csearch_path={settings.db_schema}"},
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)


def verify_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def fetch_table_schema() -> dict[str, dict[str, str]]:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"), {"schema": settings.db_schema})
        tables = [row[0] for row in result]
        schema: dict[str, dict[str, str]] = {}
        for table in tables:
            columns = conn.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = :schema AND table_name = :table ORDER BY ordinal_position"
                ),
                {"schema": settings.db_schema, "table": table},
            )
            schema[table] = {row[0]: row[1] for row in columns}
        return schema


def execute_read_query(sql: str):
    print(f"Executing SQL query **** : {sql}")
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = [dict(row._mapping) for row in result]
        return rows
