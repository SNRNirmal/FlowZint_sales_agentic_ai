"use client"

import * as React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, AlertTriangle } from "lucide-react"
import type { Deal } from "@/types/api"
import { getMomentumColor } from "@/lib/momentum"

interface AttentionTableProps {
  deals: Deal[]
}

function fmt(val: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
    notation: "compact",
  }).format(val)
}

function urgencyLevel(deal: Deal): "critical" | "warning" | "monitor" {
  if (deal.status === "stalled" || deal.momentum_score < 50) return "critical"
  if (deal.momentum_score < 70) return "warning"
  return "monitor"
}

const URGENCY_CONFIG = {
  critical: {
    dot: "bg-red-500",
    badge: "text-red-400 bg-red-500/10 border-red-500/20",
    label: "Stalled",
  },
  warning: {
    dot: "bg-amber-500",
    badge: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    label: "At Risk",
  },
  monitor: {
    dot: "bg-blue-500",
    badge: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    label: "Monitor",
  },
}

export function AttentionTable({ deals }: AttentionTableProps) {
  // Show deals that need attention: stalled status OR momentum score < 70.
  // Sort: critical first, then by momentum score ascending (worst first).
  const attention = deals
    .filter((d) => d.status === "stalled" || d.momentum_score < 70)
    .sort((a, b) => {
      const aLevel = urgencyLevel(a)
      const bLevel = urgencyLevel(b)
      const order = { critical: 0, warning: 1, monitor: 2 }
      if (order[aLevel] !== order[bLevel]) return order[aLevel] - order[bLevel]
      return a.momentum_score - b.momentum_score
    })

  if (!attention.length) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-emerald-400 font-medium">All deals on track</p>
        <p className="text-xs text-muted-foreground mt-1">
          No deals require immediate attention.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {attention.map((deal, i) => {
        const level = urgencyLevel(deal)
        const cfg = URGENCY_CONFIG[level]

        return (
          <motion.div
            key={deal.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.04 }}
          >
            <Link
              href={`/deals/${deal.id}`}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors group"
            >
              {/* Urgency indicator */}
              <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />

              {/* Deal info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {deal.customer_name}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {fmt(deal.value)} · {deal.stage.replace(/_/g, " ")}
                </p>
              </div>

              {/* Score + badge */}
              <div className="flex items-center gap-2.5 shrink-0">
                <span
                  className="text-sm font-bold tabular-nums"
                  style={{ color: getMomentumColor(deal.momentum_score) }}
                >
                  {deal.momentum_score}
                </span>
                <span
                  className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full border ${cfg.badge}`}
                >
                  {cfg.label}
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </Link>
          </motion.div>
        )
      })}

      {attention.length >= 5 && (
        <p className="text-xs text-muted-foreground text-center pt-2">
          Showing top {attention.length} deals needing attention
        </p>
      )}
    </div>
  )
}
