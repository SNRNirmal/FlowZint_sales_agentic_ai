"""LangGraph checkpointer configuration.

This module provides a singleton checkpointer for the LangGraph
StateGraph. It persists the full GraphState after every node completes, keyed
by thread_id (we use deal_id as the thread_id), enabling mid-pipeline suspension
and resumption.

Why AsyncSqliteSaver
--------------------
The service layer drives the graph exclusively through graph.ainvoke().
The sync SqliteSaver raises NotImplementedError on every async checkpoint
method ("The SqliteSaver does not support async methods"), which made the
first graph.ainvoke() — and therefore POST /webhooks/crm — fail outright.
AsyncSqliteSaver (backed by aiosqlite) implements the async surface natively.

Production Considerations
-------------------------
SQLite is suitable for hackathons, local development, and low-concurrency
deployments. The database is created automatically if the parent directory
does not exist. For production with high concurrency, a Postgres-backed
saver is recommended. This file is structured so that swapping backends is
isolated entirely here — no other module (including builder.py) needs to
know which backend is used.

Singleton Lifecycle (async-only construction)
---------------------------------------------
aiosqlite connections can only be opened and closed from a running event
loop, so the lifecycle is split:

- ``await ainit_checkpointer()`` — awaited once at startup from the FastAPI
  lifespan handler (before build_graph()) or from the test fixture.
  Idempotent: returns the existing singleton if already initialized.
- ``get_checkpointer()`` — sync fast-path accessor used by graphs/builder.py
  at compile time. Raises RuntimeError if ainit_checkpointer() has not
  been awaited yet.
- ``await aclose_checkpointer()`` — awaited at shutdown (lifespan teardown)
  or test teardown. Closing stops aiosqlite's background thread and
  releases the DB file handle (an open handle blocks deleting the file
  on Windows).

Startup Failure
---------------
If initialization fails (e.g., read-only filesystem or invalid path), the
exception propagates to the caller. When called from the FastAPI lifespan,
this aborts the process immediately, ensuring a "fail fast" startup behavior.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

logger = logging.getLogger("threshold.memory.checkpointer")

_checkpointer_instance: Optional[AsyncSqliteSaver] = None
_checkpointer_conn: Optional[aiosqlite.Connection] = None
# Guards the degenerate case of two tasks awaiting ainit_checkpointer()
# concurrently (normal callers — the lifespan handler or the test fixture —
# are single-task). A CONTENDED acquire binds asyncio.Lock to that event
# loop, so aclose_checkpointer() re-instantiates it — otherwise a later
# contended acquire from a different loop (tests get a fresh loop per
# function) would raise RuntimeError.
_init_lock = asyncio.Lock()


async def ainit_checkpointer() -> AsyncSqliteSaver:
    """Initialize and return the singleton AsyncSqliteSaver.

    Idempotent: returns the existing singleton if already initialized.
    Must be awaited before build_graph() — from the FastAPI lifespan
    handler in production, or from the test fixture in the suite.

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
    global _checkpointer_instance, _checkpointer_conn

    if _checkpointer_instance is not None:
        return _checkpointer_instance

    async with _init_lock:
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

        conn: Optional[aiosqlite.Connection] = None
        try:
            conn = await aiosqlite.connect(str(db_path))
            instance = AsyncSqliteSaver(conn)
            await instance.setup()  # commits DDL — the DB file is durable immediately
        except Exception as e:
            logger.error(f"Failed to initialize AsyncSqliteSaver: {e}")
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass  # don't mask the original init failure
            raise

        _checkpointer_conn = conn
        _checkpointer_instance = instance
        logger.info("Checkpointer initialized and schema tables created")

    return _checkpointer_instance


def get_checkpointer() -> AsyncSqliteSaver:
    """Sync fast-path accessor for the initialized singleton.

    graphs/builder.py calls this at compile time; by then the lifespan
    handler (or the test fixture) must already have awaited
    ainit_checkpointer().

    Raises
    ------
    RuntimeError
        If the checkpointer has not been initialized — call
        ainit_checkpointer() at startup / in the test fixture first.
    """
    if _checkpointer_instance is None:
        raise RuntimeError(
            "Checkpointer not initialized — await ainit_checkpointer() "
            "at startup / in the test fixture first."
        )
    return _checkpointer_instance


async def aclose_checkpointer() -> None:
    """Cleanly close the checkpointer connection and clear the singleton.

    Must be awaited during application shutdown (FastAPI lifespan teardown)
    or test teardown. Awaiting conn.close() stops aiosqlite's background
    thread and releases the DB file handle; an unawaited close() is a no-op
    coroutine that leaks the thread and pins the file on Windows.

    Closing while a graph operation is in flight makes that operation fail
    with ``ValueError: Connection closed`` — a clean failure, no DB
    corruption; safe today because requests drain before lifespan teardown,
    but a concern if fire-and-forget graph runs are ever added.

    Test-suite callers must also call graphs.builder.reset_for_testing():
    a previously compiled graph holds a reference to the now-closed
    checkpointer and will fail on next use. The next ainit_checkpointer()
    re-reads CHECKPOINT_DB_PATH.
    """
    global _checkpointer_instance, _checkpointer_conn, _init_lock

    # Fresh, loop-unbound lock for the next init cycle (see _init_lock note).
    _init_lock = asyncio.Lock()

    if _checkpointer_conn is not None:
        logger.info("Closing checkpointer connection")
        try:
            await _checkpointer_conn.close()
        except Exception as e:
            logger.error(f"Error while closing checkpointer: {e}")
        finally:
            _checkpointer_conn = None
            _checkpointer_instance = None
            logger.info("Checkpointer shutdown complete")
    else:
        _checkpointer_instance = None


def thread_config(deal_id: str) -> dict[str, Any]:
    """Standard RunnableConfig dict for a given deal's graph thread.

    Centralised here so every call site uses the same thread_id convention
    (deal_id) and the same key structure without duplicating the dict literal.
    """
    return {"configurable": {"thread_id": deal_id}}
