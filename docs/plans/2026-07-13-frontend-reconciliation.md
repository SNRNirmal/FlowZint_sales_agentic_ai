# Threshold Frontend Reconciliation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reconcile the frontend into one buildable, demo-ready app that renders only real values from the frozen backend (design: `docs/plans/2026-07-12-frontend-design.md`).

**Architecture:** Next.js App Router with a single live route group `(app)`; TanStack Query against a Zod-validated typed API client; review-run state mirrored to sessionStorage; pending approvals derived by client fan-out over `GET /deals/` + `GET /deals/{id}`. Backend is never modified.

**Tech Stack:** Next.js (upgrading 14.2.5 → 15.5.20 exact), React 18.3.1, TypeScript, Tailwind + shadcn/ui, TanStack Query v5, Zod v4, recharts 2.x, framer-motion, Vitest + React Testing Library.

**Branch:** `claude/frontend-reconciliation` (already created; design doc committed).

**Hard rules for the executor:**
- Never touch `backend/` — it is frozen. `cd backend; uv run pytest` must stay green by construction.
- No invented endpoints, no `Math.random()`, no hardcoded metrics, no placeholder charts. Every rendered value traces to an audited endpoint (see design doc Step 1).
- All commands below run from `frontend/` unless stated otherwise. PowerShell syntax.
- Commit after every task with the exact message given (append the Claude co-author trailer).

**Current known-broken state (why Tasks 1–2 exist):**
1. `app/dashboard/page.tsx` and `app/review/page.tsx` (old stubs) collide with `app/(app)/dashboard` and `app/(app)/review` → `next build` fails.
2. `components/dashboard/MomentumGauge.tsx` imports `recharts`, which is not in `package.json`.
3. `app/(app)/deals/[dealId]/page.tsx` uses `use(params)` / `params: Promise<…>` — the Next 15 contract, on a branch pinned to Next 14.2.5.

---

## Task 1: Toolchain — add recharts, upgrade Next to 15.5.20

**Files:**
- Modify: `frontend/package.json`

**Step 1: Edit package.json**

In `dependencies`: change `"next": "14.2.5"` → `"next": "15.5.20"` (exact pin, matching the repo's react pin style) and add `"recharts": "^2.15.4"` (2.x on purpose — MomentumGauge uses the 2.x API and React is 18.3; ignore npm's nag to go to recharts 3).

Add a top-level key after `"dependencies"`:

```json
"overrides": {
  "next": {
    "postcss": "^8.5.10"
  }
}
```

This override is load-bearing: Next ≤16.2 bundles a nested postcss vulnerable to GHSA-qx2v-qp2m-jg93. Do not remove it.

**Step 2: Clean install (required — npm overrides do NOT apply on incremental installs)**

Run:
```powershell
Remove-Item -Recurse -Force node_modules
if (Test-Path package-lock.json) { Remove-Item -Force package-lock.json }
npm install
```
Expected: install completes; `npm ls postcss` shows postcss ≥8.5.10 under next.

**Step 3: Verify existing tests still pass**

Run: `npm test`
Expected: PASS — 3 test files (`smoke`, `ApproverCard`, `ReviewQueue`), 0 failures.

(`npm run build` still fails here — route collisions are Task 2. Do not chase build errors in this task.)

**Step 4: Commit**

```powershell
git add package.json package-lock.json
git commit -m "build(frontend): next 15.5.20 exact + postcss override, add recharts 2.x"
```

---

## Task 2: Delete colliding routes and orphan components

**Files:**
- Delete: `frontend/app/dashboard/page.tsx` (stub — collides with `(app)/dashboard`)
- Delete: `frontend/app/review/page.tsx` (stub — collides with `(app)/review`)
- Delete: `frontend/app/deal/[id]/page.tsx` (duplicate of `(app)/deals/[dealId]`; nothing links to `/deal/…` — verified by grep)
- Delete: `frontend/components/MomentumGauge.tsx`, `frontend/components/ActivityFeed.tsx` (root-level orphans; the live ones are under `components/dashboard/`)

Do NOT delete yet: `components/ReviewQueue.tsx` + its test (ported in Task 6), `components/ApproverCard.tsx` + its test (moved in Task 3), `app/twins/page.tsx` (replaced atomically in Task 3 — deleting it now would 404 `/twins`).

**Step 1: Delete**

```powershell
git rm frontend/app/dashboard/page.tsx frontend/app/review/page.tsx
git rm -r frontend/app/deal
git rm frontend/components/MomentumGauge.tsx frontend/components/ActivityFeed.tsx
```
(Run from repo root; adjust paths if running inside `frontend/`.)

**Step 2: First green build gate**

Run: `npm run build`
Expected: PASS — compiled successfully; route list shows `/dashboard`, `/deals`, `/deals/[dealId]`, `/review`, `/twins`, `/login`, `/` exactly once each.

Troubleshooting note: if the build errors inside `(app)/deals/[dealId]/page.tsx` on `use(params)`, stop and report — do not downgrade the page to the Next-14 params contract without flagging it (Next 15.5.20 is expected to accept it; this combination was validated in this repo on 2026-07-07).

**Step 3: Tests still green**

Run: `npm test`
Expected: PASS — same 3 files (their components were not deleted).

**Step 4: Commit**

```powershell
git commit -m "fix(frontend): remove colliding stub routes and orphan components"
```

---

## Task 3: Behavioral Twins page inside the (app) shell

**Files:**
- Modify: `frontend/__tests__/ApproverCard.test.tsx`
- Create: `frontend/components/twins/ApproverCard.tsx`
- Delete: `frontend/components/ApproverCard.tsx`
- Create: `frontend/app/(app)/twins/page.tsx`
- Delete: `frontend/app/twins/page.tsx`

**Step 1: Update the test first (import path + last_updated assertion)**

Replace the full contents of `frontend/__tests__/ApproverCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ApproverCard } from "@/components/twins/ApproverCard"

const twin = {
  approver_id: "finance_raj",
  department: "Finance",
  avg_turnaround_days: 3.2,
  fastest_responding_format: "one-pager",
  slowest_trigger: "missing discount justification",
  total_deals_reviewed: 14,
  last_updated: "2026-07-10T09:00:00Z",
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
    expect(screen.getByText(/Responds fastest to: one-pager/)).toBeInTheDocument()
    expect(screen.getByText(/Slows down on: missing discount justification/)).toBeInTheDocument()
  })

  it("shows the sample size behind the twin", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/14 deals reviewed/)).toBeInTheDocument()
  })

  it("shows when the Learning Agent last updated the twin", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/Updated/)).toBeInTheDocument()
  })
})
```

**Step 2: Run to verify it fails**

Run: `npx vitest run __tests__/ApproverCard.test.tsx`
Expected: FAIL — cannot resolve `@/components/twins/ApproverCard`.

**Step 3: Create the relocated, shell-styled card**

Create `frontend/components/twins/ApproverCard.tsx` (preserves every asserted string; only real `BehavioralTwin` fields rendered):

```tsx
"use client"

import { Brain } from "lucide-react"
import type { BehavioralTwin } from "@/types/twin"

export function ApproverCard({ twin }: { twin: BehavioralTwin }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 hover:border-primary/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{twin.approver_id}</p>
          <p className="text-xs text-muted-foreground">{twin.department}</p>
        </div>
      </div>

      <div className="mt-4 space-y-1.5 text-sm">
        <p className="text-foreground">
          Avg turnaround: <strong className="tabular-nums">{twin.avg_turnaround_days} days</strong>
        </p>
        <p className="text-muted-foreground">Responds fastest to: {twin.fastest_responding_format}</p>
        <p className="text-muted-foreground">Slows down on: {twin.slowest_trigger}</p>
      </div>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <span>{twin.total_deals_reviewed} deals reviewed</span>
        <span>Updated {new Date(twin.last_updated).toLocaleDateString()}</span>
      </div>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/ApproverCard.test.tsx`
Expected: PASS — 4 tests.

**Step 5: Atomic page swap**

Delete old files:
```powershell
git rm frontend/components/ApproverCard.tsx frontend/app/twins/page.tsx
```

Create `frontend/app/(app)/twins/page.tsx`:

```tsx
"use client"

import { Brain, RefreshCw } from "lucide-react"
import { useTwins } from "@/hooks/use-twins"
import { ApproverCard } from "@/components/twins/ApproverCard"
import { PageHeader } from "@/components/shared/PageHeader"
import { EmptyState } from "@/components/shared/EmptyState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function TwinsPage() {
  const { data: twins, isLoading, error, refetch, isFetching } = useTwins()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Behavioral Twins"
        description="Live profiles per internal approver, updated by the Learning Agent after every resolved approval."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} className="gap-2">
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive">
          Failed to load twins.{" "}
          <button onClick={() => refetch()} className="underline">Retry</button>
        </div>
      )}

      {!isLoading && !error && (
        twins && twins.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {twins.map((twin) => <ApproverCard key={twin.approver_id} twin={twin} />)}
          </div>
        ) : (
          <EmptyState
            icon={<Brain className="w-5 h-5" />}
            title="No twins seeded"
            description="Run backend/behavioral_twins/seed_data.py to seed the demo approver profiles."
          />
        )
      )}
    </div>
  )
}
```

Note: `useTwins()` returns `BehavioralTwin[]` typed via `data.approver_profiles` — check `hooks/use-twins.ts` compiles against it; if `data` is untyped, no change needed (it flows from `fetchDashboardSummary`).

**Step 6: Full gates**

Run: `npm test` → PASS (3 files). Run: `npm run build` → PASS, `/twins` appears once.

**Step 7: Commit**

```powershell
git add -A
git commit -m "feat(frontend): twins page inside (app) shell using relocated tested ApproverCard"
```

---

## Task 4: Sidebar trim + one-click demo login

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/__tests__/LoginForm.test.tsx`
- Modify: `frontend/features/auth/components/LoginForm.tsx` (full rewrite)
- Delete: `frontend/services/api.ts` (mockLogin's only consumer goes away)

**Step 1: Trim the sidebar (no test — pure config change)**

In `Sidebar.tsx`, replace the `NAV_ITEMS` and `BOTTOM_ITEMS` constants:

```tsx
const NAV_ITEMS = [
  { label: "Dashboard",        href: "/dashboard",  icon: LayoutDashboard },
  { label: "Deals",            href: "/deals",      icon: Briefcase },
  { label: "Human Review",     href: "/review",     icon: ClipboardCheck },
  { label: "Behavioral Twins", href: "/twins",      icon: Brain },
]
```

Delete the `BOTTOM_ITEMS` constant and its `{BOTTOM_ITEMS.map(...)}` block in the bottom nav `<div>` (keep the collapse-toggle `<button>`). Remove now-unused icon imports (`BarChart3`, `GitBranch`, `Settings`, `Activity`).

**Step 2: Write the failing login test**

Create `frontend/__tests__/LoginForm.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const push = vi.hoisted(() => vi.fn())
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
}))

import { LoginForm } from "@/features/auth/components/LoginForm"
import { useAuthStore } from "@/store/useAuthStore"

beforeEach(() => {
  push.mockClear()
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false })
})

describe("LoginForm (one-click demo login)", () => {
  it("renders a single entry button and no credential fields", () => {
    render(<LoginForm />)
    expect(screen.getByRole("button", { name: /enter as sales ops/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
  })

  it("authenticates the store and navigates to the dashboard on click", async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.click(screen.getByRole("button", { name: /enter as sales ops/i }))

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(push).toHaveBeenCalledWith("/dashboard")
  })
})
```

**Step 3: Run to verify it fails**

Run: `npx vitest run __tests__/LoginForm.test.tsx`
Expected: FAIL — the current form renders email/password fields, no "Enter as Sales Ops" button.

**Step 4: Rewrite LoginForm**

Replace the full contents of `frontend/features/auth/components/LoginForm.tsx`:

```tsx
"use client"

import { motion } from "framer-motion"
import { ArrowRight, Zap } from "lucide-react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/store/useAuthStore"

const DEMO_USER = {
  id: "user-001",
  name: "Sales Ops",
  email: "demo@flowzint.com",
  role: "admin",
}

export function LoginForm() {
  const router = useRouter()
  const login = useAuthStore((state) => state.login)

  const enter = () => {
    login(DEMO_USER, "demo-session")
    router.push("/dashboard")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="w-full max-w-[400px]"
    >
      <Card className="border-border bg-card shadow-2xl backdrop-blur-sm">
        <CardHeader className="space-y-2">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center">
            <Zap className="w-4.5 h-4.5 text-white" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
            Threshold
          </CardTitle>
          <CardDescription className="text-secondary-foreground">
            Internal deal-friction intelligence. Sign in to review what the agents drafted.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={enter} className="w-full gap-2">
            Enter as Sales Ops
            <ArrowRight className="w-4 h-4" />
          </Button>
        </CardContent>
        <CardFooter className="justify-center text-xs text-muted-foreground">
          Demo mode — no credentials required.
        </CardFooter>
      </Card>
    </motion.div>
  )
}
```

Delete the orphaned mock: `git rm frontend/services/api.ts`

**Step 5: Run tests to verify they pass**

Run: `npx vitest run __tests__/LoginForm.test.tsx` → PASS (2 tests).
Run: `npm test` → PASS (4 files). Run: `npm run build` → PASS.

**Step 6: Commit**

```powershell
git add -A
git commit -m "feat(frontend): one-click demo login, sidebar trimmed to real pages"
```

---

## Task 5: Typed API layer with Zod validation

**Files:**
- Create: `frontend/types/api.ts`
- Create: `frontend/lib/query-keys.ts`
- Create: `frontend/__tests__/api.test.ts`
- Modify: `frontend/lib/api.ts` (full rewrite)
- Modify: `frontend/types/deal.ts`, `frontend/types/dashboard.ts`, `frontend/types/review.ts`, `frontend/types/twin.ts` (become re-export shims)
- Modify: `frontend/hooks/use-review-actions.ts` (invalidation set)

**Step 1: Write the failing API tests**

Create `frontend/__tests__/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const okJson = (payload: unknown) => ({
  ok: true,
  status: 200,
  json: async () => payload,
  text: async () => JSON.stringify(payload),
})

const deal = {
  id: "d-1",
  customer_name: "Northwind",
  value: 180000,
  discount_percent: 18,
  product_type: "custom",
  customer_segment: "enterprise",
  stage: "verbal_agreement",
  momentum_score: 72,
  status: "active",
  created_at: "2026-07-12T10:00:00",
}

describe("lib/api", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("parses a valid deals payload", async () => {
    fetchMock.mockResolvedValueOnce(okJson([deal]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).resolves.toEqual([deal])
  })

  it("rejects loudly when the response shape drifts", async () => {
    fetchMock.mockResolvedValueOnce(okJson([{ ...deal, value: "not-a-number" }]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).rejects.toThrow(/Unexpected API response/)
  })

  it("sends the nudge as a query parameter", async () => {
    fetchMock.mockResolvedValueOnce(okJson({ status: "sent", approval_id: "ap-1" }))
    const { sendApprovalNudge } = await import("@/lib/api")
    await sendApprovalNudge("ap-1", "Hello world")
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain("/approvals/ap-1/send?nudge_text=Hello+world")
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST")
  })

  it("retries a GET exactly once on network failure", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(okJson([deal]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).resolves.toEqual([deal])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("never retries a mutation on network failure", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"))
    const { holdApprovalNudge } = await import("@/lib/api")
    await expect(holdApprovalNudge("ap-1")).rejects.toThrow()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
```

**Step 2: Run to verify it fails**

Run: `npx vitest run __tests__/api.test.ts`
Expected: FAIL — current `apiFetch` has no Zod parsing/retry; shape-drift test and retry tests fail.

**Step 3: Create `frontend/types/api.ts`** — schemas transcribed 1:1 from the backend audit (design doc Step 1):

```ts
import { z } from "zod"

// ── Persisted entities (SQLAlchemy models, serialized by FastAPI) ──────────
export const DealSchema = z.object({
  id: z.string(),
  customer_name: z.string(),
  value: z.number(),
  discount_percent: z.number(),
  product_type: z.string(),
  customer_segment: z.string(),
  stage: z.string(),
  momentum_score: z.number(),
  status: z.enum(["active", "stalled", "closed"]),
  created_at: z.string(),
})

export const ApprovalSchema = z.object({
  id: z.string(),
  deal_id: z.string(),
  department: z.string(),
  approver_id: z.string(),
  status: z.enum(["pending", "sent", "approved", "rejected", "escalated"]),
  predicted_delay_days: z.number().nullable(),
  actual_delay_days: z.number().nullable(),
  artifact_format_used: z.string().nullable(),
})

export const BehavioralTwinSchema = z.object({
  approver_id: z.string(),
  department: z.string(),
  avg_turnaround_days: z.number(),
  fastest_responding_format: z.string(),
  slowest_trigger: z.string(),
  total_deals_reviewed: z.number(),
  last_updated: z.string(),
})

// ── Route responses ─────────────────────────────────────────────────────────
export const DealDetailSchema = z.object({
  deal: DealSchema,
  approvals: z.array(ApprovalSchema),
})

export const DashboardSummarySchema = z.object({
  total_deals: z.number(),
  stalled_deals: z.number(),
  avg_momentum_score: z.number(),
  deals: z.array(DealSchema),
  approver_profiles: z.array(BehavioralTwinSchema),
})

// The webhook builds prediction from RiskScore.model_dump() — or {} when the
// risk node produced nothing for that approver. Every field must be optional.
export const RiskPredictionSchema = z
  .object({
    approver_id: z.string(),
    delay_probability: z.number(),
    expected_delay_days: z.number(),
    root_cause: z.string(),
    confidence: z.number(),
  })
  .partial()

export const DraftedActionSchema = z.object({
  approval_id: z.string(),
  department: z.string(),
  approver_id: z.string(),
  prediction: RiskPredictionSchema,
  artifact_draft: z.string(),
  nudge_draft: z.string(),
  review_status: z.string(),
})

export const WebhookResponseSchema = z.object({
  deal_id: z.string(),
  momentum_score: z.number(),
  drafted_actions: z.array(DraftedActionSchema),
})

export const SendResultSchema = z.object({ status: z.string(), approval_id: z.string() })
export const HoldResultSchema = z.object({ status: z.string(), approval_id: z.string() })
export const ResolveResultSchema = z.object({ status: z.string(), new_momentum_score: z.number() })

// ── Inferred types (single source of truth) ────────────────────────────────
export type Deal = z.infer<typeof DealSchema>
export type Approval = z.infer<typeof ApprovalSchema>
export type BehavioralTwin = z.infer<typeof BehavioralTwinSchema>
export type DealDetail = z.infer<typeof DealDetailSchema>
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>
export type RiskPrediction = z.infer<typeof RiskPredictionSchema>
export type DraftedAction = z.infer<typeof DraftedActionSchema>
export type WebhookResponse = z.infer<typeof WebhookResponseSchema>
export type ResolveResult = z.infer<typeof ResolveResultSchema>

export interface ResolvePayload {
  actual_delay_days: number
  artifact_format_used: string
  delay_reason?: string
}
```

**Step 4: Rewrite `frontend/lib/api.ts`**

```ts
import { z } from "zod"
import {
  DashboardSummarySchema,
  DealDetailSchema,
  DealSchema,
  HoldResultSchema,
  ResolveResultSchema,
  SendResultSchema,
  WebhookResponseSchema,
  type DashboardSummary,
  type Deal,
  type DealDetail,
  type ResolvePayload,
  type ResolveResult,
  type WebhookResponse,
} from "@/types/api"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function apiFetch<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  options?: RequestInit,
  attempt = 0,
): Promise<z.infer<S>> {
  const method = options?.method ?? "GET"

  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    })
  } catch (err) {
    // Network-level failure. Retry GETs exactly once; never retry mutations.
    if (method === "GET" && attempt === 0) {
      return apiFetch(path, schema, options, 1)
    }
    throw new ApiError(0, String(err), "Network error — is the backend running on " + API_URL + "?")
  }

  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body, body || `API error ${res.status}`)
  }

  const json = await res.json()
  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    // Contract drift must fail loudly, never render as wrong numbers.
    console.error("API contract mismatch", path, parsed.error.issues)
    throw new ApiError(res.status, JSON.stringify(parsed.error.issues), `Unexpected API response shape from ${path}`)
  }
  return parsed.data
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const fetchDashboardSummary = (): Promise<DashboardSummary> =>
  apiFetch("/dashboard/summary", DashboardSummarySchema)

// ─── Deals ───────────────────────────────────────────────────────────────────
export const fetchDeals = (): Promise<Deal[]> => apiFetch("/deals/", z.array(DealSchema))

export const fetchDeal = (dealId: string): Promise<DealDetail> =>
  apiFetch(`/deals/${dealId}`, DealDetailSchema)

// ─── Approvals (query params — the backend contract) ───────────────────────
export const sendApprovalNudge = (approvalId: string, nudgeText: string) =>
  apiFetch(
    `/approvals/${approvalId}/send?${new URLSearchParams({ nudge_text: nudgeText })}`,
    SendResultSchema,
    { method: "POST" },
  )

export const holdApprovalNudge = (approvalId: string) =>
  apiFetch(`/approvals/${approvalId}/hold`, HoldResultSchema, { method: "POST" })

export const resolveApproval = (approvalId: string, payload: ResolvePayload): Promise<ResolveResult> =>
  apiFetch(
    `/approvals/${approvalId}/resolve?${new URLSearchParams({
      actual_delay_days: String(payload.actual_delay_days),
      artifact_format_used: payload.artifact_format_used,
      delay_reason: payload.delay_reason ?? "",
    })}`,
    ResolveResultSchema,
    { method: "POST" },
  )

// ─── Webhooks / Demo ─────────────────────────────────────────────────────────
export const triggerDemoDeal = (payload: Record<string, unknown>): Promise<WebhookResponse> =>
  apiFetch("/webhooks/crm", WebhookResponseSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  })
```

**Step 5: Turn the old type files into shims (zero import churn elsewhere)**

`frontend/types/deal.ts`:
```ts
export type { Deal, Approval, DealDetail } from "./api"
```
`frontend/types/dashboard.ts`:
```ts
export type { DashboardSummary } from "./api"
```
`frontend/types/review.ts`:
```ts
export type { RiskPrediction, DraftedAction, WebhookResponse, ResolvePayload } from "./api"
```
`frontend/types/twin.ts`:
```ts
export type { BehavioralTwin } from "./api"
```

**Step 6: Create `frontend/lib/query-keys.ts`**

```ts
export const queryKeys = {
  dashboard: ["dashboard"] as const,
  deals: ["deals"] as const,
  deal: (id: string) => ["deal", id] as const,
  dealPrefix: ["deal"] as const,
  twins: ["twins"] as const,
  pendingApprovals: ["approvals", "pending"] as const,
}
```

**Step 7: Update `frontend/hooks/use-review-actions.ts`** — one invalidation helper, all four affected key families, `twins` added on resolve:

```ts
import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query"
import { sendApprovalNudge, holdApprovalNudge, resolveApproval } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import type { ResolvePayload } from "@/types/review"

function invalidateDealData(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.dashboard })
  qc.invalidateQueries({ queryKey: queryKeys.deals })
  qc.invalidateQueries({ queryKey: queryKeys.dealPrefix })
  qc.invalidateQueries({ queryKey: queryKeys.pendingApprovals })
}

export function useSendNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => sendApprovalNudge(id, text),
    onSuccess: () => invalidateDealData(qc),
  })
}

export function useHoldNudge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => holdApprovalNudge(id),
    onSuccess: () => invalidateDealData(qc),
  })
}

export function useResolveApproval() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ResolvePayload }) => resolveApproval(id, payload),
    onSuccess: () => {
      invalidateDealData(qc)
      qc.invalidateQueries({ queryKey: queryKeys.twins })
    },
  })
}
```

Also update `hooks/use-dashboard.ts`, `hooks/use-deals.ts`, `hooks/use-twins.ts` to import their keys from `queryKeys` (mechanical: `queryKey: queryKeys.dashboard`, etc.).

**Step 8: Run all gates**

Run: `npx vitest run __tests__/api.test.ts` → PASS (5 tests).
Run: `npm test` → PASS (5 files). Run: `npm run build` → PASS.

Note: `ReviewQueue.test.tsx` mocks `@/lib/api` with a factory, so the rewrite doesn't break it. If TypeScript complains in `ReviewCard.tsx` about `prediction.delay_probability` now being optional, add the temporary guard `action.prediction.delay_probability ?? 0` — Task 6 replaces that file anyway.

**Step 9: Commit**

```powershell
git add -A
git commit -m "feat(frontend): zod-validated typed API client, single type source, unified invalidations"
```

---

## Task 6: Review page — lifted card status, sessionStorage resilience, mutation wiring

**Files:**
- Create: `frontend/hooks/use-review-session.ts`
- Create: `frontend/__tests__/review-session.test.ts`
- Create: `frontend/__tests__/review-flow.test.tsx`
- Modify: `frontend/components/review/ReviewCard.tsx` (full rewrite — controlled status)
- Modify: `frontend/app/(app)/review/page.tsx` (full rewrite)
- Delete: `frontend/components/ReviewQueue.tsx`, `frontend/__tests__/ReviewQueue.test.tsx` (assertions ported into review-flow.test.tsx)

**Step 1: Write the failing session-mirror test**

Create `frontend/__tests__/review-session.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest"
import { loadReviewSession, saveReviewSession, clearReviewSession, REVIEW_SESSION_KEY } from "@/hooks/use-review-session"

const result = {
  deal_id: "d-1",
  momentum_score: 70,
  drafted_actions: [
    {
      approval_id: "ap-1",
      department: "Finance",
      approver_id: "finance_raj",
      prediction: { root_cause: "Slow on discounts", delay_probability: 0.42 },
      artifact_draft: "Artifact",
      nudge_draft: "Nudge",
      review_status: "awaiting_human_review",
    },
  ],
}

beforeEach(() => sessionStorage.clear())

describe("review session mirror", () => {
  it("round-trips a run and its card statuses", () => {
    saveReviewSession({ result, statuses: { "ap-1": "sent" } })
    expect(loadReviewSession()).toEqual({ result, statuses: { "ap-1": "sent" } })
  })

  it("returns null when nothing is stored", () => {
    expect(loadReviewSession()).toBeNull()
  })

  it("discards corrupt JSON instead of throwing", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, "{not json")
    expect(loadReviewSession()).toBeNull()
  })

  it("discards payloads that fail schema validation", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, JSON.stringify({ result: { deal_id: 1 }, statuses: {} }))
    expect(loadReviewSession()).toBeNull()
  })

  it("clears the mirror", () => {
    saveReviewSession({ result, statuses: {} })
    clearReviewSession()
    expect(loadReviewSession()).toBeNull()
  })
})
```

**Step 2: Run to verify it fails** — `npx vitest run __tests__/review-session.test.ts` → FAIL (module missing).

**Step 3: Create `frontend/hooks/use-review-session.ts`**

```ts
import { z } from "zod"
import { WebhookResponseSchema, type WebhookResponse } from "@/types/api"

export const REVIEW_SESSION_KEY = "threshold.review.v1"

// Only settled outcomes are persisted; in-flight states rehydrate as idle.
const StoredStatusSchema = z.enum(["sent", "held"])
const StoredSessionSchema = z.object({
  result: WebhookResponseSchema,
  statuses: z.record(z.string(), StoredStatusSchema),
})

export type StoredReviewSession = {
  result: WebhookResponse
  statuses: Record<string, "sent" | "held">
}

export function loadReviewSession(): StoredReviewSession | null {
  if (typeof window === "undefined") return null
  const raw = sessionStorage.getItem(REVIEW_SESSION_KEY)
  if (!raw) return null
  try {
    const parsed = StoredSessionSchema.safeParse(JSON.parse(raw))
    return parsed.success ? parsed.data : null
  } catch {
    return null
  }
}

export function saveReviewSession(session: StoredReviewSession): void {
  if (typeof window === "undefined") return
  sessionStorage.setItem(REVIEW_SESSION_KEY, JSON.stringify(session))
}

export function clearReviewSession(): void {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(REVIEW_SESSION_KEY)
}
```

**Step 4: Run** — `npx vitest run __tests__/review-session.test.ts` → PASS (5 tests).

**Step 5: Write the failing review-flow test (ports every ReviewQueue assertion to the live page)**

Create `frontend/__tests__/review-flow.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/api", () => ({
  sendApprovalNudge: vi.fn().mockResolvedValue({ status: "sent", approval_id: "ap-1" }),
  holdApprovalNudge: vi.fn().mockResolvedValue({ status: "held", approval_id: "ap-1" }),
  triggerDemoDeal: vi.fn(),
}))

import { holdApprovalNudge, sendApprovalNudge } from "@/lib/api"
import { REVIEW_SESSION_KEY } from "@/hooks/use-review-session"
import ReviewPage from "@/app/(app)/review/page"

const action = (id: string, department: string) => ({
  approval_id: id,
  department,
  approver_id: "finance_raj",
  prediction: { root_cause: "Slow on discount deals", delay_probability: 0.42 },
  artifact_draft: "Draft artifact body",
  nudge_draft: "Please review this deal",
  review_status: "awaiting_human_review",
})

const storedRun = (actions: ReturnType<typeof action>[]) =>
  JSON.stringify({
    result: { deal_id: "d-1", momentum_score: 70, drafted_actions: actions },
    statuses: {},
  })

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReviewPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe("review flow", () => {
  it("hydrates a stored run from sessionStorage on mount", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()
    expect(screen.getByText("finance_raj")).toBeInTheDocument()
    expect(screen.getByText("Draft artifact body")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Please review this deal")).toBeInTheDocument()
  })

  it("shows the empty state when nothing is stored", () => {
    renderPage()
    expect(screen.getByText(/queue is empty/i)).toBeInTheDocument()
  })

  it("Send calls the API with the (editable) nudge text and marks the card sent", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))

    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findByText(/^sent$/i)).toBeInTheDocument()
  })

  it("Hold calls the API and marks the card held without sending", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /hold/i }))

    expect(holdApprovalNudge).toHaveBeenCalledWith("ap-1")
    expect(await screen.findByText(/^held$/i)).toBeInTheDocument()
    expect(sendApprovalNudge).not.toHaveBeenCalled()
  })

  it("tracks status per card, not globally", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      REVIEW_SESSION_KEY,
      storedRun([action("ap-1", "Finance"), action("ap-2", "Legal")]),
    )
    renderPage()

    await user.click(screen.getAllByRole("button", { name: /send to approver/i })[0])

    expect(sendApprovalNudge).toHaveBeenCalledTimes(1)
    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findAllByText(/^sent$/i)).toHaveLength(1)
  })

  it("persists settled statuses back to the mirror", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))
    await screen.findByText(/^sent$/i)

    const stored = JSON.parse(sessionStorage.getItem(REVIEW_SESSION_KEY)!)
    expect(stored.statuses["ap-1"]).toBe("sent")
  })
})
```

Note: the page also renders `PersistedQueue` after Task 7; in this task the page does not include it yet, so the test file stays valid throughout.

**Step 6: Run to verify it fails** — `npx vitest run __tests__/review-flow.test.tsx` → FAIL (page neither hydrates nor lifts status).

**Step 7: Rewrite `frontend/components/review/ReviewCard.tsx`** — controlled status, per-card error, optional prediction guard. Keep the existing visual structure; the required changes:

```tsx
"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Send, PauseCircle, ChevronDown, ChevronUp,
  AlertTriangle, Brain, FileText, MessageSquare, CheckCircle2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { DraftedAction } from "@/types/review"

export type CardStatus = "idle" | "sending" | "holding" | "sent" | "held" | "error"

interface ReviewCardProps {
  action: DraftedAction
  status: CardStatus
  error?: string
  onSend: (id: string, text: string) => void
  onHold: (id: string) => void
  index: number
}

export function ReviewCard({ action, status, error, onSend, onHold, index }: ReviewCardProps) {
  const [expanded, setExpanded] = React.useState(true)
  const [nudgeText, setNudgeText] = React.useState(action.nudge_draft)

  const delayProb = action.prediction.delay_probability
  const delayPct = typeof delayProb === "number" ? Math.round(delayProb * 100) : null
  const riskColor =
    delayPct == null ? "text-muted-foreground"
    : delayPct >= 70 ? "text-red-400"
    : delayPct >= 40 ? "text-amber-400"
    : "text-emerald-400"
  const riskBg =
    delayPct != null && delayPct >= 70 ? "bg-red-500/10 border-red-500/20"
    : delayPct != null && delayPct >= 40 ? "bg-amber-500/10 border-amber-500/20"
    : "bg-emerald-500/10 border-emerald-500/20"

  const done = status === "sent" || status === "held"
  const busy = status === "sending" || status === "holding"

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08 }}
      className={cn(
        "bg-card border rounded-xl overflow-hidden transition-all",
        done ? "border-border opacity-60" : "border-border hover:border-primary/30"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-4 px-5 py-4 cursor-pointer" onClick={() => setExpanded((e) => !e)}>
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-foreground">{action.approver_id}</span>
            <Badge variant="outline" className="text-xs px-2 py-0">{action.department}</Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {action.prediction.root_cause || "Risk analysis complete"}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className={cn("text-sm font-bold tabular-nums", riskColor)}>
            {delayPct == null ? "—" : `${delayPct}%`}
          </span>
          <span className={cn("text-xs px-2 py-0.5 rounded-full border font-medium", riskBg)}>
            delay risk
          </span>
          {done && (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {status}
            </span>
          )}
          {expanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />
          }
        </div>
      </div>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4 border-t border-border pt-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI-Generated Artifact</span>
                </div>
                <pre className="w-full text-xs text-foreground bg-background border border-border rounded-lg p-4 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
                  {action.artifact_draft || "No artifact generated."}
                </pre>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Nudge Message</span>
                  <span className="text-xs text-primary ml-auto">Editable before sending</span>
                </div>
                <Textarea
                  value={nudgeText}
                  onChange={(e) => setNudgeText(e.target.value)}
                  disabled={done || busy}
                  className="text-sm bg-background border-border min-h-[80px] resize-y"
                  placeholder="Nudge message will appear here after pipeline runs..."
                />
              </div>

              {action.prediction.root_cause && (
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-500/5 border border-amber-500/15">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-amber-400">Risk Analysis</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{action.prediction.root_cause}</p>
                  </div>
                </div>
              )}

              {status === "error" && (
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-destructive/5 border border-destructive/20">
                  <AlertTriangle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                  <p className="text-xs text-destructive">{error || "Action failed."} Try again.</p>
                </div>
              )}

              {!done && (
                <div className="flex items-center gap-2 pt-1">
                  <Button
                    onClick={() => onSend(action.approval_id, nudgeText)}
                    disabled={busy || !nudgeText.trim()}
                    size="sm"
                    className="gap-2"
                  >
                    {status === "sending" ? "Sending…" : (<><Send className="w-3.5 h-3.5" />Send to Approver</>)}
                  </Button>
                  <Button
                    onClick={() => onHold(action.approval_id)}
                    disabled={busy}
                    variant="outline"
                    size="sm"
                    className="gap-2"
                  >
                    {status === "holding" ? "Holding…" : (<><PauseCircle className="w-3.5 h-3.5" />Hold</>)}
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
```

**Step 8: Rewrite `frontend/app/(app)/review/page.tsx`**

Keep `DEMO_SCENARIOS` exactly as-is (three scenarios). New page logic:

```tsx
"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Play, ClipboardCheck, Loader2, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { triggerDemoDeal } from "@/lib/api"
import { useSendNudge, useHoldNudge } from "@/hooks/use-review-actions"
import {
  loadReviewSession, saveReviewSession, clearReviewSession,
} from "@/hooks/use-review-session"
import { ReviewCard, type CardStatus } from "@/components/review/ReviewCard"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { PageHeader } from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { WebhookResponse } from "@/types/review"

const DEMO_SCENARIOS = [ /* unchanged — copy the three scenarios verbatim from the current file */ ]

export default function ReviewPage() {
  const [scenario, setScenario] = React.useState("0")
  // Lazy initializer: hydrate the last run (and settled statuses) from sessionStorage.
  const [session] = React.useState(() => loadReviewSession())
  const [result, setResult] = React.useState<WebhookResponse | null>(session?.result ?? null)
  const [statuses, setStatuses] = React.useState<Record<string, CardStatus>>(session?.statuses ?? {})
  const [errors, setErrors] = React.useState<Record<string, string>>({})

  const sendMutation = useSendNudge()
  const holdMutation = useHoldNudge()

  const persist = (nextResult: WebhookResponse, nextStatuses: Record<string, CardStatus>) => {
    const settled = Object.fromEntries(
      Object.entries(nextStatuses).filter(([, s]) => s === "sent" || s === "held"),
    ) as Record<string, "sent" | "held">
    saveReviewSession({ result: nextResult, statuses: settled })
  }

  const runMutation = useMutation({
    mutationFn: () => triggerDemoDeal(DEMO_SCENARIOS[parseInt(scenario)].payload),
    onSuccess: (data) => {
      setResult(data)
      setStatuses({})
      setErrors({})
      persist(data, {})
    },
  })

  const setCardStatus = (id: string, status: CardStatus, errorMsg?: string) => {
    setStatuses((prev) => {
      const next = { ...prev, [id]: status }
      if (result) persist(result, next)
      return next
    })
    setErrors((prev) => ({ ...prev, [id]: errorMsg ?? "" }))
  }

  const handleSend = (id: string, text: string) => {
    setCardStatus(id, "sending")
    sendMutation.mutate(
      { id, text },
      {
        onSuccess: () => setCardStatus(id, "sent"),
        onError: (err) => setCardStatus(id, "error", err instanceof Error ? err.message : "Send failed"),
      },
    )
  }

  const handleHold = (id: string) => {
    setCardStatus(id, "holding")
    holdMutation.mutate(id, {
      onSuccess: () => setCardStatus(id, "held"),
      onError: (err) => setCardStatus(id, "error", err instanceof Error ? err.message : "Hold failed"),
    })
  }

  const handleClear = () => {
    setResult(null)
    setStatuses({})
    setErrors({})
    clearReviewSession()
  }

  const totalCount = result?.drafted_actions.length ?? 0
  const settledCount = Object.values(statuses).filter((s) => s === "sent" || s === "held").length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Human Review Queue"
        description="Nothing Threshold drafts reaches a real approver until you explicitly send it."
      />

      {/* Control panel — unchanged visual structure from the current file:
          Select over DEMO_SCENARIOS + Run button + Clear button, except
          Clear now calls handleClear. */}

      {/* Loading state — same block, with staged copy:
          "Threshold pipeline running…" /
          "Detecting approvals, predicting friction, drafting artifacts and nudges." */}

      {/* Error state — same block as current file. */}

      {/* Results — same summary bar (add `{settledCount}/{totalCount} actioned`
          instead of the old hardcoded completedCount), then: */}
      {result && (
        <div className="space-y-3">
          {result.drafted_actions.map((action, i) => (
            <ReviewCard
              key={action.approval_id}
              action={action}
              status={statuses[action.approval_id] ?? "idle"}
              error={errors[action.approval_id]}
              onSend={handleSend}
              onHold={handleHold}
              index={i}
            />
          ))}
        </div>
      )}

      {/* Empty state — same block as current file. */}
    </div>
  )
}
```

(The executor copies the untouched JSX blocks verbatim from the current file; the diff is: hydration, lifted statuses, mutation hooks, persist-on-change, Clear clears storage, `settledCount`, staged loading copy.)

**Step 9: Delete the orphan and its test (assertions now live in review-flow.test.tsx)**

```powershell
git rm frontend/components/ReviewQueue.tsx frontend/__tests__/ReviewQueue.test.tsx
```

**Step 10: Run all gates**

Run: `npx vitest run __tests__/review-flow.test.tsx` → PASS (6 tests).
Run: `npm test` → PASS (6 files: smoke, ApproverCard, LoginForm, api, review-session, review-flow).
Run: `npm run build` → PASS.

**Step 11: Commit**

```powershell
git add -A
git commit -m "feat(frontend): review queue survives refresh via sessionStorage; per-card status lifted and wired to react-query"
```

---

## Task 7: Pending-approvals fan-out — honest dashboard stat + persisted review layer

**Files:**
- Create: `frontend/hooks/use-pending-approvals.ts`
- Create: `frontend/__tests__/pending-approvals.test.tsx`
- Create: `frontend/components/review/PersistedQueue.tsx`
- Modify: `frontend/app/(app)/dashboard/page.tsx` (replace the mislabeled stat)
- Modify: `frontend/app/(app)/review/page.tsx` (append PersistedQueue section)

**Step 1: Write the failing hook test**

Create `frontend/__tests__/pending-approvals.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import * as React from "react"

vi.mock("@/lib/api", () => ({
  fetchDeals: vi.fn().mockResolvedValue([
    { id: "d-1", customer_name: "A", value: 1, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 90, status: "active", created_at: "2026-07-12T00:00:00" },
    { id: "d-2", customer_name: "B", value: 2, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 80, status: "active", created_at: "2026-07-12T00:00:00" },
  ]),
  fetchDeal: vi.fn().mockImplementation(async (id: string) => ({
    deal: { id, customer_name: id === "d-1" ? "A" : "B", value: 1, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 90, status: "active", created_at: "2026-07-12T00:00:00" },
    approvals: [
      { id: `${id}-ap-pending`, deal_id: id, department: "Finance", approver_id: "finance_raj", status: "pending", predicted_delay_days: 2, actual_delay_days: null, artifact_format_used: null },
      { id: `${id}-ap-approved`, deal_id: id, department: "Legal", approver_id: "legal_sam", status: "approved", predicted_delay_days: 1, actual_delay_days: 1, artifact_format_used: "redline" },
    ],
  })),
}))

import { usePendingApprovals } from "@/hooks/use-pending-approvals"

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("usePendingApprovals", () => {
  it("flattens pending approvals across all deals, with their deal attached", async () => {
    const { result } = renderHook(() => usePendingApprovals(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0].approval.status).toBe("pending")
    expect(result.current.data![0].deal.id).toBe("d-1")
    expect(result.current.data![1].deal.id).toBe("d-2")
  })
})
```

**Step 2: Run to verify it fails** — `npx vitest run __tests__/pending-approvals.test.tsx` → FAIL (module missing).

**Step 3: Create `frontend/hooks/use-pending-approvals.ts`**

```ts
import { useQuery } from "@tanstack/react-query"
import { fetchDeal, fetchDeals } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import type { Approval, Deal } from "@/types/deal"

export interface PendingApproval {
  approval: Approval
  deal: Deal
}

// The backend has no cross-deal approvals endpoint; this fan-out over
// GET /deals/ + GET /deals/{id} is the only honest source. N+1 is
// acknowledged and fine at demo scale (see design doc Step 2).
export function usePendingApprovals() {
  return useQuery({
    queryKey: queryKeys.pendingApprovals,
    queryFn: async (): Promise<PendingApproval[]> => {
      const deals = await fetchDeals()
      const details = await Promise.all(deals.map((d) => fetchDeal(d.id)))
      return details.flatMap((detail) =>
        detail.approvals
          .filter((a) => a.status === "pending")
          .map((approval) => ({ approval, deal: detail.deal })),
      )
    },
    refetchInterval: 30_000,
  })
}
```

**Step 4: Run** — `npx vitest run __tests__/pending-approvals.test.tsx` → PASS.

**Step 5: Fix the dashboard's mislabeled stat**

In `frontend/app/(app)/dashboard/page.tsx`:
- Add import: `import { usePendingApprovals } from "@/hooks/use-pending-approvals"`
- Inside the component add: `const { data: pending } = usePendingApprovals()`
- Delete the line `const pendingApprovals = deals.filter((d) => d.status === "active").length` (it counted active *deals*, not pending approvals — exactly the heuristic the design bans).
- Replace the "Pending Approvals" StatCard props:

```tsx
<StatCard
  index={1}
  label="Pending Approvals"
  value={pending ? pending.length : "—"}
  icon={<ClipboardCheck className="w-4 h-4" />}
  delta="Awaiting review"
  deltaType={(pending?.length ?? 0) > 0 ? "negative" : "positive"}
/>
```

**Step 6: Create `frontend/components/review/PersistedQueue.tsx`**

```tsx
"use client"

import Link from "next/link"
import { Clock, ArrowRight } from "lucide-react"
import { usePendingApprovals } from "@/hooks/use-pending-approvals"
import { StatusBadge } from "@/components/shared/StatusBadge"

// Approvals from earlier pipeline runs. The backend does not persist draft
// text (design doc, Step 1) — so this layer shows only what really exists:
// department, approver, predicted delay, status.
export function PersistedQueue({ excludeIds }: { excludeIds: string[] }) {
  const { data, isLoading } = usePendingApprovals()

  const rows = (data ?? []).filter(({ approval }) => !excludeIds.includes(approval.id))
  if (isLoading || rows.length === 0) return null

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Clock className="w-4 h-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold text-foreground">Earlier deals awaiting action</h2>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Draft text from past runs isn&apos;t stored server-side. Open the deal to record an outcome,
        or run a new simulation to generate fresh drafts.
      </p>
      <div className="space-y-2">
        {rows.map(({ approval, deal }) => (
          <Link
            key={approval.id}
            href={`/deals/${deal.id}`}
            className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card/50 hover:border-primary/40 transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {deal.customer_name} · {approval.department}
              </p>
              <p className="text-xs text-muted-foreground">{approval.approver_id}</p>
            </div>
            {approval.predicted_delay_days != null && (
              <span className="text-xs text-amber-400 tabular-nums">
                {approval.predicted_delay_days}d predicted delay
              </span>
            )}
            <StatusBadge status={approval.status} />
            <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
        ))}
      </div>
    </div>
  )
}
```

**Step 7: Append to the review page** (bottom of the returned JSX, after the empty state):

```tsx
<PersistedQueue excludeIds={result?.drafted_actions.map((a) => a.approval_id) ?? []} />
```
with import `import { PersistedQueue } from "@/components/review/PersistedQueue"`.

**Step 8: All gates**

Run: `npm test` → PASS (7 files; review-flow still passes — PersistedQueue renders null while its query loads, and `@/lib/api` is mocked there without `fetchDeals`, so add `fetchDeals: vi.fn().mockResolvedValue([])` and `fetchDeal: vi.fn()` to the review-flow mock factory).
Run: `npm run build` → PASS.

**Step 9: Commit**

```powershell
git add -A
git commit -m "feat(frontend): real pending-approvals fan-out for dashboard stat and persisted review layer"
```

---

## Task 8: Resolve-outcome dialog (the learning loop)

**Files:**
- Create: `frontend/__tests__/resolve-dialog.test.tsx`
- Create: `frontend/components/deals/ResolveDialog.tsx`
- Modify: `frontend/app/(app)/deals/[dealId]/page.tsx` (wire into ApprovalRow)

**Step 1: Write the failing test**

Create `frontend/__tests__/resolve-dialog.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/api", () => ({
  resolveApproval: vi.fn().mockResolvedValue({ status: "approved", new_momentum_score: 87 }),
}))

import { resolveApproval } from "@/lib/api"
import { ResolveDialog } from "@/components/deals/ResolveDialog"

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ResolveDialog approvalId="ap-1" approverId="finance_raj" />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe("ResolveDialog", () => {
  it("submits the outcome and shows the recomputed momentum", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    await user.type(screen.getByLabelText(/actual delay/i), "2.5")
    await user.type(screen.getByLabelText(/artifact format/i), "one-pager")
    await user.click(screen.getByRole("button", { name: /save outcome/i }))

    expect(resolveApproval).toHaveBeenCalledWith("ap-1", {
      actual_delay_days: 2.5,
      artifact_format_used: "one-pager",
      delay_reason: "",
    })
    expect(await screen.findByText(/momentum now 87/i)).toBeInTheDocument()
  })

  it("does not submit without required fields", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    await user.click(screen.getByRole("button", { name: /save outcome/i }))

    expect(resolveApproval).not.toHaveBeenCalled()
  })
})
```

**Step 2: Run to verify it fails** — `npx vitest run __tests__/resolve-dialog.test.tsx` → FAIL (module missing).

**Step 3: Create `frontend/components/deals/ResolveDialog.tsx`**

```tsx
"use client"

import * as React from "react"
import { CheckCircle2, ClipboardCheck } from "lucide-react"
import { useResolveApproval } from "@/hooks/use-review-actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"

interface ResolveDialogProps {
  approvalId: string
  approverId: string
}

// Records the real outcome of an approval. This is the only UI action that
// exercises the Learning Agent: the backend updates the approver's
// Behavioral Twin, appends to learning_log, and recomputes momentum.
export function ResolveDialog({ approvalId, approverId }: ResolveDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [delayDays, setDelayDays] = React.useState("")
  const [format, setFormat] = React.useState("")
  const [reason, setReason] = React.useState("")

  const resolveMutation = useResolveApproval()

  const canSubmit = delayDays.trim() !== "" && !Number.isNaN(Number(delayDays)) && format.trim() !== ""

  const submit = () => {
    if (!canSubmit) return
    resolveMutation.mutate({
      id: approvalId,
      payload: {
        actual_delay_days: Number(delayDays),
        artifact_format_used: format.trim(),
        delay_reason: reason.trim(),
      },
    })
  }

  const reset = (next: boolean) => {
    setOpen(next)
    if (!next) {
      resolveMutation.reset()
      setDelayDays("")
      setFormat("")
      setReason("")
    }
  }

  return (
    <Dialog open={open} onOpenChange={reset}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <ClipboardCheck className="w-3.5 h-3.5" />
          Record outcome
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Record outcome — {approverId}</DialogTitle>
          <DialogDescription>
            The Learning Agent updates this approver&apos;s Behavioral Twin from what actually happened.
          </DialogDescription>
        </DialogHeader>

        {resolveMutation.isSuccess ? (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">Outcome recorded</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Twin updated · momentum now {resolveMutation.data.new_momentum_score}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="actual-delay">Actual delay (days)</Label>
              <Input
                id="actual-delay"
                type="number"
                min="0"
                step="0.5"
                value={delayDays}
                onChange={(e) => setDelayDays(e.target.value)}
                placeholder="e.g. 2.5"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="artifact-format">Artifact format that worked</Label>
              <Input
                id="artifact-format"
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                placeholder="e.g. one-pager"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="delay-reason">Delay reason (optional)</Label>
              <Textarea
                id="delay-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="What actually held it up?"
                className="min-h-[60px]"
              />
            </div>
            {resolveMutation.isError && (
              <p className="text-xs text-destructive">
                {resolveMutation.error instanceof Error ? resolveMutation.error.message : "Failed to record outcome."}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          {resolveMutation.isSuccess ? (
            <Button size="sm" onClick={() => reset(false)}>Done</Button>
          ) : (
            <Button size="sm" onClick={submit} disabled={!canSubmit || resolveMutation.isPending}>
              {resolveMutation.isPending ? "Saving…" : "Save outcome"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

**Step 4: Run** — `npx vitest run __tests__/resolve-dialog.test.tsx` → PASS (2 tests).

**Step 5: Wire into the deal detail page**

In `frontend/app/(app)/deals/[dealId]/page.tsx`, inside `ApprovalRow` (after `<StatusBadge …/>`), render the dialog for approvals that can still be resolved:

```tsx
{(approval.status === "sent" || approval.status === "pending") && (
  <ResolveDialog approvalId={approval.id} approverId={approval.approver_id} />
)}
```
with import `import { ResolveDialog } from "@/components/deals/ResolveDialog"`.

**Step 6: All gates**

Run: `npm test` → PASS (8 files). Run: `npm run build` → PASS.

**Step 7: Commit**

```powershell
git add -A
git commit -m "feat(frontend): resolve-outcome dialog closes the learning loop from deal detail"
```

---

## Task 9: Final verification + demo script refresh

**Files:**
- Modify: `demo/demo_script.md`

**Step 1: Full automated gates**

```powershell
npm test          # expect: 8 files passing, 0 failures
npm run build     # expect: compiled successfully, 7 unique routes
cd ..\backend
uv run pytest     # expect: green — backend untouched by construction
```

**Step 2: Live walkthrough (backend + frontend running)**

Backend: `cd backend; uv run uvicorn main:app --reload` (needs `backend/.env` with `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY`), seed twins once: `uv run python behavioral_twins/seed_data.py`. Frontend: `npm run dev` (must be port 3000 — backend CORS allows only `http://localhost:3000`).

Checklist (maps to the demo script + new learning-loop close):
1. `/` redirects to `/login`; one click on "Enter as Sales Ops" lands on `/dashboard`.
2. Sidebar shows exactly Dashboard / Deals / Human Review / Behavioral Twins — every link resolves.
3. `/twins` shows the 4 seeded twins with real stats.
4. `/review` → Run Pipeline → drafted actions appear with root causes, real delay-risk %, artifact + nudge drafts.
5. Press F5 mid-review → the queue and any sent/held card states come back.
6. Send one action → switch to `/dashboard` → momentum and pending-approvals reflect it without a manual reload.
7. Open the deal from `/deals` → Record outcome (2.5 days, "one-pager") → success shows new momentum.
8. `/twins` → that approver's "Updated" date and stats changed — the Learning Agent visibly learned.

**Step 3: Update `demo/demo_script.md`**

- Replace setup line 1 with: `cd backend && uv run uvicorn main:app --reload`
- Replace setup line 2 with: `uv run python behavioral_twins/seed_data.py`
- Add after step 6 (momentum shift): a step 7 — *"Open the deal → Record outcome (actual delay, format that worked). Then flip to `/twins`: the approver's profile just changed. This is the Learning Agent — Threshold gets sharper with every deal."* (renumber the old step 7 to 8).
- Add to setup: *"Login is one click ('Enter as Sales Ops') — no credentials."*

**Step 4: Final commit**

```powershell
git add -A
git commit -m "docs(demo): uv commands, one-click login, learning-loop step in walkthrough"
```

---

## Definition of done

- `npm run build` passes (route collisions, missing recharts, and the Next-15 params contract all resolved).
- `npm test` passes: smoke, ApproverCard (4), LoginForm (2), api (5), review-session (5), review-flow (6), pending-approvals (1), resolve-dialog (2).
- `uv run pytest` in `backend/` untouched and green.
- Every rendered value traces to an audited endpoint; blocked features (Reject, checkpoint status, documents, twin confidence, learning history, observability pages) appear nowhere in the UI.
- The 8-step live walkthrough completes without a dead link, eternal spinner, or fake number.
