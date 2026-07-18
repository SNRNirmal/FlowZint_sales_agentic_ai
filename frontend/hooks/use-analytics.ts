import { useQuery } from "@tanstack/react-query"
import { fetchAnalytics } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useAnalytics() {
  return useQuery({
    queryKey: queryKeys.analytics,
    queryFn: fetchAnalytics,
    staleTime: 60000,
  })
}
