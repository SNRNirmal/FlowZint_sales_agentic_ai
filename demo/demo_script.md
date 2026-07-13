# Threshold — Live Demo Script

## Setup (before judges arrive)

1. `cd backend && uv run uvicorn main:app --reload`
   (needs `backend/.env` with `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY`)
2. `uv run python behavioral_twins/seed_data.py` (seeds the 4 demo approver profiles)
3. `cd frontend && npm run dev` (must be port 3000 — backend CORS allows only that origin)
4. Open `http://localhost:3000` — login is one click ("Enter as Sales Ops"),
   no credentials. Keep `/review`, `/dashboard`, and `/twins` tabs ready.
5. Safety net: the review queue survives an accidental refresh (it mirrors to
   sessionStorage), so a stray F5 mid-demo restores the drafted actions.

## Live walkthrough (~5 minutes)

1. **Open `/twins`** — show the 4 seeded Approver Behavioral Twin profiles.
   Say: *"Threshold already knows how each of our internal approvers
   behaves — this is the moat, it's not generic risk scoring."*

2. **Open `/review`**, pick a scenario, and click "Run Pipeline".
   This fires the mock CRM webhook for Northwind Logistics ($180k, custom
   product, enterprise segment, 18% discount) straight into the
   Orchestrator.

3. **Point out the drafted actions** appearing for Legal, Finance, and
   Security. For each one, read the `root_cause` line out loud — this is
   the Delay Intelligence Agent explaining *why* it expects friction,
   grounded in that specific approver's twin.

4. **Point at the artifact draft** — show it's tailored to that
   approver's `fastest_responding_format` (e.g., the 1-page redline
   summary for Legal, not a generic template).

5. **Point at the Human Review Checkpoint** — click "Send" on one
   action. Say explicitly: *"Nothing reaches a real approver
   unsupervised — this is what makes it enterprise-credible."*

6. **Switch to `/dashboard`** — show the Momentum Score for the deal
   and how it's already shifted after the send action (no manual reload
   needed; the send invalidates the dashboard data).

7. **Close the learning loop** — open the deal from `/deals`, click
   "Record outcome" on the sent approval (e.g., actual delay 2.5 days,
   format "one-pager"). Then flip to `/twins`: that approver's stats and
   "Updated" date just changed. Say: *"This is the Learning Agent —
   Threshold gets sharper with every deal."*

8. **Close on differentiation** — say: *"Clari would report that this
   deal is at risk. Threshold identified exactly which approver, why,
   drafted the fix, and just showed you it learning from the outcome —
   automatically."*

## Backup talking points for Q&A

- "Is the AI sending anything unsupervised?" → No, Human Review
  Checkpoint gates every send.
- "How does the Learning Agent actually update?" → Weighted rolling
  average per approver per artifact type — see
  `behavioral_twins/twin_store.py::update_twin_after_deal`.
- "What's real vs. roadmap?" → Backend agents + Postgres/SQLite +
  LLM calls + mocked Slack/CRM are real and running. Redis, ChromaDB,
  multi-CRM support, and auto-negotiation are labeled roadmap in the
  pitch deck.
- "What does the UI show when the backend has no data for something?" →
  Nothing fabricated: every rendered number comes from a real endpoint
  (audited in `docs/plans/2026-07-12-frontend-design.md`); features whose
  endpoints don't exist yet (execution timeline, analytics, reject) are
  absent, not faked.
