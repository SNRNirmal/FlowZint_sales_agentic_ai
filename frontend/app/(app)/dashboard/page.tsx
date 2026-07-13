"use client"

import * as React from "react"
import { motion } from "framer-motion"
import {
  Briefcase,
  ClipboardCheck,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
  RefreshCw,
} from "lucide-react"
import Link from "next/link"
import { useDashboard } from "@/hooks/use-dashboard"
import { usePendingApprovals } from "@/hooks/use-pending-approvals"
import { StatCard } from "@/components/dashboard/StatCard"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { RecentDeals } from "@/components/dashboard/RecentDeals"
import { ActivityFeed } from "@/components/dashboard/ActivityFeed"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuthStore } from "@/store/useAuthStore"

export default function DashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useDashboard()
  const { data: pending } = usePendingApprovals()
  const user = useAuthStore((s) => s.user)

  const totalDeals = data?.total_deals ?? 0
  const stalledDeals = data?.stalled_deals ?? 0
  const avgScore = data?.avg_momentum_score ?? 0
  const deals = data?.deals ?? []
  const twins = data?.approver_profiles ?? []

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
            Here&apos;s what Threshold is tracking right now.
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

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          index={0}
          label="Active Deals"
          value={isLoading ? "—" : totalDeals}
          icon={<Briefcase className="w-4 h-4" />}
          delta="All pipeline"
          deltaType="neutral"
        />
        <StatCard
          index={1}
          label="Pending Approvals"
          value={pending ? pending.length : "—"}
          icon={<ClipboardCheck className="w-4 h-4" />}
          delta="Awaiting review"
          deltaType={(pending?.length ?? 0) > 0 ? "negative" : "positive"}
        />
        <StatCard
          index={2}
          label="Stalled Deals"
          value={isLoading ? "—" : stalledDeals}
          icon={<AlertTriangle className="w-4 h-4" />}
          delta={stalledDeals > 0 ? "Needs attention" : "Clear"}
          deltaType={stalledDeals > 0 ? "negative" : "positive"}
        />
        <StatCard
          index={3}
          label="Avg Momentum"
          value={isLoading ? "—" : avgScore}
          icon={<TrendingUp className="w-4 h-4" />}
          delta="Portfolio score"
          deltaType={avgScore >= 80 ? "positive" : avgScore >= 50 ? "neutral" : "negative"}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent deals — 2 cols */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-foreground">Recent Deals</h2>
            <Button variant="ghost" size="sm" asChild className="text-xs text-muted-foreground h-7">
              <Link href="/deals">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
            </Button>
          </div>
          <RecentDeals deals={deals} isLoading={isLoading} />
          {!isLoading && !deals.length && (
            <div className="py-8 text-center">
              <p className="text-sm text-muted-foreground">No deals yet.</p>
              <Button asChild size="sm" className="mt-3" variant="outline">
                <Link href="/review">Simulate a deal</Link>
              </Button>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Momentum gauge card */}
          <div className="bg-card border border-border rounded-xl p-5 flex flex-col items-center gap-2">
            <div className="w-full flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-foreground">Portfolio Momentum</h2>
            </div>
            {isLoading ? (
              <Skeleton className="w-32 h-32 rounded-full" />
            ) : (
              <MomentumGauge score={avgScore} label="Average across all deals" size="lg" />
            )}
          </div>

          {/* Behavioral twins insight */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">Behavioral Twins</h2>
              <Button variant="ghost" size="sm" asChild className="text-xs text-muted-foreground h-7">
                <Link href="/twins">View all <ArrowRight className="w-3 h-3 ml-1" /></Link>
              </Button>
            </div>
            <ActivityFeed twins={twins} isLoading={isLoading} />
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
