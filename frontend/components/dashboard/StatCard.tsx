import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface StatCardProps {
  label: string
  value: string | number
  delta?: string
  deltaType?: "positive" | "negative" | "neutral"
  icon: React.ReactNode
  index?: number
}

export function StatCard({ label, value, delta, deltaType = "neutral", icon, index = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className="bg-card border border-border rounded-xl p-5 flex flex-col gap-4"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</span>
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="text-3xl font-bold tracking-tight text-foreground tabular-nums">{value}</span>
        {delta && (
          <span
            className={cn(
              "text-xs font-medium mb-1",
              deltaType === "positive" && "text-emerald-400",
              deltaType === "negative" && "text-red-400",
              deltaType === "neutral" && "text-muted-foreground"
            )}
          >
            {delta}
          </span>
        )}
      </div>
    </motion.div>
  )
}
