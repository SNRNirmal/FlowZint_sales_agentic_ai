"use client"

import * as React from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Briefcase, RefreshCw } from "lucide-react"
import { useDeals } from "@/hooks/use-deals"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { PageHeader } from "@/components/shared/PageHeader"
import { EmptyState } from "@/components/shared/EmptyState"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { getMomentumColor } from "@/lib/momentum"
import type { Deal } from "@/types/deal"

function fmt(val: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(val)
}

function DealRow({ deal, index }: { deal: Deal; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
    >
      <Link
        href={`/deals/${deal.id}`}
        className="flex items-center gap-4 px-4 py-3.5 rounded-xl border border-border bg-card hover:border-primary/40 hover:bg-accent transition-all group"
      >
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Briefcase className="w-4 h-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-3 gap-1">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{deal.customer_name}</p>
            <p className="text-xs text-muted-foreground capitalize">{deal.stage.replace(/_/g, " ")}</p>
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-medium text-foreground">{fmt(deal.value)}</p>
            <p className="text-xs text-muted-foreground">{deal.discount_percent}% discount · {deal.product_type}</p>
          </div>
          <div className="hidden sm:flex items-center gap-3">
            <StatusBadge status={deal.status} />
            <span className="text-xs text-muted-foreground">{deal.customer_segment}</span>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <div className="text-right">
            <p className="text-sm font-bold tabular-nums" style={{ color: getMomentumColor(deal.momentum_score) }}>
              {deal.momentum_score}
            </p>
            <p className="text-xs text-muted-foreground">score</p>
          </div>
          <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </Link>
    </motion.div>
  )
}

export default function DealsPage() {
  const { data: deals, isLoading, error, refetch, isFetching } = useDeals()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Deals"
        description="All deals tracked by Threshold across your pipeline."
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {isLoading && (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-[68px] w-full rounded-xl" />)}
        </div>
      )}

      {/* A failed background poll sets `error` while cached `data` survives.
          Error and content render independently so a hiccup never blanks an
          already-rendered list. */}
      {deals && deals.length > 0 && (
        <div className="space-y-2">
          {deals.map((deal, i) => <DealRow key={deal.id} deal={deal} index={i} />)}
        </div>
      )}

      {/* Only claim "no deals" for a loaded empty list — never when data is
          merely unavailable. */}
      {!isLoading && !error && deals && deals.length === 0 && (
        <EmptyState
          icon={<Briefcase className="w-5 h-5" />}
          title="No deals yet"
          description="Trigger a deal via the Human Review page to see it appear here."
          action={
            <Button asChild size="sm" variant="outline">
              <Link href="/review">Go to Review Queue</Link>
            </Button>
          }
        />
      )}

      {error && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive">
          Failed to load deals.{" "}
          <button onClick={() => refetch()} className="underline">Retry</button>
        </div>
      )}
    </div>
  )
}
