"use client"

import * as React from "react"
import { motion } from "framer-motion"
import type { BehavioralTwin } from "@/types/twin"
import { Brain, Clock, FileText, AlertTriangle } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

interface ActivityFeedProps {
  twins: BehavioralTwin[]
  isLoading?: boolean
}

export function ActivityFeed({ twins, isLoading }: ActivityFeedProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-lg" />)}
      </div>
    )
  }

  if (!twins.length) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-muted-foreground">No behavioral data yet. Run a deal to begin learning.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {twins.slice(0, 5).map((twin, i) => (
        <motion.div
          key={twin.approver_id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: i * 0.06 }}
          className="flex items-start gap-3 p-3 rounded-lg border border-border bg-card/50"
        >
          <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
            <Brain className="w-3.5 h-3.5 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-foreground">
                {twin.approver_id} <span className="text-muted-foreground font-normal">· {twin.department}</span>
              </p>
              <span className="text-xs text-muted-foreground whitespace-nowrap">{twin.total_deals_reviewed} reviews</span>
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="w-3 h-3" />
                {twin.avg_turnaround_days}d avg
              </span>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <FileText className="w-3 h-3" />
                {twin.fastest_responding_format}
              </span>
            </div>
            {twin.slowest_trigger && (
              <div className="flex items-center gap-1 mt-1">
                <AlertTriangle className="w-3 h-3 text-amber-400" />
                <span className="text-xs text-amber-400">{twin.slowest_trigger}</span>
              </div>
            )}
          </div>
        </motion.div>
      ))}
    </div>
  )
}
