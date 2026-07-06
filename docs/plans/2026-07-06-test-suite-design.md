# Test Suite Design — Threshold Project

**Date:** 2026-07-06
**Status:** Approved
**Addresses:** Release Readiness Audit Priority 4 (Testing: 0% → critical-path coverage)

## Context

The audit found zero tests across the project. The LangGraph architecture is
frozen and trusted; the stated risk is that "agentic state machines break
unpredictably without regression tests (especially for resume/interrupt
behavior)." This design covers the first testing pass.

## Decisions (validated with owner)

| Decision | Choice |
| :--- | :--- |
| What "first test" means | Build the automated test suite (not manual verification) |
| Scope | Backend + the two stable frontend components (ReviewQueue, ApproverCard). Frontend pages and E2E deferred — UI is being rewritten in Priorities 2–3 |
| Depth | Prove the critical paths: ~45–55 focused tests, 1–2 days |
| Approach | **Integration-first through the real graph** with a thin unit layer for pure logic. Rejected: unit-first pyramid (2x the code, protects the wrong layer), golden-master snapshots (brittle, can't exercise interrupt/resume) |
| LLM strategy | All LLM calls mocked. Fakes return real `schemas/structured_outputs.py` Pydantic instances so schema drift breaks tests loudly |
| Singleton handling | Add explicit `reset_for_testing()` helpers to `memory/checkpointer.py` and `graphs/builder.py` up front (owner tweak to Section 1) |
| Frontend tooling | Vitest + React Testing Library + jsdom |

## Architecture

```
backend/tests/
  conftest.py              ← shared fixtures
  unit/
    test_approval_rules.py
    test_routing.py
    test_graph_state.py
  graph/
    test_graph_lifecycle.py
    test_interrupt_resume.py
  api/
    test_deal_routes.py
    test_approval_routes.py

frontend/__tests__/
  ReviewQueue.test.tsx
  ApproverCard.test.tsx
```

### Isolation strategy (conftest.py)

1. **LLM mocking.** The 3 LLM nodes (`delay_intelligence`, `document_generator`,
   `communication_planner`) each hold a lazy module-global `_structured_llm`
   built by `_get_structured_llm()`. A `mock_llms` fixture monkeypatches each
   module's global with a fake exposing the same `ainvoke()` interface,
   returning canned instances of the real structured-output schemas. Every
   fake records its calls so tests can assert invocation counts (the
   short-circuit test asserts zero).

2. **Singleton reset.** An autouse fixture calls the new
   `reset_for_testing()` helpers on builder and checkpointer after each test,
   and points `CHECKPOINT_DB_PATH` at a pytest `tmp_path` before the first
   `build_graph()`. Fresh disposable checkpoint DB per test; the real
   `checkpoints/threshold_checkpoints.db` is never touched.

3. **Database.** A `db_session` fixture creates an in-memory SQLite engine,
   runs `create_all`, and yields a session injected via
   `config["configurable"]["db"]` — the same seam `deal_service.py` uses.
   API tests reuse the engine through FastAPI dependency overrides.

Production code is not modified for testability beyond the two additive
`reset_for_testing()` helpers. Async tests run under `pytest-asyncio`
(`asyncio_mode = "auto"`); both libraries are already declared in
`pyproject.toml`.

## Backend test inventory (~35–45 tests)

- **`unit/test_approval_rules.py`** (~10) — one test per rule boundary in the
  deterministic policy table (value/discount thresholds, product type,
  segment), "no rules fire" → empty approvals, result shape (priority
  ordering, confidence 1.0, reasons populated).
- **`unit/test_routing.py`** (~8) — all 4 routing functions as pure functions:
  approval-detection short-circuit both ways; human-review branches approve →
  END, reject → END, request_changes → `document_generator`, `latest_review
  is None` → END; legacy routers' low-confidence / high-risk paths.
- **`unit/test_graph_state.py`** (~6) — reducer contract (`merge_dicts`
  accumulation and None handling, `add` append), Pydantic range/literal
  validation, `new_graph_state` factory shape.
- **`graph/test_graph_lifecycle.py`** (~8) — real compiled graph, mocked LLMs,
  in-memory DB. Short-circuit path (no approvals → END, zero LLM calls, no DB
  rows). Full path to interrupt (pauses at `human_review`,
  `state_snapshot.next == ("human_review",)`, interrupt payload carries
  artifacts/nudges/risk_scores, approvals persisted, momentum updated).
- **`graph/test_interrupt_resume.py`** (~7) — via the service layer
  (`process_deal_via_graph` / `resume_deal_graph`): approve → END; reject →
  END; request_changes → regenerates → pauses again → second resume completes;
  resume of a non-paused deal returns None; **restart survival** — interrupt,
  reset singletons, rebuild graph from the same checkpoint file, resume
  successfully.
- **`api/test_deal_routes.py` + `api/test_approval_routes.py`** (~8) —
  `TestClient` with DB override, graph patched at the service seam: create
  deal 200 + persisted, missing deal 404, review endpoint forwards
  action/feedback/reviewer to `resume_deal_graph`, malformed payload 422.

## Frontend test inventory (~10–12 tests)

Add devDependencies: `vitest`, `@vitejs/plugin-react`, `jsdom`,
`@testing-library/react`, `@testing-library/user-event`,
`@testing-library/jest-dom`. Add `vitest.config.ts` (jsdom, React plugin,
tsconfig path alias) and a `"test": "vitest run"` script.

- **`ApproverCard.test.tsx`** (~4) — renders approver id, department,
  turnaround, fastest format, slowest trigger, review count from props.
- **`ReviewQueue.test.tsx`** (~6–8) — `lib/api` mocked with `vi.mock`: one
  card per action; risk shown as percentage; drafts rendered; Send calls
  `sendApprovalNudge(approval_id, nudge_draft)` and shows "Status: sent";
  Hold calls `holdApprovalNudge(approval_id)` and shows "Status: held";
  empty list renders.

All assertions target text/roles, never styles — the tests survive and
protect the upcoming Tailwind refactor.

## Conventions

- Backend: `cd backend && uv run pytest`. Frontend: `cd frontend && npm test`.
- No test needs `ANTHROPIC_API_KEY`, network, or a running server. Target
  runtime: under ~30s backend.
- Test names state behavior (`test_request_changes_loops_back_to_document_generator`).
- Deal/LLM fixtures are factories (`make_deal(value=..., discount=...)`) so
  scenarios read as one-liners.

## Explicit non-goals (this pass)

Playwright E2E; frontend page tests (`app/**` — being rewritten); tool-layer
unit tests beyond graph coverage; coverage-percentage gates; CI config
(a ~20-line GitHub Actions file once this lands).

## Success criterion

The suite proves the audit's core worry wrong: interrupt → resume works
reliably across all three review actions **and** across a process restart.
