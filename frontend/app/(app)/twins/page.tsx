"use client"

import { Brain, RefreshCw, Activity, CheckCircle2, AlertTriangle } from "lucide-react"
import { useTwins } from "@/hooks/use-twins"
import { ApproverCard } from "@/components/twins/ApproverCard"
import { PageHeader } from "@/components/shared/PageHeader"
import { EmptyState } from "@/components/shared/EmptyState"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function TwinsPage() {
  const { data: twins, isLoading, error, refetch, isFetching } = useTwins()

  // Derived aggregate metrics
  const avgTurnaround = twins && twins.length > 0 
    ? (twins.reduce((sum, t) => sum + t.avg_turnaround_days, 0) / twins.length).toFixed(1) 
    : "—"
  
  const highConfidenceCount = twins?.filter(t => t.total_deals_reviewed >= 20).length ?? 0
  const totalReviews = twins?.reduce((sum, t) => sum + t.total_deals_reviewed, 0) ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Behavioral Twins"
        description="Live AI models predicting internal approver behavior. The Learning Agent continuously updates these profiles after every resolved deal."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} className="gap-2">
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh Models
          </Button>
        }
      />

      {/* Aggregate Intelligence Header */}
      {!isLoading && !error && twins && twins.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">High Confidence Models</p>
              <p className="text-xl font-bold text-foreground">
                {highConfidenceCount} <span className="text-sm font-normal text-muted-foreground">/ {twins.length}</span>
              </p>
            </div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Activity className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Enterprise Avg Delay</p>
              <p className="text-xl font-bold tabular-nums text-foreground">
                {avgTurnaround} <span className="text-sm font-normal text-muted-foreground">days</span>
              </p>
            </div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
              <Brain className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Decisions Learned</p>
              <p className="text-xl font-bold tabular-nums text-foreground">{totalReviews}</p>
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-64 rounded-xl" />)}
        </div>
      )}

      {error && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Failed to load twin models from the intelligence engine.
          <button onClick={() => refetch()} className="underline ml-2 font-medium">Retry connection</button>
        </div>
      )}

      {twins && twins.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Sort: slowest models (highest delay) first to highlight bottlenecks */}
          {[...twins]
            .sort((a, b) => b.avg_turnaround_days - a.avg_turnaround_days)
            .map((twin) => (
              <ApproverCard key={twin.approver_id} twin={twin} />
            ))}
        </div>
      )}

      {!isLoading && !error && twins && twins.length === 0 && (
        <EmptyState
          icon={<Brain className="w-5 h-5" />}
          title="No models deployed"
          description="The intelligence engine requires initial seed data. Run backend/behavioral_twins/seed_data.py to bootstrap the models."
        />
      )}
    </div>
  )
}
