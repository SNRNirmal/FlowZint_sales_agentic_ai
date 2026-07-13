"use client"

import { Brain, RefreshCw } from "lucide-react"
import { useTwins } from "@/hooks/use-twins"
import { ApproverCard } from "@/components/twins/ApproverCard"
import { PageHeader } from "@/components/shared/PageHeader"
import { EmptyState } from "@/components/shared/EmptyState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function TwinsPage() {
  const { data: twins, isLoading, error, refetch, isFetching } = useTwins()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Behavioral Twins"
        description="Live profiles per internal approver, updated by the Learning Agent after every resolved approval."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} className="gap-2">
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      )}

      {/* A failed background poll sets `error` while cached `data` survives.
          Error and content render independently so a hiccup never blanks an
          already-rendered grid. */}
      {error && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive">
          Failed to load twins.{" "}
          <button onClick={() => refetch()} className="underline">Retry</button>
        </div>
      )}

      {twins && twins.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {twins.map((twin) => <ApproverCard key={twin.approver_id} twin={twin} />)}
        </div>
      )}

      {/* "No twins seeded" is a diagnosis, so only claim it for a loaded
          empty list — never when data is merely unavailable. */}
      {!isLoading && !error && twins && twins.length === 0 && (
        <EmptyState
          icon={<Brain className="w-5 h-5" />}
          title="No twins seeded"
          description="Run backend/behavioral_twins/seed_data.py to seed the demo approver profiles."
        />
      )}
    </div>
  )
}
