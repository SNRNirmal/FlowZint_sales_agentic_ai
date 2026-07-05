import type { Deal } from "./deal"
import type { BehavioralTwin } from "./twin"

export interface DashboardSummary {
  total_deals: number
  stalled_deals: number
  avg_momentum_score: number
  deals: Deal[]
  approver_profiles: BehavioralTwin[]
}
