import { useQuery } from "@tanstack/react-query"
import { fetchDeals, fetchAllApprovals } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import type { Approval, Deal } from "@/types/deal"

export interface PendingApproval {
  approval: Approval
  deal: Deal
}

// Returns all pending approvals across all deals efficiently using the
// /approvals/ endpoint and joining with the /deals/ endpoint.
export function usePendingApprovals() {
  return useQuery({
    queryKey: queryKeys.pendingApprovals,
    queryFn: async (): Promise<PendingApproval[]> => {
      const [deals, approvals] = await Promise.all([
        fetchDeals(),
        fetchAllApprovals(),
      ])
      const dealsById = new Map(deals.map((d) => [d.id, d]))
      return approvals
        .filter((a) => a.status === "pending")
        .map((approval) => ({ approval, deal: dealsById.get(approval.deal_id) }))
        .filter((p): p is PendingApproval => p.deal !== undefined)
    },
    refetchInterval: 30_000,
  })
}
