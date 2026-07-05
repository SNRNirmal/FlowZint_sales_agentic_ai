"use client"

import * as React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"
import type { Deal } from "@/types/deal"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { MomentumGauge } from "./MomentumGauge"
import { getMomentumColor } from "@/lib/momentum"
import { Skeleton } from "@/components/ui/skeleton"

interface RecentDealsProps {
  deals: Deal[]
  isLoading?: boolean
}

function fmt(val: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(val)
}

export function RecentDeals({ deals, isLoading }: RecentDealsProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {deals.slice(0, 6).map((deal, i) => (
        <motion.div
          key={deal.id}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.25, delay: i * 0.04 }}
        >
          <Link
            href={`/deals/${deal.id}`}
            className="flex items-center gap-4 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{deal.customer_name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {fmt(deal.value)} · {deal.stage.replace(/_/g, " ")}
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <div className="text-right">
                <span
                  className="text-sm font-bold tabular-nums"
                  style={{ color: getMomentumColor(deal.momentum_score) }}
                >
                  {deal.momentum_score}
                </span>
              </div>
              <StatusBadge status={deal.status} />
              <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </Link>
        </motion.div>
      ))}
    </div>
  )
}
