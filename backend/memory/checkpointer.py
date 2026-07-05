"""LangGraph checkpointer configuration.

This is the concrete fix for the current architecture's biggest gap:
there is no way today to pause mid-pipeline (e.g., after Delay
Intelligence but before Human Review) and resume later without losing
everything. The checkpointer persists the full GraphState after every
node completes, keyed by thread_id (we use deal_id as the thread_id),
so `interrupt()` in the Human Review node (Module 5) can suspend
execution indefinitely and `Command(resume=...)` can pick up exactly
where it left off.

Uses SqliteSaver for the hackathon build (zero extra infra, matches
the existing SQLite-friendly backend). Swapping to PostgresSaver for
production is a one-line change, isolated entirely to this file — no
other module needs to know which backend is used.
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

CHECKPOINT_DB_PATH = Path(__file__).parent.parent / "checkpoints" / "threshold_checkpoints.db"

_checkpointer_instance: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Returns a singleton SqliteSaver checkpointer. Singleton so every
    graph compile in the process shares one underlying connection
    instead of opening a new sqlite file handle per request."""
    global _checkpointer_instance

    if _checkpointer_instance is None:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        _checkpointer_instance = SqliteSaver(conn)

    return _checkpointer_instance


def thread_config(deal_id: str) -> dict:
    """Standard config dict passed to graph.invoke()/get_state()/
    get_state_history() for a given deal. Centralized here so every
    call site uses the same thread_id convention (deal_id)."""
    return {"configurable": {"thread_id": deal_id}}
