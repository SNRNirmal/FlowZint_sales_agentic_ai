"use client"

import * as React from "react"
import { use } from "react"
import { motion } from "framer-motion"
import Link from "next/link"
import {
  ArrowLeft, DollarSign, Tag, Building, GitBranch,
  ClipboardCheck, Clock, CheckCircle2, XCircle, Send
} from "lucide-react"
import { useDeal } from "@/hooks/use-deals"
import { StatusBadge } from "@/components/shared/StatusBadge"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import type { Approval } from "@/types/deal"

function fmt(val: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(val)
}

function MetaItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-7 h-7 rounded-md bg-muted flex items-center justify-center text-muted-foreground shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium text-foreground capitalize">{value}</p>
      </div>
    </div>
  )
}

function ApprovalRow({ approval, index }: { approval: Approval; index: number }) {
  const statusIcon = {
    approved: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
    rejected: <XCircle className="w-4 h-4 text-red-400" />,
    sent: <Send className="w-4 h-4 text-blue-400" />,
    pending: <Clock className="w-4 h-4 text-amber-400" />,
  }[approval.status] ?? <Clock className="w-4 h-4 text-muted-foreground" />

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card/50"
    >
      {statusIcon}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{approval.approver_id}</p>
        <p className="text-xs text-muted-foreground">{approval.department}</p>
      </div>
      <div className="text-right">
        {approval.predicted_delay_days != null && (
          <p className="text-xs text-amber-400">{approval.predicted_delay_days}d predicted delay</p>
        )}
        {approval.actual_delay_days != null && (
          <p className="text-xs text-muted-foreground">{approval.actual_delay_days}d actual</p>
        )}
      </div>
      <StatusBadge status={approval.status} />
    </motion.div>
  )
}

export default function DealDetailPage({ params }: { params: Promise<{ dealId: string }> }) {
  const { dealId } = use(params)
  const { data, isLoading, error } = useDeal(dealId)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-6 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive">
        Deal not found or failed to load.
      </div>
    )
  }

  const { deal, approvals } = data

  return (
    <div className="space-y-6">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild className="mt-0.5 shrink-0">
          <Link href="/deals"><ArrowLeft className="w-4 h-4" /></Link>
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-foreground truncate">
              {deal.customer_name}
            </h1>
            <StatusBadge status={deal.status} />
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">Deal ID: {deal.id}</p>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Deal metadata */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Deal Overview</h2>
            <div className="grid grid-cols-2 gap-4">
              <MetaItem icon={<DollarSign className="w-3.5 h-3.5" />} label="Value" value={fmt(deal.value)} />
              <MetaItem icon={<Tag className="w-3.5 h-3.5" />} label="Discount" value={`${deal.discount_percent}%`} />
              <MetaItem icon={<Building className="w-3.5 h-3.5" />} label="Segment" value={deal.customer_segment} />
              <MetaItem icon={<GitBranch className="w-3.5 h-3.5" />} label="Stage" value={deal.stage.replace(/_/g, " ")} />
            </div>
          </div>

          {/* Approvals */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground">Approval Chain</h2>
              <span className="text-xs text-muted-foreground">{approvals.length} approver{approvals.length !== 1 ? "s" : ""}</span>
            </div>
            {approvals.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">No approvals generated yet.</p>
            ) : (
              <div className="space-y-2">
                {approvals.map((a, i) => <ApprovalRow key={a.id} approval={a} index={i} />)}
              </div>
            )}
          </div>
        </div>

        {/* Momentum sidebar */}
        <div className="bg-card border border-border rounded-xl p-5 flex flex-col items-center gap-4 h-fit">
          <h2 className="text-sm font-semibold text-foreground w-full">Momentum Score</h2>
          <MomentumGauge score={deal.momentum_score} size="lg" />
          <Separator className="w-full" />
          <div className="w-full space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Product type</span>
              <span className="text-foreground capitalize">{deal.product_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Approvals</span>
              <span className="text-foreground">{approvals.filter(a => a.status === "approved").length}/{approvals.length}</span>
            </div>
          </div>
          <Button asChild variant="outline" size="sm" className="w-full gap-2">
            <Link href="/review">
              <ClipboardCheck className="w-3.5 h-3.5" />
              Open in Review Queue
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
