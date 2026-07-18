"use client"

import * as React from "react"
import { Briefcase } from "lucide-react"
import { getMomentumColor } from "@/lib/momentum"

interface DealContextBannerProps {
  customerName: string
  value: string
  productType: string
  customerSegment: string
  momentumScore: number | null
  totalApprovals: number
}

function fmtCurrency(val: string): string {
  const n = Number(val)
  if (!Number.isFinite(n)) return val
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n)
}

export function DealContextBanner({
  customerName,
  value,
  productType,
  customerSegment,
  momentumScore,
  totalApprovals,
}: DealContextBannerProps) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-between gap-4 sticky top-4 z-10 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Briefcase className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-foreground">
            {customerName || "Unknown Customer"}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {fmtCurrency(value)} · {customerSegment} · {productType}
          </p>
        </div>
      </div>
      
      <div className="flex items-center gap-6">
        <div className="text-right hidden sm:block">
          <p className="text-xs text-muted-foreground mb-0.5">Momentum</p>
          <p 
            className="text-sm font-bold tabular-nums"
            style={{ color: momentumScore != null ? getMomentumColor(momentumScore) : undefined }}
          >
            {momentumScore ?? "—"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground mb-0.5">Approvals</p>
          <p className="text-sm font-medium text-foreground">
            {totalApprovals} Required
          </p>
        </div>
      </div>
    </div>
  )
}
