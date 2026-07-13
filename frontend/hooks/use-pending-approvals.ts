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
