export interface RiskPrediction {
  root_cause: string
  delay_probability: number
}

export interface DraftedAction {
  approval_id: string
  department: string
  approver_id: string
  prediction: RiskPrediction
  artifact_draft: string
  nudge_draft: string
  review_status: string
}

export interface WebhookResponse {
  deal_id: string
  momentum_score: number
  drafted_actions: DraftedAction[]
}

export interface ResolvePayload {
  actual_delay_days: number
  artifact_format_used: string
  delay_reason?: string
}
