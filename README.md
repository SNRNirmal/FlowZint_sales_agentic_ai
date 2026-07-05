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

## Project layout

- `backend/` — FastAPI service: agents, models, routes, integrations
- `frontend/` — Next.js dashboard, review checkpoint, twin profiles
- `demo/` — seed data + demo script for the live hackathon walkthrough
