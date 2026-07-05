"""Shared utilities for LangGraph nodes.

approval_detection_node needed no DB access (pure in-memory reasoning
over state.deal). Every node from here on does need one, to call
tools that read/write the database. This is the one place that
decides how a node gets its Session, so every node uses the same
convention instead of each one inventing its own DB-access pattern.

Convention: a node's DB session comes from the graph invocation's
RunnableConfig (config["configurable"]["db"]), set by the service
layer (Module 10) when it calls graph.ainvoke(). If no config/db is
provided — e.g. when a node is unit-tested in isolation — the node
falls back to opening its own SessionLocal(), which it must then
close itself. This keeps every node independently testable (per the
requirement) without needing the full graph + service layer wired up.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from db.database import SessionLocal


def get_db_session(config: RunnableConfig | None) -> tuple[Session, bool]:
    """Returns (session, owns_session).

    owns_session=True means the caller opened this session itself and
    is responsible for closing it (via a try/finally). owns_session=
    False means the session came from the graph's config and belongs
    to the caller of graph.ainvoke() — the node must NOT close it.
    """
    if config is not None:
        configurable = config.get("configurable", {})
        injected_db = configurable.get("db")
        if injected_db is not None:
            return injected_db, False

    return SessionLocal(), True
