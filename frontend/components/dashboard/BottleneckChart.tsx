"use client"

import * as React from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts"
import type { BehavioralTwin } from "@/types/api"

interface BottleneckChartProps {
  twins: BehavioralTwin[]
}

// Color bands matching momentum thresholds — red for slow, green for fast.
function barColor(days: number): string {
  if (days >= 6) return "#ef4444"   // red — high delay
  if (days >= 3) return "#f59e0b"   // amber — medium
  return "#22c55e"                   // green — fast
}

interface TooltipPayloadEntry {
  payload: BehavioralTwin & { avg_turnaround_days: number }
  value: number
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: TooltipPayloadEntry[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-foreground">{d.department}</p>
      <p className="text-muted-foreground mt-0.5">
        Avg turnaround: <span className="font-medium text-foreground">{d.avg_turnaround_days}d</span>
      </p>
      <p className="text-muted-foreground">{d.total_deals_reviewed} deals reviewed</p>
    </div>
  )
}

export function BottleneckChart({ twins }: BottleneckChartProps) {
  if (!twins.length) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No approver data available. Seed behavioral twins to see department delays.
      </p>
    )
  }

  // Sort slowest first so the most critical departments are most visible.
  const sorted = [...twins].sort((a, b) => b.avg_turnaround_days - a.avg_turnaround_days)

  return (
    <ResponsiveContainer width="100%" height={sorted.length * 44 + 16}>
      <BarChart
        data={sorted}
        layout="vertical"
        margin={{ top: 0, right: 48, bottom: 0, left: 0 }}
        barCategoryGap="30%"
      >
        <XAxis
          type="number"
          dataKey="avg_turnaround_days"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickFormatter={(v) => `${v}d`}
          domain={[0, "auto"]}
        />
        <YAxis
          type="category"
          dataKey="department"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: "hsl(var(--foreground))" }}
          width={96}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--accent))" }} />
        <Bar dataKey="avg_turnaround_days" radius={[0, 4, 4, 0]}>
          {sorted.map((entry) => (
            <Cell key={entry.approver_id} fill={barColor(entry.avg_turnaround_days)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
