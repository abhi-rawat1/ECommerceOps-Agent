from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
APP_ENV = os.getenv("APP_ENV", "dev")
_ENV_FILE = BASE_DIR / f".{APP_ENV}.env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)


@dataclass(frozen=True)
class Settings:
    app_env: str = APP_ENV
    postgres_url: str = os.getenv("POSTGRES_URL", "")
    db_schema: str = os.getenv("DB_SCHEMA", "ecommerce")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    allowed_tables: tuple[str, ...] = tuple(
        table.strip()
        for table in os.getenv(
            "ALLOWED_TABLES",
            "customers,orders,order_items,products,returns,refunds,inventory,shipments",
        ).split(",")
        if table.strip()
    )
    approval_required_actions: tuple[str, ...] = tuple(
        table.strip()
        for table in os.getenv(
            "APPROVAL_REQUIRED_ACTIONS",
            "refund_order,initiate_refund,create_return,initiate_return,cancel_order,cancel_item,update_inventory",
        ).split(",")
        if table.strip()
    )
    log_dir: str = os.getenv("LOG_DIR", "logs")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    streamlit_port: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    langgraph_checkpoint_store: str = os.getenv("LANGGRAPH_CHECKPOINT_STORE", "memory")
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))


settings = Settings()

if not settings.postgres_url:
    raise RuntimeError("POSTGRES_URL must be configured for CustomerSupportAssist.")
