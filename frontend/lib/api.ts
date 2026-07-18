import { z } from "zod"
import {
  AnalyticsSummarySchema,
  ApprovalSchema,
  DashboardSummarySchema,
  DealDetailSchema,
  DealSchema,
  DealTimelineSchema,
  HoldResultSchema,
  ResolveResultSchema,
  SendResultSchema,
  WebhookAcceptedSchema,
  WebhookResultSchema,
  DealStatusSchema,
  type AnalyticsSummary,
  type DashboardSummary,
  type Deal,
  type DealDetail,
  type DealTimeline,
  type ResolvePayload,
  type ResolveResult,
  type WebhookAccepted,
  type WebhookResult,
  type DealStatus,
  Approval,
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

export async function apiFetch<S extends z.ZodTypeAny>(
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
export const triggerDemoDeal = (payload: Record<string, unknown>): Promise<WebhookAccepted> =>
  apiFetch("/webhooks/crm", WebhookAcceptedSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  })

export const fetchDealStatus = (dealId: string): Promise<DealStatus> =>
  apiFetch(`/deals/${dealId}/status`, DealStatusSchema)

export const fetchDealResult = (dealId: string): Promise<WebhookResult> =>
  apiFetch(`/deals/${dealId}/result`, WebhookResultSchema)

// ─── Analytics ───────────────────────────────────────────────────────────────
export const fetchAnalytics = (): Promise<AnalyticsSummary> =>
  apiFetch("/dashboard/analytics", AnalyticsSummarySchema)

// ─── Timeline ────────────────────────────────────────────────────────────────
export const fetchDealTimeline = (dealId: string): Promise<DealTimeline> =>
  apiFetch(`/deals/${dealId}/timeline`, DealTimelineSchema)

// ─── Cross-deal approvals ─────────────────────────────────────────────────────
export const fetchAllApprovals = (): Promise<Approval[]> =>
  apiFetch("/approvals/", z.array(ApprovalSchema))
