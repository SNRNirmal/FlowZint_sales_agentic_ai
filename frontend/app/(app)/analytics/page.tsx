"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, 
  ComposedChart, Scatter, Line
} from "recharts"
import { 
  TrendingUp, Clock, FileCheck, RefreshCw, AlertTriangle, Activity
} from "lucide-react"
import { useAnalytics } from "@/hooks/use-analytics"
import { PageHeader } from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

function fmtCurrency(val: number): string {
  if (val === 0) return "$0"
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
    notation: "compact",
  }).format(val)
}

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-lg">
        <p className="font-semibold text-foreground mb-1">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-muted-foreground" style={{ color: entry.color }}>
            {entry.name}: <span className="font-medium">{entry.value}</span>
          </p>
        ))}
      </div>
    )
  }
  return null
}

export default function AnalyticsPage() {
  const { data, isLoading, error, refetch, isFetching } = useAnalytics()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics & Reports"
        description="Deep dive into pipeline metrics, approval bottlenecks, and AI prediction accuracy."
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} className="gap-2">
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
          <Skeleton className="h-[300px] md:col-span-2 rounded-xl" />
          <Skeleton className="h-[300px] rounded-xl" />
        </div>
      )}

      {error && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 text-sm text-destructive flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Failed to load analytics data.
          <button onClick={() => refetch()} className="underline ml-2 font-medium">Retry</button>
        </div>
      )}

      {!isLoading && !error && data && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* KPI Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <FileCheck className="w-4 h-4" />
                <h3 className="text-xs uppercase font-semibold tracking-wide">Total Deals</h3>
              </div>
              <p className="text-3xl font-bold text-foreground tabular-nums">{data.total_deals}</p>
            </div>
            
            <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <Activity className="w-4 h-4" />
                <h3 className="text-xs uppercase font-semibold tracking-wide">Total Approvals</h3>
              </div>
              <p className="text-3xl font-bold text-foreground tabular-nums">{data.total_approvals}</p>
            </div>

            <div className="bg-card border border-border rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <Clock className="w-4 h-4" />
                <h3 className="text-xs uppercase font-semibold tracking-wide">Avg Cycle Time</h3>
              </div>
              <p className="text-3xl font-bold text-foreground tabular-nums">
                {data.avg_cycle_days != null ? `${data.avg_cycle_days}d` : "—"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Approval Funnel */}
            <div className="bg-card border border-border rounded-xl p-5 shadow-sm lg:col-span-2">
              <h3 className="text-sm font-semibold text-foreground mb-4">Approval Funnel</h3>
              <div className="h-[250px] w-full">
                {data.approval_funnel.total > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        { name: "Pending", value: data.approval_funnel.pending },
                        { name: "Sent", value: data.approval_funnel.sent },
                        { name: "Approved", value: data.approval_funnel.approved },
                        { name: "Rejected", value: data.approval_funnel.rejected },
                        { name: "Escalated", value: data.approval_funnel.escalated },
                      ]}
                      margin={{ top: 10, right: 10, bottom: 20, left: -20 }}
                    >
                      <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--accent)" }} />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        <Cell fill="#3b82f6" /> {/* Pending - Blue */}
                        <Cell fill="#8b5cf6" /> {/* Sent - Purple */}
                        <Cell fill="#10b981" /> {/* Approved - Green */}
                        <Cell fill="#ef4444" /> {/* Rejected - Red */}
                        <Cell fill="#f59e0b" /> {/* Escalated - Amber */}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
                    No approvals recorded yet.
                  </div>
                )}
              </div>
            </div>

            {/* Revenue by Status */}
            <div className="bg-card border border-border rounded-xl p-5 shadow-sm flex flex-col">
              <h3 className="text-sm font-semibold text-foreground mb-4">Pipeline Revenue</h3>
              <div className="space-y-4 flex-1 flex flex-col justify-center">
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground uppercase font-semibold">Active</span>
                    <span className="font-medium text-foreground">{fmtCurrency(data.revenue_by_status.active)}</span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div className="bg-emerald-500 h-2 rounded-full" style={{ width: "100%" }} />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground uppercase font-semibold">Stalled</span>
                    <span className="font-medium text-foreground">{fmtCurrency(data.revenue_by_status.stalled)}</span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div className="bg-red-500 h-2 rounded-full" style={{ width: "100%" }} />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground uppercase font-semibold">Closed</span>
                    <span className="font-medium text-foreground">{fmtCurrency(data.revenue_by_status.closed)}</span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: "100%" }} />
                  </div>
                </div>
              </div>
            </div>
            
            {/* AI Prediction Accuracy (Predicted vs Actual) */}
            <div className="bg-card border border-border rounded-xl p-5 shadow-sm lg:col-span-3">
              <h3 className="text-sm font-semibold text-foreground mb-4">AI Prediction Accuracy (Predicted vs Actual Delay)</h3>
              <div className="h-[250px] w-full">
                {data.predicted_vs_actual.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={data.predicted_vs_actual}
                      margin={{ top: 10, right: 10, bottom: 20, left: -20 }}
                    >
                      <XAxis dataKey="department" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="actual" name="Actual Delay (days)" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
                      <Scatter dataKey="predicted" name="Predicted Delay (days)" fill="#f59e0b" />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
                    Not enough completed deals to evaluate accuracy.
                  </div>
                )}
              </div>
            </div>

          </div>
        </motion.div>
      )}
    </div>
  )
}
