"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  DollarSign,
  Clock,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
  RefreshCw,
  ClipboardCheck,
} from "lucide-react"
import Link from "next/link"
import { useDashboard } from "@/hooks/use-dashboard"
import { usePendingApprovals } from "@/hooks/use-pending-approvals"
import { StatCard } from "@/components/dashboard/StatCard"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { RecentDeals } from "@/components/dashboard/RecentDeals"
import { BottleneckChart } from "@/components/dashboard/BottleneckChart"
import { PipelineDonut } from "@/components/dashboard/PipelineDonut"
import { AttentionTable } from "@/components/dashboard/AttentionTable"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuthStore } from "@/store/useAuthStore"

// Formats a number as compact USD currency: 1_500_000 → "$1.5M"
function fmtCurrency(val: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
    notation: "compact",
  }).format(val)
}

export default function DashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useDashboard()
  const { data: pending } = usePendingApprovals()
  const user = useAuthStore((s) => s.user)

  const deals = data?.deals ?? []
  const twins = data?.approver_profiles ?? []
  const avgScore = data?.avg_momentum_score

  // ── Business metrics derived from real API data ─────────────────────────
  // Revenue at Risk: sum of deal values where momentum < 70 OR status stalled.
  const revenueAtRisk = deals
    .filter((d) => d.momentum_score < 70 || d.status === "stalled")
    .reduce((sum, d) => sum + d.value, 0)

  // Pending Approval Value: sum of deal values that have at least one pending approval.
  const pendingDealIds = new Set(pending?.map((p) => p.deal.id) ?? [])
  const pendingApprovalValue = deals
    .filter((d) => pendingDealIds.has(d.id))
    .reduce((sum, d) => sum + d.value, 0)

  // Average Approval Time across all behavioral twins (learned from real history).
  const avgApprovalTime =
    twins.length > 0
      ? (twins.reduce((sum, t) => sum + t.avg_turnaround_days, 0) / twins.length).toFixed(1)
      : null

  return (
    <div className="space-y-6">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Good morning, {user?.name?.split(" ")[0] ?? "there"}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Revenue intelligence across your approval pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-muted-foreground"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button asChild size="sm">
            <Link href="/review">
              Review Queue
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Link>
          </Button>
        </div>
      </motion.div>

      {/* KPI cards row — all business metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          index={0}
          label="Revenue at Risk"
          value={isLoading ? "—" : (deals.length > 0 ? fmtCurrency(revenueAtRisk) : "Unavailable")}
          icon={<DollarSign className="w-4 h-4" />}
          delta={
            isLoading ? undefined
            : deals.length > 0
              ? `${deals.filter((d) => d.momentum_score < 70 || d.status === "stalled").length} deals`
              : undefined
          }
          deltaType={revenueAtRisk > 0 ? "negative" : "positive"}
        />
        <StatCard
          index={1}
          label="Pending Approval Value"
          value={isLoading ? "—" : (deals.length > 0 ? fmtCurrency(pendingApprovalValue) : "Unavailable")}
          icon={<ClipboardCheck className="w-4 h-4" />}
          delta={
            pending != null
              ? `${pending.length} approval${pending.length !== 1 ? "s" : ""} waiting`
              : undefined
          }
          deltaType={(pending?.length ?? 0) > 0 ? "negative" : "positive"}
        />
        <StatCard
          index={2}
          label="Avg Approval Time"
          value={isLoading ? "—" : (avgApprovalTime != null ? `${avgApprovalTime}d` : "Unavailable")}
          icon={<Clock className="w-4 h-4" />}
          delta={twins.length > 0 ? `across ${twins.length} approvers` : undefined}
          deltaType="neutral"
        />
        <StatCard
          index={3}
          label="Portfolio Momentum"
          value={isLoading ? "—" : (avgScore ?? "Unavailable")}
          icon={<TrendingUp className="w-4 h-4" />}
          delta="avg across all deals"
          deltaType={avgScore != null ? (avgScore >= 80 ? "positive" : avgScore >= 50 ? "neutral" : "negative") : "neutral"}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — deals needing attention + recent deals */}
        <div className="lg:col-span-2 space-y-6">
          {/* Deals needing attention */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-foreground">Requires Attention</h2>
              </div>
              <Button variant="ghost" size="sm" asChild className="text-xs text-muted-foreground h-7">
                <Link href="/deals">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
              </Button>
            </div>
            {isLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-11 w-full rounded-lg" />)}
              </div>
            ) : (
              <AttentionTable deals={deals} />
            )}
          </div>

          {/* Recent deals */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">Recent Deals</h2>
              <Button variant="ghost" size="sm" asChild className="text-xs text-muted-foreground h-7">
                <Link href="/deals">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
              </Button>
            </div>
            <RecentDeals deals={deals} isLoading={isLoading} />
            {!isLoading && !error && deals.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-sm text-muted-foreground">No deals yet.</p>
                <Button asChild size="sm" className="mt-3" variant="outline">
                  <Link href="/review">Run a deal</Link>
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Portfolio momentum gauge */}
          <div className="bg-card border border-border rounded-xl p-5 flex flex-col items-center gap-2">
            <div className="w-full flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-foreground">Portfolio Momentum</h2>
            </div>
            {isLoading ? (
              <Skeleton className="w-32 h-32 rounded-full" />
            ) : avgScore != null ? (
              <MomentumGauge score={avgScore} label="Average across all deals" size="lg" />
            ) : (
              <p className="text-sm text-muted-foreground py-8">No momentum data available.</p>
            )}
          </div>

          {/* Pipeline health donut */}
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Pipeline Health</h2>
            {isLoading ? (
              <Skeleton className="w-full h-[180px] rounded-lg" />
            ) : (
              <PipelineDonut deals={deals} />
            )}
          </div>

          {/* Department bottleneck chart */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">Dept Bottlenecks</h2>
              <Button variant="ghost" size="sm" asChild className="text-xs text-muted-foreground h-7">
                <Link href="/twins">View twins <ArrowRight className="w-3 h-3 ml-1" /></Link>
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
              Average approval days per department
            </p>
            {isLoading ? (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full rounded" />)}
              </div>
            ) : (
              <BottleneckChart twins={twins} />
            )}
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive">
          Failed to load dashboard data. The backend may be offline.{" "}
          <button onClick={() => refetch()} className="underline ml-1">Retry</button>
        </div>
      )}
    </div>
  )
}
