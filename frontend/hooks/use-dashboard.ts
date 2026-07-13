import { useQuery } from "@tanstack/react-query"
import { fetchDashboardSummary } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useDashboard() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: fetchDashboardSummary,
    refetchInterval: 30_000,
  })
}
