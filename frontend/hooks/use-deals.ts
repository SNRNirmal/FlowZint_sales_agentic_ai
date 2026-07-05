import { useQuery } from "@tanstack/react-query"
import { fetchDeals, fetchDeal } from "@/lib/api"

export function useDeals() {
  return useQuery({
    queryKey: ["deals"],
    queryFn: fetchDeals,
    refetchInterval: 15_000,
  })
}

export function useDeal(dealId: string) {
  return useQuery({
    queryKey: ["deal", dealId],
    queryFn: () => fetchDeal(dealId),
    enabled: !!dealId,
  })
}
