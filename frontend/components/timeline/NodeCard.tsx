import * as React from "react"
import { motion } from "framer-motion"
import { Activity, Clock, FileCheck, CheckCircle2, AlertTriangle, PauseCircle, SkipForward } from "lucide-react"
import type { NodeTransition } from "@/types/api"

interface NodeCardProps {
  transition: NodeTransition
  index: number
  isLast: boolean
}

// Maps node names to user-friendly labels and icons.
const NODE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  __start__: {
    label: "Pipeline Started",
    icon: <Activity className="w-4 h-4" />,
    color: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  },
  approval_detection: {
    label: "Approval Detection Reasoning",
    icon: <CheckCircle2 className="w-4 h-4" />,
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  behavioral_twin_retrieval: {
    label: "Behavioral Twin Retrieval",
    icon: <Activity className="w-4 h-4" />,
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  },
  communication_planning: {
    label: "Communication Strategy",
    icon: <FileCheck className="w-4 h-4" />,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  },
  artifact_generation: {
    label: "Artifact Generation",
    icon: <FileCheck className="w-4 h-4" />,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  },
  nudge_drafting: {
    label: "Nudge Drafting",
    icon: <FileCheck className="w-4 h-4" />,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  },
  human_review: {
    label: "Human Review",
    icon: <AlertTriangle className="w-4 h-4" />,
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  action_dispatch: {
    label: "Action Dispatch",
    icon: <CheckCircle2 className="w-4 h-4" />,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
}

export function NodeCard({ transition, index, isLast }: NodeCardProps) {
  const cfg = NODE_CONFIG[transition.node_name] || {
    label: transition.node_name,
    icon: <Activity className="w-4 h-4" />,
    color: "text-muted-foreground bg-muted border-border",
  }

  // Determine status layout based on the transition properties
  let statusBadge = null
  if (transition.is_interrupt) {
    statusBadge = (
      <span className="flex items-center gap-1 text-[10px] uppercase font-semibold tracking-wider text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full">
        <PauseCircle className="w-3 h-3" /> Paused
      </span>
    )
  } else if (transition.is_resume) {
    statusBadge = (
      <span className="flex items-center gap-1 text-[10px] uppercase font-semibold tracking-wider text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
        <SkipForward className="w-3 h-3" /> Resumed
      </span>
    )
  } else if (transition.human_action) {
    statusBadge = (
      <span className="flex items-center gap-1 text-[10px] uppercase font-semibold tracking-wider text-blue-500 bg-blue-500/10 px-2 py-0.5 rounded-full">
        {transition.human_action}
      </span>
    )
  } else if (transition.node_name !== "__start__") {
    statusBadge = (
      <span className="flex items-center gap-1 text-[10px] uppercase font-semibold tracking-wider text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
        <CheckCircle2 className="w-3 h-3" /> Complete
      </span>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className="relative flex gap-4"
    >
      {/* Timeline line connecting nodes */}
      {!isLast && (
        <div className="absolute left-[19px] top-10 bottom-[-16px] w-px bg-border" />
      )}

      {/* Icon node */}
      <div className={`w-10 h-10 rounded-full border flex items-center justify-center shrink-0 z-10 ${cfg.color}`}>
        {cfg.icon}
      </div>

      {/* Card Content */}
      <div className="flex-1 bg-card border border-border rounded-xl p-4 shadow-sm mb-4 transition-colors hover:border-primary/30">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h4 className="text-sm font-semibold text-foreground">{cfg.label}</h4>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-xs text-muted-foreground font-mono">
                {transition.checkpoint_id.slice(0, 8)}…
              </span>
              <span className="text-muted-foreground text-xs">•</span>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(transition.timestamp).toLocaleTimeString()}
              </span>
            </div>
          </div>
          <div className="shrink-0">{statusBadge}</div>
        </div>
      </div>
    </motion.div>
  )
}
