"use client"

import { Brain, Activity, TrendingUp, AlertTriangle } from "lucide-react"
import type { BehavioralTwin } from "@/types/api"
import { getApproverDisplay } from "@/lib/approver-names"

// Pinned locale so server and client render identically, with a graceful
// fallback instead of the stringified "Invalid Date".
function formatUpdated(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? "recently"
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

export function ApproverCard({ twin }: { twin: BehavioralTwin }) {
  const display = getApproverDisplay(twin.approver_id)

  // Confidence calculation (20 deals = 100%)
  const confidence = Math.min(100, Math.round((twin.total_deals_reviewed / 20) * 100))
  
  // Risk banding
  const delay = twin.avg_turnaround_days
  const riskLabel = delay >= 6 ? "HIGH RISK" : delay >= 3 ? "MEDIUM RISK" : "LOW RISK"
  const riskColor = 
    delay >= 6 ? "text-red-400 bg-red-500/10 border-red-500/20"
    : delay >= 3 ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
    : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"

  return (
    <div className="bg-card border border-border rounded-xl p-5 hover:border-primary/30 transition-colors flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{display.label}</p>
            <p className="text-xs text-muted-foreground">{display.department}</p>
          </div>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold tracking-wider shrink-0 ${riskColor}`}>
          {riskLabel}
        </span>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="p-3 bg-background rounded-lg border border-border">
          <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
            <Activity className="w-3.5 h-3.5" />
            <span className="text-xs uppercase tracking-wide">Avg Delay</span>
          </div>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {twin.avg_turnaround_days} <span className="text-sm font-normal text-muted-foreground">days</span>
          </p>
        </div>
        <div className="p-3 bg-background rounded-lg border border-border">
          <div className="flex items-center gap-1.5 mb-1 text-muted-foreground">
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="text-xs uppercase tracking-wide">Deals</span>
          </div>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {twin.total_deals_reviewed}
          </p>
        </div>
      </div>

      {/* Behavioral Patterns */}
      <div className="space-y-3 mb-6 flex-1">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Fastest Format</p>
          <p className="text-sm font-medium text-foreground">{twin.fastest_responding_format}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Slowdown Trigger</p>
          <div className="flex items-start gap-2 text-sm text-amber-400">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-medium">{twin.slowest_trigger}</span>
          </div>
        </div>
      </div>

      {/* Footer: Learning Progress */}
      <div className="mt-auto pt-4 border-t border-border">
        <div className="flex items-center justify-between mb-1.5 text-xs">
          <span className="text-muted-foreground">Twin Confidence</span>
          <span className="font-medium text-foreground">{confidence}%</span>
        </div>
        <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
          <div 
            className="h-full bg-primary rounded-full transition-all duration-500" 
            style={{ width: `${confidence}%` }}
          />
        </div>
        <p className="text-[10px] text-muted-foreground mt-2 text-right">
          Last updated {formatUpdated(twin.last_updated)}
        </p>
      </div>
    </div>
  )
}
