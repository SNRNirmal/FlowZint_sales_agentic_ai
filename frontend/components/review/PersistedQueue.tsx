"use client"

import Link from "next/link"
import { Clock, ArrowRight } from "lucide-react"
import { usePendingApprovals } from "@/hooks/use-pending-approvals"
import { StatusBadge } from "@/components/shared/StatusBadge"

// Approvals from earlier pipeline runs. The backend does not persist draft
// text (design doc, Step 1) — so this layer shows only what really exists:
// department, approver, predicted delay, status.
export function PersistedQueue({ excludeIds }: { excludeIds: string[] }) {
  const { data, isLoading } = usePendingApprovals()

  const rows = (data ?? []).filter(({ approval }) => !excludeIds.includes(approval.id))
  if (isLoading || rows.length === 0) return null

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Clock className="w-4 h-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold text-foreground">Earlier deals awaiting action</h2>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Draft text from past runs isn&apos;t stored server-side. Open the deal to record an outcome,
        or run a new simulation to generate fresh drafts.
      </p>
      <div className="space-y-2">
        {rows.map(({ approval, deal }) => (
          <Link
            key={approval.id}
            href={`/deals/${deal.id}`}
            className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card/50 hover:border-primary/40 transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {deal.customer_name} · {approval.department}
              </p>
              <p className="text-xs text-muted-foreground">{approval.approver_id}</p>
            </div>
            {approval.predicted_delay_days != null && (
              <span className="text-xs text-amber-400 tabular-nums">
                {approval.predicted_delay_days}d predicted delay
              </span>
            )}
            <StatusBadge status={approval.status} />
            <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
        ))}
      </div>
    </div>
  )
}
