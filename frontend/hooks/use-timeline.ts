import { useQuery } from "@tanstack/react-query"
import { fetchDealTimeline } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTimeline(dealId: string | null) {
  return useQuery({
    queryKey: dealId ? queryKeys.timeline(dealId) : [],
    queryFn: () => {
      if (!dealId) throw new Error("No dealId provided")
      return fetchDealTimeline(dealId)
    },
    enabled: !!dealId,
    staleTime: 30000,
  })
}
