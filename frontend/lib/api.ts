import type { DashboardSummary } from "@/types/dashboard"
import type { Deal, DealDetail } from "@/types/deal"
import type { WebhookResponse, ResolvePayload } from "@/types/review"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  })
  if (!res.ok) {
    const error = await res.text()
    throw new Error(error || `API error ${res.status}`)
  }
  return res.json()
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export const fetchDashboardSummary = () =>
  apiFetch<DashboardSummary>("/dashboard/summary")

// ─── Deals ────────────────────────────────────────────────────────────────────
export const fetchDeals = () => apiFetch<Deal[]>("/deals/")

export const fetchDeal = (dealId: string) =>
  apiFetch<DealDetail>(`/deals/${dealId}`)

// ─── Approvals ────────────────────────────────────────────────────────────────
export const sendApprovalNudge = (approvalId: string, nudgeText: string) =>
  apiFetch(`/approvals/${approvalId}/send?nudge_text=${encodeURIComponent(nudgeText)}`, {
    method: "POST",
  })

export const holdApprovalNudge = (approvalId: string) =>
  apiFetch(`/approvals/${approvalId}/hold`, { method: "POST" })

export const resolveApproval = (approvalId: string, payload: ResolvePayload) =>
  apiFetch(
    `/approvals/${approvalId}/resolve?actual_delay_days=${payload.actual_delay_days}&artifact_format_used=${encodeURIComponent(payload.artifact_format_used)}&delay_reason=${encodeURIComponent(payload.delay_reason ?? "")}`,
    { method: "POST" }
  )

// ─── Webhooks / Demo ──────────────────────────────────────────────────────────
export const triggerDemoDeal = (payload: Record<string, unknown>) =>
  apiFetch<WebhookResponse>("/webhooks/crm", {
    method: "POST",
    body: JSON.stringify(payload),
  })
