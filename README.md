# Threshold — Internal Deal-Friction Intelligence Agent

FlowZint AI Hackathon 2026 — Sales Bot Track

Threshold detects, predicts, and unblocks internal approval bottlenecks
(Legal, Finance, Security, Executive sign-off) that stall enterprise
deals after the buyer has already agreed to purchase.

See `Threshold_Implementation_Guide.md` (project root, if copied in)
for full architecture, agent specs, and demo script.

## Quick start (backend)

Create `backend/.env` with an LLM API key — either provider works:

```env
# Option A: Google Gemini (free tier at https://aistudio.google.com/apikey)
GOOGLE_API_KEY=your-gemini-key

# Option B: Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-...

# Optional overrides (defaults: inferred provider, claude-sonnet-4-6 / gemini-2.5-flash)
# LLM_PROVIDER=gemini
# LLM_MODEL=gemini-2.5-flash-lite
```

The provider is inferred from which key is set (Anthropic wins if both;
set `LLM_PROVIDER` to force). Then:

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

Seed the demo approver twins once (after first startup created the tables):

```bash
uv run python behavioral_twins/seed_data.py
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
