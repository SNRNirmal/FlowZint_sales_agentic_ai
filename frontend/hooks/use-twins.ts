import { useQuery } from "@tanstack/react-query"
import { fetchDashboardSummary } from "@/lib/api"

export function useTwins() {
  return useQuery({
    queryKey: ["twins"],
    queryFn: async () => {
      const data = await fetchDashboardSummary()
      return data.approver_profiles
    },
    refetchInterval: 60_000,
  })
}
