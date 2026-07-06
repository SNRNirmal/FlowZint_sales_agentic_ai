"""LangGraph checkpointer configuration.

This module provides a thread-safe, singleton checkpointer for the LangGraph
StateGraph. It persists the full GraphState after every node completes, keyed
by thread_id (we use deal_id as the thread_id), enabling mid-pipeline suspension
and resumption.

Production Considerations
-------------------------
The current backend defaults to SQLite via SqliteSaver, which is suitable for
hackathons, local development, and low-concurrency deployments. The database
is created automatically if the parent directory does not exist.

For production with high concurrency, PostgresSaver is recommended. This file
is structured so that swapping to PostgresSaver is isolated entirely here — no
other module (including builder.py) needs to know which backend is used.

Thread-safety and Singleton Lifecycle
-------------------------------------
`get_checkpointer()` is called at startup from the FastAPI lifespan
handler (before any request is accepted) and never again thereafter
— the singleton is set once and only read after that. The
`threading.Lock` around construction guards against the degenerate
case where `get_checkpointer()` is called concurrently during a test
or by future code that bypasses the lifespan pre-warm.

Graceful Shutdown
-----------------
The checkpointer uses a context manager (`SqliteSaver.from_conn_string`) which
is entered at startup. `close_checkpointer()` must be called during the FastAPI
lifespan shutdown (after `yield`) to cleanly close the database connection.

Startup Failure
---------------
If initialization fails (e.g., read-only filesystem or invalid path), the
exception propagates to the caller. When called from the FastAPI lifespan,
this aborts the process immediately, ensuring a "fail fast" startup behavior.
"""

import logging
import os
import sqlite3
import threading
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Optional

from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger("threshold.memory.checkpointer")

_checkpointer_instance: Optional[SqliteSaver] = None
_checkpointer_cm: Optional[AbstractContextManager] = None
_checkpointer_lock = threading.Lock()


def get_checkpointer() -> SqliteSaver:
    """Return the singleton checkpointer, initializing it if necessary.

    Uses double-checked locking for thread safety.

    Configuration:
    - CHECKPOINT_BACKEND (default: sqlite)
    - CHECKPOINT_DB_PATH (default: checkpoints/threshold_checkpoints.db)

    Raises
    ------
    Exception
        Propagates any exception encountered during directory creation,
        database connection, or schema setup. In a FastAPI lifespan, this
        causes a fail-fast startup abort.
    """
    global _checkpointer_instance, _checkpointer_cm

    if _checkpointer_instance is not None:
        return _checkpointer_instance

    with _checkpointer_lock:
        if _checkpointer_instance is not None:
            return _checkpointer_instance

        backend = os.environ.get("CHECKPOINT_BACKEND", "sqlite").lower()
        if backend != "sqlite":
            logger.warning(f"Unsupported checkpoint backend '{backend}', falling back to sqlite")

        default_path = Path(__file__).parent.parent / "checkpoints" / "threshold_checkpoints.db"
        db_path_str = os.environ.get("CHECKPOINT_DB_PATH", str(default_path))
        db_path = Path(db_path_str).resolve()

        logger.info(
            "Initializing checkpointer",
            extra={"backend": "sqlite", "db_path": str(db_path)},
        )

        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create checkpoint directory: {e}")
            raise

        try:
            if hasattr(SqliteSaver, "from_conn_string"):
                cm = SqliteSaver.from_conn_string(str(db_path))
                instance = cm.__enter__()
                _checkpointer_cm = cm
            else:
                conn = sqlite3.connect(str(db_path), check_same_thread=False)
                instance = SqliteSaver(conn)
                _checkpointer_cm = None

            instance.setup()
            _checkpointer_instance = instance
            logger.info("Checkpointer initialized and schema tables created")
        except Exception as e:
            logger.error(f"Failed to initialize SqliteSaver: {e}")
            raise

    return _checkpointer_instance


def close_checkpointer() -> None:
    """Cleanly close the checkpointer connection.

    Must be called during application shutdown (e.g., FastAPI lifespan teardown).
    """
    global _checkpointer_instance, _checkpointer_cm

    with _checkpointer_lock:
        if _checkpointer_cm is not None:
            logger.info("Closing checkpointer connection")
            try:
                _checkpointer_cm.__exit__(None, None, None)
            except Exception as e:
                logger.error(f"Error while closing checkpointer: {e}")
            finally:
                _checkpointer_cm = None
                _checkpointer_instance = None
                logger.info("Checkpointer shutdown complete")
        elif _checkpointer_instance is not None:
            logger.info("Closing checkpointer connection (manual fallback)")
            try:
                if hasattr(_checkpointer_instance, "conn"):
                    _checkpointer_instance.conn.close()
            except Exception as e:
                logger.error(f"Error while closing manual checkpointer connection: {e}")
            finally:
                _checkpointer_instance = None
                logger.info("Checkpointer shutdown complete")


def thread_config(deal_id: str) -> dict[str, Any]:
    """Standard RunnableConfig dict for a given deal's graph thread.

    Centralised here so every call site uses the same thread_id convention
    (deal_id) and the same key structure without duplicating the dict literal.
    """
    return {"configurable": {"thread_id": deal_id}}


def reset_for_testing() -> None:
    """Close and clear the checkpointer singleton so the next
    get_checkpointer() call re-reads CHECKPOINT_DB_PATH. Exists for the
    test suite; production uses close_checkpointer() at shutdown.

    Callers must also call graphs.builder.reset_for_testing(): a
    previously compiled graph holds a reference to the now-closed
    checkpointer and will fail on next use."""
    close_checkpointer()
