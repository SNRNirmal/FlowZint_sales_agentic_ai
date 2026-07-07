# Threshold — Internal Deal-Friction Intelligence Agent

FlowZint AI Hackathon 2026 — Sales Bot Track

Threshold detects, predicts, and unblocks internal approval bottlenecks
(Legal, Finance, Security, Executive sign-off) that stall enterprise
deals after the buyer has already agreed to purchase.

See `Threshold_Implementation_Guide.md` (project root, if copied in)
for full architecture, agent specs, and demo script.

## Quick start (backend)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

## Quick start (frontend)

```bash
cd frontend
npm install
npm run dev
```

## Testing

Backend (pytest — runs the real LangGraph with fake LLMs, no API key needed):

    cd backend
    uv run pytest

Frontend (Vitest + React Testing Library):

    cd frontend
    npm test

No test requires network access, ANTHROPIC_API_KEY, or a running server.
The graph tests prove the human-review interrupt → resume cycle (approve /
reject / request-changes with regeneration) and checkpoint durability across
process restarts, including a negative control (deleting the checkpoint file
loses the pause — it lives nowhere else).

## Project layout

- `backend/` — FastAPI service: agents, models, routes, integrations
- `backend/tests/` — pytest suite: unit (rules, routing, state), graph (lifecycle, interrupt/resume), api (HTTP contracts)
- `frontend/` — Next.js dashboard, review checkpoint, twin profiles
- `frontend/__tests__/` — Vitest component tests (ReviewQueue, ApproverCard)
- `demo/` — seed data + demo script for the live hackathon walkthrough
