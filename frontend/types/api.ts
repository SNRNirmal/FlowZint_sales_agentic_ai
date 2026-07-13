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
