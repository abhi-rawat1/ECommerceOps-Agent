from __future__ import annotations

from config import settings

_checkpoint_context = None


def build_checkpoint_saver():
    """Build the configured LangGraph checkpointer for the application process."""
    global _checkpoint_context

    if settings.langgraph_checkpoint_store.lower() == "postgresql":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "LANGGRAPH_CHECKPOINT_STORE=postgresql requires langgraph-checkpoint-postgres"
            ) from exc

        connection_string = settings.postgres_url.replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        _checkpoint_context = PostgresSaver.from_conn_string(connection_string)
        saver = _checkpoint_context.__enter__()
        saver.setup()
        return saver

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
