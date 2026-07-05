export interface Deal {
  id: string
  customer_name: string
  value: number
  discount_percent: number
  product_type: string
  customer_segment: string
  stage: string
  momentum_score: number
  status: "active" | "stalled" | "closed"
  created_at: string
}

export interface Approval {
  id: string
  deal_id: string
  department: string
  approver_id: string
  status: "pending" | "sent" | "approved" | "rejected"
  predicted_delay_days: number | null
  actual_delay_days: number | null
  artifact_format_used: string | null
}

export interface DealDetail {
  deal: Deal
  approvals: Approval[]
}
