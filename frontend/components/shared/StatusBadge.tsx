import * as React from "react"
import { cn } from "@/lib/utils"

type Status = "active" | "stalled" | "closed" | "pending" | "sent" | "approved" | "rejected" | string

const STATUS_STYLES: Record<string, string> = {
  active:   "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  sent:     "bg-blue-500/10 text-blue-400 border-blue-500/20",
  stalled:  "bg-amber-500/10 text-amber-400 border-amber-500/20",
  pending:  "bg-amber-500/10 text-amber-400 border-amber-500/20",
  closed:   "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  rejected: "bg-red-500/10 text-red-400 border-red-500/20",
}

export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const styles = STATUS_STYLES[status] ?? "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border",
        styles,
        className
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
