"use client"

import * as React from "react"
import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts"
import { motion } from "framer-motion"
import { getMomentumColor, getMomentumLabel, getMomentumClasses } from "@/lib/momentum"
import { cn } from "@/lib/utils"

interface MomentumGaugeProps {
  score: number
  label?: string
  size?: "sm" | "md" | "lg"
}

export function MomentumGauge({ score, label = "Momentum Score", size = "md" }: MomentumGaugeProps) {
  const color = getMomentumColor(score)
  const bandLabel = getMomentumLabel(score)
  const bandClasses = getMomentumClasses(score)

  const data = [
    { value: 100, fill: "#27272a" },
    { value: score, fill: color },
  ]

  const heights: Record<string, number> = { sm: 100, md: 140, lg: 180 }
  const h = heights[size]

  return (
    <div className="flex flex-col items-center gap-2">
      <div style={{ width: h, height: h }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="65%"
            outerRadius="90%"
            data={data}
            startAngle={225}
            endAngle={-45}
            barSize={8}
          >
            <RadialBar dataKey="value" cornerRadius={4} background={false} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-2xl font-bold tabular-nums"
            style={{ color }}
          >
            {score}
          </motion.span>
          <span className="text-[10px] text-muted-foreground mt-0.5">/ 100</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs text-muted-foreground">{label}</p>
        <span className={cn("inline-flex items-center gap-1 text-xs font-medium mt-1 px-2 py-0.5 rounded-full border", bandClasses)}>
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          {bandLabel}
        </span>
      </div>
    </div>
  )
}
