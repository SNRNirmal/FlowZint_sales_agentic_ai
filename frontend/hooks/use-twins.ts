import { useQuery } from "@tanstack/react-query"
import { fetchDashboardSummary } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useTwins() {
  return useQuery({
    queryKey: queryKeys.twins,
    queryFn: async () => {
      const data = await fetchDashboardSummary()
      return data.approver_profiles
    },
    refetchInterval: 60_000,
  })
}
