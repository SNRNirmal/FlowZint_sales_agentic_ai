"use client"

import { Brain } from "lucide-react"
import type { BehavioralTwin } from "@/types/twin"

// Pinned locale so server and client render identically, with a graceful
// fallback instead of the stringified "Invalid Date".
function formatUpdated(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? "recently"
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

export function ApproverCard({ twin }: { twin: BehavioralTwin }) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 hover:border-primary/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate">{twin.approver_id}</p>
          <p className="text-xs text-muted-foreground">{twin.department}</p>
        </div>
      </div>

      <div className="mt-4 space-y-1.5 text-sm">
        <p className="text-foreground">
          Avg turnaround: <strong className="tabular-nums">{twin.avg_turnaround_days} days</strong>
        </p>
        <p className="text-muted-foreground">Responds fastest to: {twin.fastest_responding_format}</p>
        <p className="text-muted-foreground">Slows down on: {twin.slowest_trigger}</p>
      </div>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <span>{twin.total_deals_reviewed} deals reviewed</span>
        <span>Updated {formatUpdated(twin.last_updated)}</span>
      </div>
    </div>
  )
}
