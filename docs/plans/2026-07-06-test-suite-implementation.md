# Threshold Test Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Take the project from 0% test coverage to a passing critical-path suite (~60 tests) proving the LangGraph pipeline, interrupt/resume lifecycle, API routes, and the two stable frontend components work — per the approved design in `docs/plans/2026-07-06-test-suite-design.md`.

**Architecture:** Integration-first: backend tests run the *real* compiled graph with real SQLite checkpointing (temp file per test) and a real in-memory SQLAlchemy DB; only the three `ChatAnthropic` singletons are faked. A thin unit layer covers pure logic (approval rules, routing, reducers). Frontend uses Vitest + React Testing Library with `lib/api` mocked.

**Tech Stack:** pytest 9 + pytest-asyncio (already in `backend/pyproject.toml`), LangGraph 1.2.7 SqliteSaver, SQLAlchemy 2 + StaticPool in-memory SQLite, FastAPI TestClient, Vitest + @testing-library/react + jsdom.

**Working directory note:** Backend commands run from `backend/`, frontend commands from `frontend/`. This project develops directly on `main` (hackathon single-branch workflow); commit after every task.

**Important execution rule:** These tests characterize *existing, working* code. After the designed-to-fail (RED) steps, tests are expected to pass. If a test fails unexpectedly, do NOT bend the test to match — use @superpowers:systematic-debugging to find out which of the two (test or code) is wrong, and report findings before changing production code.

---

## Codebase facts the executor needs (verified 2026-07-06)

- **Graph:** `graphs/builder.py:build_graph()` — singleton `_compiled_graph`. Nodes: `approval_detection → (cond) approval_persistence → behavioral_twin_retrieval → delay_intelligence → document_generator → communication_planner → human_review → (cond) END | document_generator`.
- **Approval rules** (`nodes/approval_detection.py`): Finance `value>=50k or discount>=15` (finance_raj, prio 1); Legal `custom or >=100k` (legal_jane, 2); Security `segment=="enterprise"` (security_amy, 3); Procurement `custom and >=150k` (procurement_li, 4); Compliance `product in (regulated,custom) and enterprise` (compliance_maria, 5); Executive `>=250k` (exec_daniel, 6).
  - A deal with `value=180_000, discount=20, product_type="custom", segment="enterprise"` fires exactly 5 rules (no Executive).
  - A deal with `value=10_000, discount=0, product_type="standard", segment="smb"` fires none → graph short-circuits to END.
- **LLM seam:** `nodes/delay_intelligence.py`, `nodes/document_generator.py`, `nodes/communication_planner.py` each have module global `_structured_llm = None` + `_get_structured_llm()` that returns the global if set. Setting the global to a fake with `async ainvoke(messages)` bypasses ChatAnthropic entirely. Fakes must return `DelayPrediction` / `DraftedArtifact` / `DraftedNudge` instances (`schemas/structured_outputs.py`).
- **DB seam:** nodes get their session from `config["configurable"]["db"]` (`nodes/_node_utils.py:get_db_session`). `services/deal_service.py:process_deal_via_graph(db, deal)` injects it and sets `thread_id = deal.id`. `resume_deal_graph(deal_id, action, feedback, reviewer)` resumes via `Command(resume={...})` and returns `None` if not paused.
- **Momentum:** `approval_persistence` node persists approvals then runs `compute_momentum_score` **via `asyncio.to_thread`** — the test DB engine MUST use `poolclass=StaticPool` and `connect_args={"check_same_thread": False}` or the worker thread gets a different (empty) in-memory DB. It returns `momentum_score` into state AND writes `Deal.momentum_score`.
- **Checkpointer:** `memory/checkpointer.py:get_checkpointer()` reads `CHECKPOINT_DB_PATH` env var *at call time*; singleton `_checkpointer_instance` + `_checkpointer_cm`; `close_checkpointer()` closes and clears both. `thread_config(deal_id)` builds `{"configurable": {"thread_id": deal_id}}`.
- **Import-time env:** `config.py` reads env at import (`load_dotenv()` does NOT override already-set env vars). `db/database.py` creates its engine from `settings.DATABASE_URL` at import. Therefore conftest must set env vars at the very top, before any project import.
- **Interrupt inspection:** after an interrupted run, `graph.get_state(config)` returns a snapshot with `snapshot.next == ("human_review",)` and the payload at `snapshot.tasks[0].interrupts[0].value` (keys: `review_id, deal_id, customer_name, momentum_score, approvals, generated_documents, draft_communications, risk_scores, behavioral_twin_summaries, timestamp`).
- **Graph return type:** `ainvoke` may return a `GraphState` or a plain dict of channel values depending on LangGraph internals — conftest provides `as_state()` to normalize; never assert on the raw return type.
- **Routes:** `main.py` builds `app`; lifespan (init_db + build_graph) only runs if TestClient is used as a context manager — instantiate `TestClient(app)` WITHOUT `with` so it doesn't. `routes/approvals.py` imports `resume_deal_graph` and `send_slack_message` into its own namespace → patch `routes.approvals.<name>`. Same for `routes.webhooks.process_deal_via_graph`.
- **Frontend:** `components/ReviewQueue.tsx` imports `../lib/api` (`sendApprovalNudge(approvalId, nudgeText)`, `holdApprovalNudge(approvalId)`); tsconfig alias `@/* → ./*`. `components/ApproverCard.tsx` is pure props. No test tooling exists yet.

---

### Task 1: pytest configuration + sanity test

**Files:**
- Modify: `backend/pyproject.toml` (append config block)
- Create: `backend/tests/test_sanity.py`

**Step 1: Add pytest config to `backend/pyproject.toml`**

Append at the end of the file:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]` makes `from graphs.builder import ...` resolve when pytest runs from `backend/`. `asyncio_mode = "auto"` lets plain `async def test_*` functions run without decorators.

**Step 2: Write the sanity test**

Create `backend/tests/test_sanity.py`:

```python
"""Proves the test harness can import the project and see its deps."""


def test_project_imports():
    from graphs.builder import build_graph  # noqa: F401
    from schemas.graph_state import GraphState  # noqa: F401
    from services.deal_service import process_deal_via_graph  # noqa: F401


async def test_async_mode_works():
    assert True
```

**Step 3: Run it**

Run: `cd backend; uv sync; uv run pytest -v`
Expected: `2 passed`. (If `uv sync` changes the lockfile because pytest wasn't locked yet, that's expected — include `uv.lock` in the commit.)

**Step 4: Commit**

```bash
git add backend/pyproject.toml backend/tests/test_sanity.py backend/uv.lock
git commit -m "test: add pytest configuration and sanity test"
```

---

### Task 2: `reset_for_testing()` helpers (TDD)

**Files:**
- Create: `backend/tests/unit/test_reset_helpers.py`
- Modify: `backend/graphs/builder.py` (append function)
- Modify: `backend/memory/checkpointer.py` (append function)

**Step 1: Write the failing tests**

Create `backend/tests/unit/test_reset_helpers.py`:

```python
"""The test-isolation contract: singletons must be resettable so every
test can get a fresh compiled graph and a fresh checkpoint DB."""

import pytest

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
    yield
    builder_module.reset_for_testing()
    checkpointer_module.reset_for_testing()


def test_build_graph_is_singleton_until_reset():
    g1 = builder_module.build_graph()
    assert builder_module.build_graph() is g1

    builder_module.reset_for_testing()
    g2 = builder_module.build_graph()
    assert g2 is not g1


def test_checkpointer_reset_rereads_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "first.db"))
    c1 = checkpointer_module.get_checkpointer()
    assert checkpointer_module.get_checkpointer() is c1
    assert (tmp_path / "first.db").exists()

    checkpointer_module.reset_for_testing()
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "second.db"))
    c2 = checkpointer_module.get_checkpointer()
    assert c2 is not c1
    assert (tmp_path / "second.db").exists()
```

**Step 2: Run to verify they fail**

Run: `cd backend; uv run pytest tests/unit/test_reset_helpers.py -v`
Expected: FAIL — `AttributeError: module 'graphs.builder' has no attribute 'reset_for_testing'`

**Step 3: Implement the helpers**

Append to `backend/graphs/builder.py`:

```python
def reset_for_testing() -> None:
    """Drop the compiled-graph singleton so the next build_graph() call
    recompiles (against whatever checkpointer is then active). Exists for
    the test suite; production never calls it."""
    global _compiled_graph
    _compiled_graph = None
```

Append to `backend/memory/checkpointer.py`:

```python
def reset_for_testing() -> None:
    """Close and clear the checkpointer singleton so the next
    get_checkpointer() call re-reads CHECKPOINT_DB_PATH. Exists for the
    test suite; production uses close_checkpointer() at shutdown."""
    close_checkpointer()
```

**Step 4: Run to verify they pass**

Run: `cd backend; uv run pytest tests/unit/test_reset_helpers.py -v`
Expected: `2 passed`

**Step 5: Commit**

```bash
git add backend/graphs/builder.py backend/memory/checkpointer.py backend/tests/unit/test_reset_helpers.py
git commit -m "test: add reset_for_testing helpers for graph and checkpointer singletons"
```

---

### Task 3: Shared fixtures (`conftest.py`)

**Files:**
- Create: `backend/tests/conftest.py`

**Step 1: Write conftest**

Create `backend/tests/conftest.py`:

```python
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
def fresh_graph_and_checkpointer(tmp_path, monkeypatch):
    """Fresh compiled graph + disposable checkpoint DB per test."""
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "checkpoints.db"))
    builder_module.reset_for_testing()
    checkpointer_module.reset_for_testing()
    yield
    builder_module.reset_for_testing()
    checkpointer_module.reset_for_testing()


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
```

**Step 2: Verify nothing broke**

Run: `cd backend; uv run pytest -v`
Expected: `4 passed` (sanity + reset tests still green with autouse fixtures now active)

**Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add shared fixtures (fake LLMs, singleton isolation, in-memory DB)"
```

---

### Task 4: Approval rules unit tests

**Files:**
- Create: `backend/tests/unit/test_approval_rules.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_approval_rules.py`:

```python
"""Approval detection is company policy encoded as rules — these tests
pin every rule boundary so a rule change is always a conscious act."""

from nodes.approval_detection import (
    _needs_compliance,
    _needs_executive,
    _needs_finance,
    _needs_legal,
    _needs_procurement,
    _needs_security,
    approval_detection_node,
)
from schemas.graph_state import GraphState
from tests.conftest import make_deal, make_quiet_deal


# ---- Rule boundaries ------------------------------------------------------

def test_finance_fires_at_50k_value_boundary():
    assert _needs_finance(make_quiet_deal(value=50_000)) is True
    assert _needs_finance(make_quiet_deal(value=49_999.99)) is False


def test_finance_fires_at_15_percent_discount_boundary():
    assert _needs_finance(make_quiet_deal(discount_percent=15)) is True
    assert _needs_finance(make_quiet_deal(discount_percent=14.9)) is False


def test_legal_fires_on_custom_product_or_100k():
    assert _needs_legal(make_quiet_deal(product_type="custom")) is True
    assert _needs_legal(make_quiet_deal(value=100_000)) is True
    assert _needs_legal(make_quiet_deal(value=99_999, product_type="standard")) is False


def test_security_fires_only_for_enterprise_segment():
    assert _needs_security(make_quiet_deal(customer_segment="enterprise")) is True
    assert _needs_security(make_quiet_deal(customer_segment="smb")) is False


def test_procurement_needs_custom_AND_150k():
    assert _needs_procurement(make_quiet_deal(product_type="custom", value=150_000)) is True
    assert _needs_procurement(make_quiet_deal(product_type="custom", value=149_999)) is False
    assert _needs_procurement(make_quiet_deal(product_type="standard", value=200_000)) is False


def test_compliance_needs_regulated_or_custom_enterprise():
    assert _needs_compliance(make_quiet_deal(product_type="regulated", customer_segment="enterprise")) is True
    assert _needs_compliance(make_quiet_deal(product_type="custom", customer_segment="enterprise")) is True
    assert _needs_compliance(make_quiet_deal(product_type="custom", customer_segment="smb")) is False
    assert _needs_compliance(make_quiet_deal(product_type="standard", customer_segment="enterprise")) is False


def test_executive_fires_at_250k():
    assert _needs_executive(make_quiet_deal(value=250_000)) is True
    assert _needs_executive(make_quiet_deal(value=249_999)) is False


# ---- Node behavior --------------------------------------------------------

async def test_node_detects_five_departments_for_big_custom_enterprise_deal():
    state = GraphState(deal=make_deal())  # 180k, 20%, custom, enterprise
    update = await approval_detection_node(state)

    departments = [a.department for a in update["approvals"]]
    assert departments == ["Finance", "Legal", "Security", "Procurement", "Compliance"]
    assert all(a.status == "pending" for a in update["approvals"])


async def test_node_detects_all_six_for_quarter_million_deal():
    state = GraphState(deal=make_deal(value=300_000))
    update = await approval_detection_node(state)
    assert [a.department for a in update["approvals"]][-1] == "Executive"
    assert len(update["approvals"]) == 6


async def test_node_returns_empty_for_quiet_deal():
    state = GraphState(deal=make_quiet_deal())
    update = await approval_detection_node(state)
    assert update["approvals"] == []
    assert update["agent_outputs"]["approval_detection"]["total_detected"] == 0


async def test_node_queues_one_twin_retrieval_task_per_approval():
    state = GraphState(deal=make_deal())
    update = await approval_detection_node(state)
    assert update["pending_tasks"] == [
        f"retrieve_twin:{a.approver_id}" for a in update["approvals"]
    ]
```

Note the import `from tests.conftest import make_deal, make_quiet_deal` — factories are plain functions, imported directly (they are not fixtures).

**Step 2: Run**

Run: `cd backend; uv run pytest tests/unit/test_approval_rules.py -v`
Expected: `11 passed`

**Step 3: Commit**

```bash
git add backend/tests/unit/test_approval_rules.py
git commit -m "test: pin approval rule boundaries and detection node contract"
```

---

### Task 5: Routing unit tests

**Files:**
- Create: `backend/tests/unit/test_routing.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_routing.py`:

```python
"""Routing functions are pure GraphState -> str decisions. These tests
pin every branch, especially the human-review decision fan-out."""

from langgraph.graph import END

from graphs.routing import (
    route_after_approval_detection,
    route_after_delay_intelligence,
    route_after_human_review,
    route_after_twin_retrieval,
)
from schemas.graph_state import (
    ApprovalStatus,
    BehavioralTwinSnapshot,
    GraphState,
    HumanReviewDecision,
    RiskScore,
)
from tests.conftest import make_deal


def _state(**kwargs) -> GraphState:
    return GraphState(deal=make_deal(), **kwargs)


def _approval() -> ApprovalStatus:
    return ApprovalStatus(
        approval_id="ap-1", department="Finance", approver_id="finance_raj"
    )


# ---- route_after_approval_detection ----------------------------------------

def test_no_approvals_short_circuits_to_end():
    assert route_after_approval_detection(_state(approvals=[])) == END


def test_approvals_continue_to_persistence():
    assert (
        route_after_approval_detection(_state(approvals=[_approval()]))
        == "approval_persistence"
    )


# ---- route_after_human_review ----------------------------------------------

def test_approve_ends_pipeline():
    state = _state(latest_review=HumanReviewDecision(action="approve"))
    assert route_after_human_review(state) == END


def test_reject_ends_pipeline():
    state = _state(latest_review=HumanReviewDecision(action="reject"))
    assert route_after_human_review(state) == END


def test_request_changes_loops_back_to_document_generator():
    state = _state(latest_review=HumanReviewDecision(action="request_changes"))
    assert route_after_human_review(state) == "document_generator"


def test_missing_review_defaults_to_end():
    assert route_after_human_review(_state(latest_review=None)) == END


# ---- legacy always-continue routers (kept for future gate insertion) -------

def test_twin_retrieval_always_continues_even_with_low_confidence():
    twin = BehavioralTwinSnapshot(
        approver_id="finance_raj",
        department="Finance",
        avg_turnaround_days=3.0,
        fastest_responding_format="one-pager",
        slowest_trigger="missing context",
        confidence=0.1,
    )
    state = _state(behavioral_twins={"finance_raj": twin})
    assert route_after_twin_retrieval(state) == "delay_intelligence"


def test_delay_intelligence_always_continues_even_when_high_risk():
    risk = RiskScore(
        approver_id="finance_raj",
        delay_probability=0.95,
        expected_delay_days=9.0,
        root_cause="chronic overload",
        confidence=0.9,
    )
    state = _state(risk_scores={"finance_raj": risk})
    assert route_after_delay_intelligence(state) == "document_generator"
```

**Step 2: Run**

Run: `cd backend; uv run pytest tests/unit/test_routing.py -v`
Expected: `8 passed`

**Step 3: Commit**

```bash
git add backend/tests/unit/test_routing.py
git commit -m "test: pin all routing branches including human-review fan-out"
```

---

### Task 6: GraphState / reducer unit tests

**Files:**
- Create: `backend/tests/unit/test_graph_state.py`

**Step 1: Write the tests**

Create `backend/tests/unit/test_graph_state.py`:

```python
"""The reducer contract every node depends on: dict fields merge,
list fields append, validation rejects malformed node output."""

import pytest
from pydantic import ValidationError

from schemas.graph_state import (
    ApprovalStatus,
    GraphState,
    RiskScore,
    merge_dicts,
    new_graph_state,
)
from tests.conftest import make_deal


def test_merge_dicts_accumulates_and_right_wins():
    assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert merge_dicts({"a": 1}, {"a": 9}) == {"a": 9}


def test_merge_dicts_tolerates_none_operands():
    assert merge_dicts(None, {"a": 1}) == {"a": 1}
    assert merge_dicts({"a": 1}, None) == {"a": 1}
    assert merge_dicts(None, None) == {}


def test_risk_score_probability_must_be_within_unit_interval():
    with pytest.raises(ValidationError):
        RiskScore(
            approver_id="x",
            delay_probability=1.5,
            expected_delay_days=1.0,
            root_cause="r",
            confidence=0.5,
        )


def test_approval_status_rejects_unknown_status_literal():
    with pytest.raises(ValidationError):
        ApprovalStatus(
            approval_id="ap-1",
            department="Finance",
            approver_id="finance_raj",
            status="bogus",
        )


def test_new_graph_state_seeds_task_queue_and_audit_log():
    state = new_graph_state(make_deal(deal_id="deal-42"))
    assert state.pending_tasks == ["process_deal:deal-42"]
    assert state.audit_log[0]["event"] == "graph_started"
    assert state.momentum_score == 100


def test_graph_state_defaults_are_empty_not_shared():
    a, b = new_graph_state(make_deal()), new_graph_state(make_deal())
    a.artifacts["x"] = "draft"
    assert b.artifacts == {}
```

**Step 2: Run**

Run: `cd backend; uv run pytest tests/unit/test_graph_state.py -v`
Expected: `6 passed`

**Step 3: Commit**

```bash
git add backend/tests/unit/test_graph_state.py
git commit -m "test: pin GraphState reducer contract and validation rules"
```

---

### Task 6.5: Production fixes required before graph tests (user-approved 2026-07-07)

> Added after Task 3's code-quality review empirically found two pre-existing
> production bugs that block Tasks 7–8 and break/flake production itself.
> The user explicitly approved changing production code for both.

**Finding 1 (deterministic blocker):** with `langgraph==1.2.7` +
`langgraph-checkpoint-sqlite==3.1.0`, the sync `SqliteSaver` raises
`NotImplementedError: The SqliteSaver does not support async methods` on the
first `graph.ainvoke()` — `POST /webhooks/crm` cannot complete a run.

**Finding 2 (~50% flaky):** nodes fan out `asyncio.to_thread` calls
concurrently over the single injected DB session. `behavioral_twin_retrieval`
masks collisions via tenacity retries; `delay_intelligence`'s cold-start
`get_department_pattern` call has no retry and sits outside the per-approver
try, silently dropping approvers (4-of-5 risk scores observed).

**Finding 3 (hygiene):** `from tests.conftest import ...` double-imports the
conftest (namespace package). Fix by adding `__init__.py` files to
`tests/`, `tests/unit/`, `tests/graph/`, `tests/api/`.

**Proven recipe (validated empirically in-session):** construct via
`conn = await aiosqlite.connect(path)`, `saver = AsyncSqliteSaver(conn)`,
`await saver.setup()` (file exists durably right after setup). Construction
and close are async-only: `await conn.close()` releases the Windows file
handle (unlink succeeds); an unawaited `conn.close()` is a no-op coroutine
that leaks aiosqlite's background thread. Do NOT lazily construct from sync
code while a loop runs. **Sync `graph.get_state()` raises
`InvalidStateError` with AsyncSqliteSaver when called from the main/loop
thread — every call site must become `await graph.aget_state(...)`.**

**Files:**
- Modify: `backend/memory/checkpointer.py` — add `async def ainit_checkpointer()` (aiosqlite connect + AsyncSqliteSaver + setup, assigns singleton) and `async def aclose_checkpointer()` (awaited close + clear); `get_checkpointer()` stays the sync fast-path accessor for the pre-initialized singleton and raises a clear error if never initialized; keep `CHECKPOINT_DB_PATH` read at init and parent-dir mkdir.
- Modify: `backend/main.py` lifespan — `await ainit_checkpointer()` before `build_graph()`; `await aclose_checkpointer()` on shutdown.
- Modify: `backend/services/deal_service.py:127` — `graph.get_state(config)` → `await graph.aget_state(config)` (breaks outright post-swap otherwise).
- Modify: `backend/tests/conftest.py` — `fresh_graph_and_checkpointer` becomes an async autouse fixture: awaits `ainit_checkpointer()` after setting `CHECKPOINT_DB_PATH`, awaits `aclose_checkpointer()` + builder reset on teardown.
- Modify: `backend/tests/unit/test_reset_helpers.py` — rewrite the two tests against the new async init/close API (same contracts: singleton until reset; env re-read after reset; file created eagerly; unlink proves handle release).
- Modify: `backend/nodes/delay_intelligence.py` (build twin contexts sequentially over the shared session before gathering the concurrent LLM calls; keep LLM concurrency)
- Modify: `backend/nodes/behavioral_twin_retrieval.py` (fetch twins sequentially over the shared session — local SQLite reads gain nothing from `gather` and the retries were masking real collisions)
- Create: `backend/tests/graph/test_async_checkpointer.py` (RED first: quiet-deal `graph.ainvoke` smoke test that currently fails with NotImplementedError; GREEN after the swap)
- Create: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/graph/__init__.py`, `backend/tests/api/__init__.py` (empty)

> **Amendment to Tasks 7 and 8 below (post-swap API):** every
> `graph.get_state(config)` in their code blocks must be
> `await graph.aget_state(config)`, and `_assert_not_paused` becomes
> `async def` (awaited at call sites). The dispatching controller hands
> implementers the amended code.

**Verification:**
- Existing suite stays green (reset tests still prove file-handle release via `unlink()` on Windows).
- New smoke test passes.
- Race fix proven by running the full-deal pipeline scenario 10 consecutive times with all-5-approver assertions (was ~50% flaky before).

**Commit:** `fix: async checkpointer and race-safe node DB reads (unblocks graph tests)`

---

### Task 7: Graph lifecycle integration tests

**Files:**
- Create: `backend/tests/graph/test_graph_lifecycle.py`

**Step 1: Write the tests**

Create `backend/tests/graph/test_graph_lifecycle.py`:

```python
"""Runs the REAL compiled graph (real checkpointer on tmp_path, real
in-memory DB, fake LLMs) through its two macro paths: short-circuit
and full-run-to-interrupt."""

import graphs.builder as builder_module
from models.approval import Approval
from models.deal import Deal
from schemas.graph_state import new_graph_state
from tests.conftest import as_state, graph_config, make_deal, make_quiet_deal

FIVE_APPROVERS = {
    "finance_raj",
    "legal_jane",
    "security_amy",
    "procurement_li",
    "compliance_maria",
}


def _persist_orm_deal(db_session, deal_info) -> Deal:
    orm = Deal(
        id=deal_info.deal_id,
        customer_name=deal_info.customer_name,
        value=deal_info.value,
        discount_percent=deal_info.discount_percent,
        product_type=deal_info.product_type,
        customer_segment=deal_info.customer_segment,
        stage=deal_info.stage,
    )
    db_session.add(orm)
    db_session.commit()
    db_session.refresh(orm)
    return orm


# ---- Short-circuit path -----------------------------------------------------

async def test_quiet_deal_short_circuits_to_end(db_session, mock_llms):
    deal = make_quiet_deal()
    graph = builder_module.build_graph()
    config = graph_config(deal.deal_id, db_session)

    result = await graph.ainvoke(new_graph_state(deal), config=config)
    state = as_state(result)

    assert state.approvals == []
    snapshot = graph.get_state(config)
    assert snapshot.next == ()  # ran to END — not paused


async def test_quiet_deal_never_touches_llms_or_db(db_session, mock_llms):
    deal = make_quiet_deal()
    graph = builder_module.build_graph()
    await graph.ainvoke(new_graph_state(deal), config=graph_config(deal.deal_id, db_session))

    assert mock_llms["delay"].calls == []
    assert mock_llms["docs"].calls == []
    assert mock_llms["nudges"].calls == []
    assert db_session.query(Approval).count() == 0


# ---- Full path to interrupt -------------------------------------------------

async def test_big_deal_pauses_at_human_review(db_session):
    deal = make_deal(deal_id="deal-big")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-big", db_session)

    await graph.ainvoke(new_graph_state(deal), config=config)

    snapshot = graph.get_state(config)
    assert snapshot.next == ("human_review",)


async def test_interrupt_payload_carries_everything_the_reviewer_needs(db_session):
    deal = make_deal(deal_id="deal-payload")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-payload", db_session)

    await graph.ainvoke(new_graph_state(deal), config=config)

    payload = graph.get_state(config).tasks[0].interrupts[0].value
    assert payload["deal_id"] == "deal-payload"
    assert set(payload["generated_documents"]) == FIVE_APPROVERS
    assert set(payload["draft_communications"]) == FIVE_APPROVERS
    assert set(payload["risk_scores"]) == FIVE_APPROVERS
    assert {a["approver_id"] for a in payload["approvals"]} == FIVE_APPROVERS


async def test_big_deal_persists_approvals_and_momentum(db_session):
    deal = make_deal(deal_id="deal-momentum")
    orm = _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    config = graph_config("deal-momentum", db_session)

    result = await graph.ainvoke(new_graph_state(deal), config=config)
    state = as_state(result)

    rows = db_session.query(Approval).filter_by(deal_id="deal-momentum").all()
    assert {r.approver_id for r in rows} == FIVE_APPROVERS
    assert all(r.status == "pending" for r in rows)

    db_session.refresh(orm)
    assert orm.momentum_score < 100          # 5 pending approvals deduct points
    assert state.momentum_score == orm.momentum_score  # state and DB in sync


async def test_each_llm_called_once_per_approver(db_session, mock_llms):
    deal = make_deal(deal_id="deal-calls")
    _persist_orm_deal(db_session, deal)
    graph = builder_module.build_graph()
    await graph.ainvoke(new_graph_state(deal), config=graph_config("deal-calls", db_session))

    assert len(mock_llms["delay"].calls) == 5
    assert len(mock_llms["docs"].calls) == 5
    assert len(mock_llms["nudges"].calls) == 5
```

**Step 2: Run**

Run: `cd backend; uv run pytest tests/graph/test_graph_lifecycle.py -v`
Expected: `6 passed`. If `snapshot.tasks[0].interrupts` raises IndexError, inspect `graph.get_state(config)` in a debugger before changing anything — the LangGraph 1.2.7 interrupt surface is `snapshot.tasks[n].interrupts`.

**Step 3: Commit**

```bash
git add backend/tests/graph/test_graph_lifecycle.py
git commit -m "test: graph lifecycle — short-circuit and run-to-interrupt paths"
```

---

### Task 8: Interrupt/resume tests (the crown jewels)

**Files:**
- Create: `backend/tests/graph/test_interrupt_resume.py`

**Step 1: Write the tests**

Create `backend/tests/graph/test_interrupt_resume.py`:

```python
"""Interrupt/resume through the PRODUCTION service layer — the exact
code path the API routes use. This is the audit's core worry:
'resume/interrupt behavior breaks unpredictably without tests'."""

import graphs.builder as builder_module
import memory.checkpointer as checkpointer_module
from memory.checkpointer import thread_config
from models.deal import Deal
from services.deal_service import process_deal_via_graph, resume_deal_graph
from tests.conftest import as_state


async def _run_to_pause(db_session, deal_id: str) -> Deal:
    """Create a 5-approval deal and run the pipeline until it pauses
    at human_review, exactly like POST /webhooks/crm does."""
    orm = Deal(
        id=deal_id,
        customer_name="Acme Corp",
        value=180_000,
        discount_percent=20,
        product_type="custom",
        customer_segment="enterprise",
    )
    db_session.add(orm)
    db_session.commit()
    db_session.refresh(orm)
    await process_deal_via_graph(db_session, orm)
    return orm


def _assert_not_paused(deal_id: str):
    snapshot = builder_module.build_graph().get_state(thread_config(deal_id))
    assert snapshot.next == ()


async def test_resume_with_approve_completes_pipeline(db_session):
    await _run_to_pause(db_session, "deal-approve")

    final = await resume_deal_graph("deal-approve", "approve", "LGTM", "sathya")

    state = as_state(final)
    assert state.latest_review is not None
    assert state.latest_review.action == "approve"
    assert state.latest_review.reviewed_by == "sathya"
    _assert_not_paused("deal-approve")


async def test_resume_with_reject_aborts_pipeline(db_session):
    await _run_to_pause(db_session, "deal-reject")

    final = await resume_deal_graph("deal-reject", "reject", "Numbers are wrong")

    assert as_state(final).latest_review.action == "reject"
    _assert_not_paused("deal-reject")


async def test_request_changes_regenerates_and_pauses_again(db_session, mock_llms):
    await _run_to_pause(db_session, "deal-loop")
    drafts_before = len(mock_llms["docs"].calls)  # 5

    await resume_deal_graph("deal-loop", "request_changes", "Make it shorter")

    # Looped back through document_generator → drafted 5 more artifacts…
    assert len(mock_llms["docs"].calls) == drafts_before + 5
    # …and is now paused at human_review for a SECOND review.
    snapshot = builder_module.build_graph().get_state(thread_config("deal-loop"))
    assert snapshot.next == ("human_review",)

    # Second review approves — pipeline completes.
    final = await resume_deal_graph("deal-loop", "approve")
    assert as_state(final).latest_review.action == "approve"
    _assert_not_paused("deal-loop")


async def test_resume_of_never_paused_deal_returns_none(db_session):
    result = await resume_deal_graph("deal-that-never-ran", "approve")
    assert result is None


async def test_paused_review_survives_process_restart(db_session):
    """Interrupt, then simulate a full process restart (drop the compiled
    graph AND the checkpointer connection), then resume from the same
    checkpoint file. Proves paused reviews are durable."""
    await _run_to_pause(db_session, "deal-restart")

    # Simulate restart: both singletons die; CHECKPOINT_DB_PATH still
    # points at the same tmp file (set by the autouse fixture).
    builder_module.reset_for_testing()
    checkpointer_module.reset_for_testing()

    # Fresh process would rebuild the graph on demand and find the
    # checkpoint on disk.
    snapshot = builder_module.build_graph().get_state(thread_config("deal-restart"))
    assert snapshot.next == ("human_review",)

    final = await resume_deal_graph("deal-restart", "approve", reviewer="post-restart")
    assert as_state(final).latest_review.action == "approve"
    _assert_not_paused("deal-restart")
```

**Step 2: Run**

Run: `cd backend; uv run pytest tests/graph/test_interrupt_resume.py -v`
Expected: `5 passed`. The restart test is the most likely to surface real bugs — if it fails, that is a genuine finding about checkpoint durability, not a test problem. Investigate with @superpowers:systematic-debugging and report before changing production code.

**Step 3: Commit**

```bash
git add backend/tests/graph/test_interrupt_resume.py
git commit -m "test: interrupt/resume lifecycle incl. request-changes loop and restart survival"
```

---

### Task 9: API route tests

**Files:**
- Create: `backend/tests/api/test_deal_routes.py`
- Create: `backend/tests/api/test_approval_routes.py`

**Step 1: Write the deal route tests**

Create `backend/tests/api/test_deal_routes.py`:

```python
"""HTTP contract tests for /deals and /webhooks/crm. The graph is
patched at the service seam — routes are tested as HTTP adapters."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from db.database import get_db
from main import app
from models.approval import Approval
from models.deal import Deal
from schemas.graph_state import ApprovalStatus, RiskScore, new_graph_state
from tests.conftest import make_deal


@pytest.fixture()
def client(db_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # NOTE: no `with` — lifespan (init_db on the real file DB + graph
    # pre-warm) must NOT run in route tests.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_deal(db_session, deal_id="deal-api-1") -> Deal:
    deal = Deal(id=deal_id, customer_name="Acme Corp", value=180_000)
    db_session.add(deal)
    db_session.commit()
    return deal


def test_list_deals_returns_seeded_rows(client, db_session):
    _seed_deal(db_session, "deal-a")
    _seed_deal(db_session, "deal-b")

    resp = client.get("/deals/")

    assert resp.status_code == 200
    assert {d["id"] for d in resp.json()} == {"deal-a", "deal-b"}


def test_get_deal_returns_deal_with_its_approvals(client, db_session):
    _seed_deal(db_session, "deal-a")
    db_session.add(
        Approval(id="ap-1", deal_id="deal-a", department="Finance", approver_id="finance_raj")
    )
    db_session.commit()

    resp = client.get("/deals/deal-a")

    assert resp.status_code == 200
    body = resp.json()
    assert body["deal"]["id"] == "deal-a"
    assert body["approvals"][0]["id"] == "ap-1"


def test_get_missing_deal_is_404(client):
    assert client.get("/deals/nope").status_code == 404


def test_crm_webhook_persists_deal_and_maps_drafted_actions(client, db_session, monkeypatch):
    async def fake_process(db, deal):
        state = new_graph_state(make_deal(deal_id=deal.id))
        state.approvals = [
            ApprovalStatus(approval_id="ap-9", department="Finance", approver_id="finance_raj")
        ]
        state.risk_scores = {
            "finance_raj": RiskScore(
                approver_id="finance_raj",
                delay_probability=0.42,
                expected_delay_days=3.5,
                root_cause="test",
                confidence=0.8,
            )
        }
        state.artifacts = {"finance_raj": "artifact text"}
        state.nudges = {"finance_raj": "nudge text"}
        return state

    monkeypatch.setattr("routes.webhooks.process_deal_via_graph", fake_process)

    resp = client.post("/webhooks/crm", json={"customer_name": "Acme Corp", "value": 180000})

    assert resp.status_code == 200
    body = resp.json()
    assert db_session.query(Deal).filter_by(id=body["deal_id"]).count() == 1
    action = body["drafted_actions"][0]
    assert action["approval_id"] == "ap-9"
    assert action["artifact_draft"] == "artifact text"
    assert action["nudge_draft"] == "nudge text"
    assert action["review_status"] == "awaiting_human_review"
```

**Step 2: Write the approval route tests**

Create `backend/tests/api/test_approval_routes.py`:

```python
"""HTTP contract tests for the three human-review checkpoint endpoints.
resume_deal_graph, send_slack_message, and the learning/momentum tools
are patched IN THE ROUTE MODULE'S NAMESPACE (routes.approvals imports
them by name)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from db.database import get_db
from main import app
from models.approval import Approval
from models.deal import Deal


@pytest.fixture()
def client(db_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_approval(db_session):
    db_session.add(Deal(id="deal-1", customer_name="Acme Corp", value=180_000))
    db_session.add(
        Approval(id="ap-1", deal_id="deal-1", department="Finance", approver_id="finance_raj")
    )
    db_session.commit()
    return "ap-1"


@pytest.fixture()
def resume_recorder(monkeypatch):
    calls = {}

    async def fake_resume(deal_id, action, feedback="", reviewer="system"):
        calls.update(deal_id=deal_id, action=action)
        return None

    monkeypatch.setattr("routes.approvals.resume_deal_graph", fake_resume)
    return calls


@pytest.fixture()
def slack_recorder(monkeypatch):
    calls = {}

    def fake_slack(channel, text):
        calls.update(channel=channel, text=text)

    monkeypatch.setattr("routes.approvals.send_slack_message", fake_slack)
    return calls


def test_send_marks_sent_and_resumes_with_approve(
    client, db_session, seeded_approval, resume_recorder, slack_recorder
):
    resp = client.post(f"/approvals/{seeded_approval}/send", params={"nudge_text": "Please review"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "sent", "approval_id": "ap-1"}
    db_session.expire_all()
    assert db_session.get(Approval, "ap-1").status == "sent"
    assert slack_recorder == {"channel": "#finance-approvals", "text": "Please review"}
    assert resume_recorder == {"deal_id": "deal-1", "action": "approve"}


def test_send_missing_approval_is_404(client, resume_recorder, slack_recorder):
    resp = client.post("/approvals/nope/send", params={"nudge_text": "x"})
    assert resp.status_code == 404
    assert resume_recorder == {}          # graph untouched
    assert slack_recorder == {}           # nothing sent


def test_send_without_nudge_text_is_422(client, seeded_approval, resume_recorder, slack_recorder):
    assert client.post(f"/approvals/{seeded_approval}/send").status_code == 422


def test_hold_resumes_with_request_changes_and_sends_nothing(
    client, db_session, seeded_approval, resume_recorder, slack_recorder
):
    resp = client.post(f"/approvals/{seeded_approval}/hold")

    assert resp.status_code == 200
    assert resp.json() == {"status": "held", "approval_id": "ap-1"}
    db_session.expire_all()
    assert db_session.get(Approval, "ap-1").status == "pending"  # unchanged
    assert slack_recorder == {}
    assert resume_recorder == {"deal_id": "deal-1", "action": "request_changes"}


def test_resolve_records_outcome_and_recomputes_momentum(
    client, db_session, seeded_approval, monkeypatch
):
    outcome_calls = {}

    def fake_record(db, **kwargs):
        outcome_calls.update(kwargs)

    monkeypatch.setattr("routes.approvals.record_outcome_sync", fake_record)
    monkeypatch.setattr("routes.approvals.compute_momentum_score", lambda db, deal_id: 85)

    resp = client.post(
        f"/approvals/{seeded_approval}/resolve",
        params={"actual_delay_days": 2.5, "artifact_format_used": "one-pager"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "approved", "new_momentum_score": 85}
    db_session.expire_all()
    row = db_session.get(Approval, "ap-1")
    assert row.status == "approved"
    assert row.actual_delay_days == 2.5
    assert outcome_calls["approver_id"] == "finance_raj"


def test_resolve_missing_required_params_is_422(client, seeded_approval):
    assert client.post(f"/approvals/{seeded_approval}/resolve").status_code == 422
```

**Step 3: Run**

Run: `cd backend; uv run pytest tests/api -v`
Expected: `10 passed`

**Step 4: Run the whole backend suite**

Run: `cd backend; uv run pytest`
Expected: all ~46 tests pass, total runtime well under 60 seconds.

**Step 5: Commit**

```bash
git add backend/tests/api
git commit -m "test: HTTP contract tests for deals, webhook, and approval checkpoint routes"
```

---

### Task 10: Frontend test tooling

**Files:**
- Modify: `frontend/package.json` (deps via npm, plus scripts)
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/__tests__/smoke.test.tsx`

**Step 1: Install dev dependencies**

Run from `frontend/`:

```bash
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/jest-dom @testing-library/user-event
```

**Step 2: Add test scripts to `frontend/package.json`**

In the `"scripts"` block add:

```json
"test": "vitest run",
"test:watch": "vitest"
```

**Step 3: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Mirror tsconfig's "@/*": ["./*"] so component imports and vi.mock
    // specifiers resolve to the same module ids.
    alias: { "@": path.resolve(__dirname, ".") },
  },
  test: {
    environment: "jsdom",
    globals: true, // required for @testing-library/react auto-cleanup
    setupFiles: ["./vitest.setup.ts"],
  },
})
```

**Step 4: Create `frontend/vitest.setup.ts`**

```ts
import "@testing-library/jest-dom/vitest"
```

**Step 5: Create `frontend/__tests__/smoke.test.tsx`**

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

describe("test harness", () => {
  it("renders JSX into jsdom", () => {
    render(<div>harness works</div>)
    expect(screen.getByText("harness works")).toBeInTheDocument()
  })
})
```

**Step 6: Run**

Run: `cd frontend; npm test`
Expected: `1 passed`

**Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/__tests__/smoke.test.tsx
git commit -m "test: add Vitest + React Testing Library harness for frontend"
```

---

### Task 11: ApproverCard component tests

**Files:**
- Create: `frontend/__tests__/ApproverCard.test.tsx`

**Step 1: Write the tests**

Create `frontend/__tests__/ApproverCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import ApproverCard from "@/components/ApproverCard"

const twin = {
  approver_id: "finance_raj",
  department: "Finance",
  avg_turnaround_days: 3.2,
  fastest_responding_format: "one-pager",
  slowest_trigger: "missing discount justification",
  total_deals_reviewed: 14,
}

describe("ApproverCard", () => {
  it("shows the approver identity", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText("finance_raj")).toBeInTheDocument()
    expect(screen.getByText("Finance")).toBeInTheDocument()
  })

  it("shows the behavioral statistics", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/3.2 days/)).toBeInTheDocument()
    expect(screen.getByText(/one-pager/)).toBeInTheDocument()
    expect(screen.getByText(/missing discount justification/)).toBeInTheDocument()
  })

  it("shows the sample size behind the twin", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/14 deals reviewed/)).toBeInTheDocument()
  })
})
```

**Step 2: Run**

Run: `cd frontend; npm test`
Expected: `4 passed` (3 new + smoke)

**Step 3: Commit**

```bash
git add frontend/__tests__/ApproverCard.test.tsx
git commit -m "test: ApproverCard renders twin profile from props"
```

---

### Task 12: ReviewQueue component tests

**Files:**
- Create: `frontend/__tests__/ReviewQueue.test.tsx`

**Step 1: Write the tests**

Create `frontend/__tests__/ReviewQueue.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

// The component imports "../lib/api"; both that specifier and this alias
// resolve to the same module id, so this factory intercepts it.
vi.mock("@/lib/api", () => ({
  sendApprovalNudge: vi.fn().mockResolvedValue({}),
  holdApprovalNudge: vi.fn().mockResolvedValue({}),
}))

import { holdApprovalNudge, sendApprovalNudge } from "@/lib/api"
import ReviewQueue from "@/components/ReviewQueue"

const action = {
  approval_id: "ap-1",
  department: "Finance",
  approver_id: "finance_raj",
  artifact_draft: "Draft artifact body",
  nudge_draft: "Please review this deal",
  prediction: { root_cause: "Slow on discount deals", delay_probability: 0.42 },
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("ReviewQueue", () => {
  it("renders one card per action with prediction context", () => {
    render(<ReviewQueue actions={[action, { ...action, approval_id: "ap-2", department: "Legal" }]} />)
    expect(screen.getByText(/Finance — finance_raj/)).toBeInTheDocument()
    expect(screen.getByText(/Legal — finance_raj/)).toBeInTheDocument()
    expect(screen.getAllByText(/delay risk: 42%/)).toHaveLength(2)
  })

  it("renders the drafted artifact and nudge", () => {
    render(<ReviewQueue actions={[action]} />)
    expect(screen.getByText("Draft artifact body")).toBeInTheDocument()
    expect(screen.getByText("Please review this deal")).toBeInTheDocument()
  })

  it("Send calls the API with the nudge draft and shows sent status", async () => {
    const user = userEvent.setup()
    render(<ReviewQueue actions={[action]} />)

    await user.click(screen.getByRole("button", { name: "Send" }))

    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findByText(/Status: sent/)).toBeInTheDocument()
  })

  it("Hold calls the API and shows held status", async () => {
    const user = userEvent.setup()
    render(<ReviewQueue actions={[action]} />)

    await user.click(screen.getByRole("button", { name: "Hold" }))

    expect(holdApprovalNudge).toHaveBeenCalledWith("ap-1")
    expect(await screen.findByText(/Status: held/)).toBeInTheDocument()
    expect(sendApprovalNudge).not.toHaveBeenCalled()
  })

  it("renders nothing gracefully for an empty queue", () => {
    const { container } = render(<ReviewQueue actions={[]} />)
    expect(container.querySelectorAll("button")).toHaveLength(0)
  })
})
```

**Step 2: Run**

Run: `cd frontend; npm test`
Expected: `9 passed` total.

**Step 3: Commit**

```bash
git add frontend/__tests__/ReviewQueue.test.tsx
git commit -m "test: ReviewQueue send/hold behavior with mocked API layer"
```

---

### Task 13: Full verification + document how to run

**Files:**
- Modify: `README.md` (add a Testing section)

**Step 1: Run both suites end-to-end** (@superpowers:verification-before-completion — paste real output, no claims without evidence)

Run: `cd backend; uv run pytest -v`
Expected: ~46 passed, 0 failed, runtime < 60s.

Run: `cd frontend; npm test`
Expected: ~13 passed, 0 failed.

**Step 2: Confirm no stray artifacts**

Run: `git status --short`
Expected: only the README edit below. In particular `backend/checkpoints/threshold_checkpoints.db` and `backend/threshold.db` must NOT appear modified — if they do, a test escaped its sandbox; stop and debug.

**Step 3: Add a Testing section to `README.md`**

Append:

```markdown
## Testing

Backend (pytest — runs the real LangGraph with fake LLMs, no API key needed):

    cd backend
    uv run pytest

Frontend (Vitest + React Testing Library):

    cd frontend
    npm test

No test requires network access, ANTHROPIC_API_KEY, or a running server.
The graph tests prove the human-review interrupt → resume cycle (approve /
reject / request-changes) and checkpoint durability across process restarts.
```

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add testing instructions to README"
```

---

## Definition of done

- [ ] `cd backend; uv run pytest` → all pass, no network, no API key
- [ ] `cd frontend; npm test` → all pass
- [ ] `git status` clean; real `threshold.db` / `checkpoints/` untouched by tests
- [ ] Interrupt/resume proven for approve, reject, request_changes (with loop-back), and post-restart resume
- [ ] All work committed in per-task commits
