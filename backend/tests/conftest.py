"""Shared fixtures for the Threshold backend test suite.

Isolation guarantees provided here:
  1. DATABASE_URL is forced to in-memory BEFORE any project import, so no
     test can ever touch the real threshold.db file.
  2. Every test gets a fresh compiled graph wired to a disposable
     checkpoint DB under tmp_path (autouse fresh_graph_and_checkpointer).
  3. Every test gets fake LLMs (autouse mock_llms) — no test can hit the
     Anthropic API, with or without a key.
"""

import os

# --- Env guards: MUST run before any project import (config.py and
# --- db/database.py read env at import time).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-never-used")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module
import nodes.communication_planner as comm_module
import nodes.delay_intelligence as delay_module
import nodes.document_generator as doc_module
from db.database import Base
from memory.checkpointer import thread_config
from schemas.graph_state import DealInfo, GraphState
from schemas.structured_outputs import DelayPrediction, DraftedArtifact, DraftedNudge

# Register every table on Base.metadata before create_all.
import models.approval  # noqa: F401
import models.behavioral_twin  # noqa: F401
import models.deal  # noqa: F401
import models.learning_log  # noqa: F401


# ---------------------------------------------------------------------------
# Deal factory
# ---------------------------------------------------------------------------

def make_deal(**overrides) -> DealInfo:
    """A big custom enterprise deal that fires 5 approval rules
    (Finance, Legal, Security, Procurement, Compliance — not Executive).
    Override fields to shape other scenarios."""
    defaults = dict(
        deal_id="deal-test-1",
        customer_name="Acme Corp",
        value=180_000.0,
        discount_percent=20.0,
        product_type="custom",
        customer_segment="enterprise",
        stage="verbal_agreement",
    )
    defaults.update(overrides)
    return DealInfo(**defaults)


def make_quiet_deal(**overrides) -> DealInfo:
    """A small SMB deal that fires ZERO approval rules → short-circuit."""
    defaults = dict(
        deal_id="deal-quiet-1",
        customer_name="Tiny LLC",
        value=10_000.0,
        discount_percent=0.0,
        product_type="standard",
        customer_segment="smb",
    )
    defaults.update(overrides)
    return DealInfo(**defaults)


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def graph_config(deal_id: str, db) -> dict:
    """Same shape services/deal_service.py builds for graph.ainvoke()."""
    cfg = thread_config(deal_id)
    cfg["configurable"]["db"] = db
    return cfg


def as_state(result) -> GraphState:
    """Normalize graph.ainvoke()'s return (GraphState or channel-values
    dict, possibly containing dunder keys like __interrupt__)."""
    if isinstance(result, GraphState):
        return result
    if isinstance(result, dict):
        return GraphState.model_validate(
            {k: v for k, v in result.items() if not k.startswith("__")}
        )
    raise TypeError(f"Unexpected graph result type: {type(result)!r}")


# ---------------------------------------------------------------------------
# Fake LLMs
# ---------------------------------------------------------------------------

class FakeStructuredLLM:
    """Stands in for ChatAnthropic(...).with_structured_output(Schema).
    Records every call so tests can assert invocation counts."""

    def __init__(self, make_response):
        self.make_response = make_response
        self.calls: list = []

    async def ainvoke(self, messages, **kwargs):
        self.calls.append(messages)
        return self.make_response()


@pytest.fixture(autouse=True)
def mock_llms(monkeypatch):
    """Replace all three LLM singletons with recording fakes returning
    valid structured-output instances. Autouse: no test can hit the API."""
    fakes = {
        "delay": FakeStructuredLLM(
            lambda: DelayPrediction(
                delay_probability=0.42,
                expected_delay_days=3.5,
                root_cause="Historically slower on high-discount deals",
                confidence=0.8,
            )
        ),
        "docs": FakeStructuredLLM(
            lambda: DraftedArtifact(
                content="Deal summary — one-pager (test draft)",
                format_used="one-pager",
                approver_id="static",
            )
        ),
        "nudges": FakeStructuredLLM(
            lambda: DraftedNudge(
                message="Hi — could you review the attached approval when you have a moment?",
                urgency="normal",
                approver_id="static",
            )
        ),
    }
    monkeypatch.setattr(delay_module, "_structured_llm", fakes["delay"])
    monkeypatch.setattr(doc_module, "_structured_llm", fakes["docs"])
    monkeypatch.setattr(comm_module, "_structured_llm", fakes["nudges"])
    return fakes


# ---------------------------------------------------------------------------
# Singleton isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def fresh_graph_and_checkpointer(tmp_path, monkeypatch):
    """Fresh compiled graph + disposable checkpoint DB per test.

    Async because the AsyncSqliteSaver lifecycle is async-only
    (aiosqlite connect/close must be awaited from a running loop).
    ainit BEFORE the test so build_graph() finds an initialized
    checkpointer; aclose AFTER so the DB file handle is released
    (tmp_path cleanup on Windows fails on open handles)."""
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.db"))
    builder_module.reset_for_testing()
    await checkpointer_module.ainit_checkpointer()
    yield
    builder_module.reset_for_testing()
    await checkpointer_module.aclose_checkpointer()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_engine():
    """In-memory SQLite shared across threads. StaticPool is REQUIRED:
    approval_persistence runs compute_momentum_score via asyncio.to_thread,
    and without a shared connection the worker thread would see an empty DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestSession()
    yield session
    session.close()
