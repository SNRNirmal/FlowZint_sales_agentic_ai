import { useQuery } from "@tanstack/react-query"
import { fetchDeals, fetchDeal } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useDeals() {
  return useQuery({
    queryKey: queryKeys.deals,
    queryFn: fetchDeals,
    refetchInterval: 15_000,
  })
}

export function useDeal(dealId: string) {
  return useQuery({
    queryKey: queryKeys.deal(dealId),
    queryFn: () => fetchDeal(dealId),
    enabled: !!dealId,
  })
}
