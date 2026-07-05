"""LangGraph checkpointer configuration.

This is the concrete fix for the current architecture's biggest gap:
there is no way today to pause mid-pipeline (e.g., after Delay
Intelligence but before Human Review) and resume later without losing
everything. The checkpointer persists the full GraphState after every
node completes, keyed by thread_id (we use deal_id as the thread_id),
so `interrupt()` in the Human Review node can suspend execution
indefinitely and `Command(resume=...)` can pick up exactly where it
left off.

Uses SqliteSaver for the hackathon build (zero extra infra, matches
the existing SQLite-friendly backend). Swapping to PostgresSaver for
production is a one-line change, isolated entirely to this file — no
other module needs to know which backend is used.

Thread-safety
-------------
`get_checkpointer()` is called at startup from the FastAPI lifespan
handler (before any request is accepted) and never again thereafter
— the singleton is set once and only read after that. The
`threading.Lock` around construction guards against the degenerate
case where `get_checkpointer()` is called concurrently during a test
or by future code that bypasses the lifespan pre-warm.

`setup()` is idempotent (internally uses CREATE TABLE IF NOT EXISTS),
so calling it more than once is safe, but the lock means it is only
called once in practice.

Startup failure
---------------
If `SqliteSaver.setup()` raises (e.g., the checkpoints/ directory
does not exist, or the filesystem is read-only), the exception
propagates to the caller. `main.py` calls `get_checkpointer()` via
`build_graph()` inside the lifespan handler — FastAPI treats a
lifespan exception as a startup failure and aborts the process
immediately, which is exactly the "fail fast" behaviour required.
The server never reaches the request-serving phase with a broken
checkpointer.
"""

import logging
import sqlite3
import threading
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger("threshold.memory.checkpointer")

CHECKPOINT_DB_PATH = Path(__file__).parent.parent / "checkpoints" / "threshold_checkpoints.db"

_checkpointer_instance: SqliteSaver | None = None
_checkpointer_lock = threading.Lock()


def get_checkpointer() -> SqliteSaver:
    """Return the singleton SqliteSaver checkpointer.

    Construction is guarded by a threading.Lock to prevent two threads
    from both seeing ``_checkpointer_instance is None`` simultaneously
    and creating duplicate connections.

    ``SqliteSaver.setup()`` is called exactly once per process
    immediately after construction. It creates the checkpoint schema
    tables (``checkpoints``, ``checkpoint_blobs``, ``checkpoint_writes``)
    using ``CREATE TABLE IF NOT EXISTS``, so repeated calls are a
    no-op — but the lock guarantees it is only invoked once anyway.

    Raises
    ------
    Exception
        Any exception from ``sqlite3.connect()`` or ``setup()`` is
        propagated to the caller. When called from the FastAPI lifespan
        handler this aborts startup immediately (fail fast).
    """
    global _checkpointer_instance

    # Fast path: already constructed — no lock needed for reads because
    # Python reference reads are atomic and the reference is set before
    # the lock is released in the slow path.
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    with _checkpointer_lock:
        # Re-check inside the lock: another thread may have completed
        # construction while this thread was waiting.
        if _checkpointer_instance is not None:
            return _checkpointer_instance

        logger.info(
            "Initializing SqliteSaver checkpointer",
            extra={"db_path": str(CHECKPOINT_DB_PATH)},
        )

        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        instance = SqliteSaver(conn)

        # Create checkpoint schema tables. This call is idempotent
        # (CREATE TABLE IF NOT EXISTS) but only invoked once due to the lock.
        instance.setup()

        _checkpointer_instance = instance
        logger.info("Checkpointer initialized and schema tables created")

    return _checkpointer_instance


def thread_config(deal_id: str) -> dict:
    """Standard RunnableConfig dict for a given deal's graph thread.

    Centralised here so every call site — graph invocations, state
    reads, state-history queries — uses the same thread_id convention
    (deal_id) and the same key structure without duplicating the dict
    literal.
    """
    return {"configurable": {"thread_id": deal_id}}
