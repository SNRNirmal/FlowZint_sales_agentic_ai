# Threshold Frontend — Design (2026-07-12)

Status: **approved** (brainstormed and validated section-by-section with the user).

## Context and goal

The backend is complete and frozen: FastAPI + LangGraph with a human-review
interrupt/resume checkpoint, SQLAlchemy persistence (SQLite by default,
Postgres via `DATABASE_URL`), and an observability layer that is not yet
exposed over HTTP. The frontend must serve exactly this backend.

Governing rule (user directive): **every UI value renders only if a backend
endpoint produces it.** No invented APIs, no mock endpoints, no heuristic or
hardcoded values, no fake momentum/confidence, no placeholder analytics. If
data is unavailable, the feature is omitted and the missing endpoint is named
here — nothing fake ships.

Earlier decisions (approved during brainstorming):

- **Demo-ready reconciliation** of the existing `(app)` UI, not a rebuild.
- **One-click demo login** ("Enter as Sales Ops"), no typed credentials.
- **Review resilience via sessionStorage** mirror (approach A) — chosen
  because `Approval` rows do not persist drafts, so a refresh can never
  restore them from the server.
- **Approved as presented** with zero backend changes; observability pages
  stay blocked.

## Step 1 — Backend API audit

8 HTTP endpoints exist (`main.py` registers deals, approvals, webhooks,
dashboard, plus `/`). No auth. CORS allows `localhost:3000`.

| Endpoint | Method | Request | Response | Status |
|---|---|---|---|---|
| `/` | GET | — | `{status}` | ✅ Ready |
| `/webhooks/crm` | POST | body: `customer_name`*, `value`*, `discount_percent?`, `product_type?`, `customer_segment?`, `stage?` | `{deal_id, momentum_score, drafted_actions[]}`; action = `{approval_id, department, approver_id, prediction{delay_probability, expected_delay_days, root_cause, confidence}, artifact_draft, nudge_draft, review_status}` | ✅ — but drafts/predictions are **not persisted**; this response is their only carrier |
| `/deals/` | GET | — | `Deal[]` | ✅ — no search/filter/sort/pagination params; client-side only |
| `/deals/{deal_id}` | GET | path | `{deal, approvals[]}` | ✅ — approvals have no timestamps and no draft text |
| `/approvals/{id}/send` | POST | query `nudge_text` | `{status:"sent", approval_id}` | ✅ — resumes graph as `approve`; Slack is console-mock unless `SLACK_BOT_TOKEN` |
| `/approvals/{id}/hold` | POST | — | `{status:"held", approval_id}` | 🟡 — resumes as `request_changes` but the route discards regenerated drafts; round-2 content is unreachable |
| `/approvals/{id}/resolve` | POST | query `actual_delay_days`*, `artifact_format_used`*, `delay_reason?` | `{status:"approved", new_momentum_score}` | ✅ — updates twin + `learning_log`, recomputes momentum; the only demonstrable learning loop |
| `/dashboard/summary` | GET | — | `{total_deals, stalled_deals, avg_momentum_score, deals[], approver_profiles[]}` | ✅ — unpaginated arrays, fine at demo scale |

Backend capabilities with **no route** (frozen; named for honesty):

| Capability | Lives in | Missing endpoint |
|---|---|---|
| Per-deal execution timeline | `observability/execution_history.build_execution_timeline` | `GET /observability/deals/{id}/timeline` |
| Aggregated graph metrics | `observability/graph_metrics.compute_aggregated_metrics` | `GET /observability/metrics` |
| Mermaid graph structure | `observability/graph_metrics.generate_mermaid_visualization` | `GET /observability/graph` |
| Reject decision | `services/deal_service.resume_deal_graph(action="reject")` | `POST /approvals/{id}/reject` |
| Reviewer feedback/comments | `resume_deal_graph(feedback=, reviewer=)` | params not exposed by routes |
| Learning history | `learning_log` table (written, never read) | `GET /twins/{approver_id}/learning-log` |
| Twin confidence | in-graph `BehavioralTwinSnapshot.confidence` only; no ORM column | not exposed at rest |
| Pending approvals across deals | per-deal only | derivable by client fan-out; no single endpoint |

Mocks: Slack (console unless token), email (always mock, unused by routes).
Everything else returns genuinely computed/persisted values.

## Step 2 — Architecture

Five real pages; three blocked pages ship as nothing (not scaffolded, not in
the sidebar), each one small read-only route away if the backend unfreezes.

1. **Dashboard** — totals, stalled count, avg + per-deal momentum, recent
   deals from `/dashboard/summary`. Pending-approvals count and approval
   statistics from the client fan-out (`/deals/` → `/deals/{id}`, cached per
   deal; real rows, N+1 acknowledged at demo scale). AI-recommendations
   widget omitted (nothing persists them).
2. **Deals** — real list; search/filter/sort/pagination client-side, labeled
   as such in code.
3. **Deal Details** — metadata, momentum, approvals with `predicted_delay_days`
   and status; twin summary via client-side join on `approver_id` against
   `approver_profiles`; **Resolve-outcome dialog** (`POST /approvals/{id}/resolve`)
   closing the learning loop. Documents and at-rest AI analysis omitted; a
   live webhook run in this browser session is shown from the sessionStorage
   mirror, badged "from live run".
4. **Human Review** — two truthful layers. *Live:* fire `/webhooks/crm`,
   render `drafted_actions` (root_cause, real risk/confidence from the LLM,
   artifact + nudge drafts, twin join); actions Send (= approve) and Hold
   (= request_changes, caveat: round-2 drafts stay server-side). *Persisted:*
   pending approvals from the fan-out for deals run earlier — department,
   approver, predicted delay, status; no draft text exists to fetch. Reject
   and checkpoint-status omitted (no routes; we do not infer state).
5. **Twin Center** — `approver_profiles`: avg turnaround, fastest format,
   slowest trigger, total reviewed, `last_updated` (visibly changes after a
   Resolve — the learning moment). Confidence and learning history omitted.
6. **Execution Timeline / Analytics / AI Control Center** — 🔴 blocked
   entirely; see missing-endpoint table.

**State:** TanStack Query; data-bearing views are client components (RSC only
for shell/layout). Query keys: `['dashboard']`, `['deals']`, `['deal', id]`,
`['twins']`. Invalidation: Send/Hold → dashboard, deals, deal:id; Resolve →
those + twins. Optimistic per-card review status (`awaiting → sending →
sent/held`) with rollback. Review runs mirrored to sessionStorage
(`threshold.review.v1`), hydrated on mount, defensively parsed (corrupt
payload → discard, start clean). New simulation replaces the stored queue.

**API layer:** `lib/api.ts` = typed fetch wrapper; Zod validates every
response at runtime; narrow error type (status + body); one retry on network
failure for GETs only; base URL from `NEXT_PUBLIC_API_URL`; auth-header slot
ready but unused. `types/api.ts` inferred from the Zod schemas (types and
validators cannot diverge). `send`/`resolve` pass query params, matching the
backend contract exactly.

**Design language:** enterprise-minimal within the existing shadcn/Tailwind
system (Stripe/Linear register) — neutral surfaces, one accent, dense tables,
tabular numerals for money/scores. Framer-motion only where state changes
meaning (card status, momentum gauge, drafted-action reveal).

**Login:** one-click button sets the client flag `AuthGuard` already checks;
`/` redirects by that flag.

## Step 3 — Folder structure

```
frontend/
  app/
    page.tsx                    # redirect: authed ? /dashboard : /login
    login/page.tsx              # one-click "Enter as Sales Ops"
    providers.tsx
    (app)/
      layout.tsx                # AuthGuard + Sidebar + TopNav
      dashboard/page.tsx
      deals/page.tsx
      deals/[dealId]/page.tsx
      review/page.tsx
      twins/page.tsx
  components/
    layout/    Sidebar, TopNav, AuthGuard
    dashboard/ StatCard, MomentumGauge, RecentDeals, ApprovalStats
    deals/     DealsTable, DealFilters, DealHeader, ApprovalList
    review/    ReviewCard, ScenarioLauncher, PersistedQueue
    twins/     ApproverCard (tested component, relocated), TwinGrid
    shared/    PageHeader, StatusBadge, EmptyState, BlockedNote
    ui/        (shadcn, unchanged)
  hooks/       use-dashboard, use-deals, use-deal, use-twins,
               use-review-actions, use-pending-approvals, use-review-session
  lib/         api.ts, query-keys.ts, momentum.ts, utils.ts
  types/       api.ts
  __tests__/   ported ReviewCard/ApproverCard suites + hydration test
```

**Deletions** (route collisions and orphans): flat `app/dashboard`,
`app/review` (placeholder stubs colliding with the `(app)` routes — currently
break `next build`), flat `app/deal/[id]` (duplicate detail route; links
updated to `/deals/…`), flat `app/twins` (recreated inside the shell);
orphaned root components `ReviewQueue`, `MomentumGauge`, `ActivityFeed`.
Sidebar lists exactly the five real pages; `/analytics`, `/timeline`,
`/system`, `/settings` links removed.

## Step 4 — Page-to-endpoint mapping

| Page | Endpoints | Blocked sub-features (missing endpoint) |
|---|---|---|
| Dashboard | `GET /dashboard/summary`; fan-out `GET /deals/` + `GET /deals/{id}` | AI recommendations |
| Deals | `GET /deals/` | server-side search/sort/pagination |
| Deal Details | `GET /deals/{id}`, `GET /dashboard/summary`, `POST /approvals/{id}/resolve` | documents; AI analysis at rest |
| Human Review | `POST /webhooks/crm`, `POST /approvals/{id}/send`, `POST /approvals/{id}/hold`, fan-out | Reject; checkpoint status; round-2 drafts |
| Twin Center | `GET /dashboard/summary` → `approver_profiles` | confidence; learning history |
| Execution Timeline | — | entire page: `GET /observability/deals/{id}/timeline` |
| Analytics | — | entire page: `GET /observability/metrics` |
| AI Control Center | — | entire page: timeline + checkpoint inspection |

## Step 5 — Implementation order

1. **Foundation** — `types/api.ts` + Zod + rebuilt `lib/api.ts` +
   `query-keys.ts`; route reconciliation (deletions, twins into shell,
   sidebar trim, one-click login). Gate: `npm run build` passes.
2. **Dashboard** — summary wiring, approval-stats fan-out, real momentum gauge.
3. **Deals + Deal Details** — table with client-side operations; detail with
   approvals, twin join, Resolve dialog.
4. **Human Review** — live webhook flow + sessionStorage mirror + optimistic
   card statuses + invalidations; persisted-queue layer.
5. **Twin Center** — TwinGrid on the relocated tested ApproverCard.
6. **Polish + tests** — enterprise-minimal pass; port ReviewQueue assertions
   onto the live ReviewCard flow; ApproverCard tests move with the file; new
   sessionStorage-hydration test. Gate: `npm test` + `npm run build` green,
   full demo-script walkthrough.

## Error handling

- Webhook failure → inline alert + retry; any previously stored queue stays
  intact. Multi-second pipeline latency gets a staged progress state
  ("Running Threshold pipeline — predicting friction, drafting artifacts…").
- Send/Hold/Resolve failure → that card/dialog alone shows the error with
  retry; optimistic status rolls back.
- Unreachable backend → EmptyState with retry action, never an eternal
  spinner; unknown deal id → EmptyState.
- Zod mismatch → loud console error + user-visible "unexpected API response"
  state (drift must never render as wrong numbers).

## Testing

- Port the `ReviewQueue` suite's assertions (send/hold via mocked API layer,
  per-card status isolation) onto the live review flow.
- `ApproverCard` tests move with the component (import-path change only).
- New: review page hydrates queue + statuses from sessionStorage on mount.
- Definition of done: `npm run build` and `npm test` green; backend `uv run
  pytest` untouched by construction; manual demo-script walkthrough
  (/twins → /review simulate → send → /dashboard momentum shift → resolve →
  /twins last_updated change).

## Non-goals

No backend changes; no Reject UI; no observability pages until their
endpoints exist; no visual rebrand outside the existing design system; no
fake data anywhere under any circumstance.
