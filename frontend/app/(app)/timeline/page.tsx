"use client"

import * as React from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { Search, Activity } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { fetchDeals } from "@/lib/api"
import { PageHeader } from "@/components/shared/PageHeader"
import { EmptyState } from "@/components/shared/EmptyState"
import { TimelineView } from "@/components/timeline/TimelineView"
import { useTimeline } from "@/hooks/use-timeline"
import { Skeleton } from "@/components/ui/skeleton"
import type { Deal } from "@/types/api"

export default function TimelinePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const selectedDealId = searchParams.get("deal")

const { data: deals, isLoading: dealsLoading } = useQuery({
  queryKey: queryKeys.deals,
  queryFn: fetchDeals,
})

  // Fetch timeline for the selected deal
  const { data: timeline, isLoading: timelineLoading, error } = useTimeline(selectedDealId)

  // Handle deal selection
  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id) {
      router.push(`/timeline?deal=${id}`)
    } else {
      router.push("/timeline")
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Execution Timeline"
        description="Inspect the step-by-step LangGraph checkpoint history for any processed deal. This observability layer exposes the agentic routing and tool invocations."
        action={
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <select
              className="pl-9 pr-8 py-2 text-sm bg-background border border-border rounded-lg shadow-sm appearance-none min-w-[240px] focus:outline-none focus:ring-1 focus:ring-primary/50 text-foreground"
              value={selectedDealId || ""}
              onChange={handleSelect}
              disabled={dealsLoading}
            >
              <option value="">Select a deal to inspect...</option>
              {deals?.map((deal) => (
                <option key={deal.id} value={deal.id}>
                  {deal.customer_name} ({deal.id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>
        }
      />

      {/* Main Content Area */}
      {!selectedDealId ? (
        <EmptyState
          icon={<Activity className="w-5 h-5" />}
          title="No deal selected"
          description="Select a deal from the dropdown above to view its LangGraph execution history."
        />
      ) : timelineLoading ? (
        <div className="space-y-4 pt-4">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-[400px] w-full rounded-xl" />
        </div>
      ) : error ? (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive mt-6">
          Failed to load execution timeline for this deal. Ensure the observability API is running.
        </div>
      ) : timeline ? (
        <div className="pt-2">
          <TimelineView timeline={timeline} />
        </div>
      ) : null}
    </div>
  )
}
