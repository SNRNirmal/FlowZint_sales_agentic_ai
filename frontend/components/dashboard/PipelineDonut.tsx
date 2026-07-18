"use client"

import * as React from "react"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts"
import type { Deal } from "@/types/api"

interface PipelineDonutProps {
  deals: Deal[]
}

const BANDS = [
  { label: "On Track",  color: "#22c55e", min: 80,  max: 100 },
  { label: "At Risk",   color: "#f59e0b", min: 50,  max: 79  },
  { label: "Stalled",   color: "#ef4444", min: 0,   max: 49  },
]

interface TooltipPayload {
  name: string
  value: number
  payload: { color: string }
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: TooltipPayload[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold" style={{ color: d.payload.color }}>{d.name}</p>
      <p className="text-muted-foreground mt-0.5">
        {d.value} deal{d.value !== 1 ? "s" : ""}
      </p>
    </div>
  )
}

export function PipelineDonut({ deals }: PipelineDonutProps) {
  if (!deals.length) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No deal data available.
      </p>
    )
  }

  const data = BANDS.map((band) => ({
    name: band.label,
    value: deals.filter(
      (d) => d.momentum_score >= band.min && d.momentum_score <= band.max
    ).length,
    color: band.color,
  })).filter((d) => d.value > 0)

  if (!data.length) {
    return (
      <p className="text-sm text-muted-foreground py-6 text-center">
        No deals to display.
      </p>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={52}
          outerRadius={72}
          paddingAngle={3}
          dataKey="value"
          strokeWidth={0}
        >
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span className="text-xs text-muted-foreground">{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
