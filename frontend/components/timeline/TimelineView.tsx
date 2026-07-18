"use client"

import * as React from "react"
import { Activity, Clock, CheckCircle2, AlertTriangle, Layers } from "lucide-react"
import type { DealTimeline } from "@/types/api"
import { NodeCard } from "./NodeCard"

interface TimelineViewProps {
  timeline: DealTimeline
}

export function TimelineView({ timeline }: TimelineViewProps) {
  if (!timeline.transitions || timeline.transitions.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-8 text-center text-muted-foreground">
        <Layers className="w-8 h-8 mx-auto mb-3 text-muted-foreground/50" />
        <p className="text-sm font-medium text-foreground">No Execution History</p>
        <p className="text-xs mt-1">This deal has not been processed by the pipeline yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Execution Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1 flex items-center gap-1">
            <Clock className="w-3 h-3" /> Duration
          </p>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {timeline.total_duration_ms > 0 ? `${(timeline.total_duration_ms / 1000).toFixed(2)}s` : "—"}
          </p>
        </div>
        
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1 flex items-center gap-1">
            <Layers className="w-3 h-3" /> LLM Tokens
          </p>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {timeline.total_tokens > 0 ? timeline.total_tokens.toLocaleString() : "—"}
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1 flex items-center gap-1">
            <Activity className="w-3 h-3" /> Tool Calls
          </p>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {timeline.total_tool_calls > 0 ? timeline.total_tool_calls : "—"}
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> State Resumes
          </p>
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {timeline.resume_count}
          </p>
        </div>
      </div>

      {/* Outcome Banner */}
      {timeline.final_outcome && (
        <div className={`p-4 rounded-xl border flex items-center gap-3 ${
          timeline.final_outcome.includes("ERROR") 
            ? "bg-destructive/10 border-destructive/20 text-destructive"
            : timeline.final_outcome === "PAUSED_PENDING_REVIEW"
              ? "bg-amber-500/10 border-amber-500/20 text-amber-500"
              : "bg-emerald-500/10 border-emerald-500/20 text-emerald-500"
        }`}>
          {timeline.final_outcome.includes("ERROR") ? (
            <AlertTriangle className="w-5 h-5 shrink-0" />
          ) : timeline.final_outcome === "PAUSED_PENDING_REVIEW" ? (
            <Activity className="w-5 h-5 shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 shrink-0" />
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide mb-0.5">Final Outcome</p>
            <p className="text-sm font-medium">{timeline.final_outcome}</p>
          </div>
        </div>
      )}

      {/* Node Transitions */}
      <div className="pt-4 ml-2">
        {timeline.transitions.map((transition, i) => (
          <NodeCard
            key={`${transition.checkpoint_id}-${i}`}
            transition={transition}
            index={i}
            isLast={i === timeline.transitions.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
