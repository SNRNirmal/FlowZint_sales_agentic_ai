"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Play, ClipboardCheck, Loader2, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { triggerDemoDeal, sendApprovalNudge, holdApprovalNudge } from "@/lib/api"
import { ReviewCard } from "@/components/review/ReviewCard"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { PageHeader } from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { WebhookResponse } from "@/types/review"

const DEMO_SCENARIOS = [
  {
    label: "Enterprise SaaS — High Value",
    payload: {
      customer_name: "Northwind Logistics",
      value: 180000,
      discount_percent: 18,
      product_type: "custom",
      customer_segment: "enterprise",
      stage: "verbal_agreement",
    },
  },
  {
    label: "Mid-Market — Standard Deal",
    payload: {
      customer_name: "Cascade Analytics",
      value: 65000,
      discount_percent: 8,
      product_type: "standard",
      customer_segment: "mid-market",
      stage: "proposal_sent",
    },
  },
  {
    label: "SMB — High Discount Risk",
    payload: {
      customer_name: "Meridian Co.",
      value: 28000,
      discount_percent: 25,
      product_type: "standard",
      customer_segment: "smb",
      stage: "verbal_agreement",
    },
  },
]

export default function ReviewPage() {
  const [scenario, setScenario] = React.useState("0")
  const [result, setResult] = React.useState<WebhookResponse | null>(null)

  const runMutation = useMutation({
    mutationFn: () => triggerDemoDeal(DEMO_SCENARIOS[parseInt(scenario)].payload),
    onSuccess: (data) => setResult(data),
  })

  const handleSend = async (id: string, text: string) => {
    await sendApprovalNudge(id, text)
  }

  const handleHold = async (id: string) => {
    await holdApprovalNudge(id)
  }

  const completedCount = 0 // In a real app, track per-card status
  const totalCount = result?.drafted_actions.length ?? 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Human Review Queue"
        description="Nothing Threshold drafts reaches a real approver until you explicitly send it."
      />

      {/* Control panel */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-1">
          <Play className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Pipeline Simulator</h2>
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          Trigger a deal through the full Threshold AI pipeline. Review the output before anything is sent.
        </p>
        <div className="flex items-center gap-3 flex-wrap">
          <Select value={scenario} onValueChange={setScenario}>
            <SelectTrigger className="w-64 bg-background">
              <SelectValue placeholder="Select scenario" />
            </SelectTrigger>
            <SelectContent>
              {DEMO_SCENARIOS.map((s, i) => (
                <SelectItem key={i} value={String(i)}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            className="gap-2"
          >
            {runMutation.isPending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Running pipeline…
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Run Pipeline
              </>
            )}
          </Button>
          {result && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setResult(null)}
              className="gap-2 text-muted-foreground"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Loading state */}
      <AnimatePresence>
        {runMutation.isPending && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="bg-primary/5 border border-primary/20 rounded-xl p-6 flex items-center gap-4"
          >
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">Threshold pipeline running…</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Analyzing deal, building behavioral twin profiles, drafting artifacts and nudges.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error state */}
      {runMutation.isError && (
        <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-destructive shrink-0" />
          <p className="text-sm text-destructive">
            Pipeline failed. Is the backend running at localhost:8000?
          </p>
        </div>
      )}

      {/* Results */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-5"
          >
            {/* Summary bar */}
            <div className="flex items-center gap-6 bg-card border border-border rounded-xl p-4 flex-wrap">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <div>
                  <p className="text-xs text-muted-foreground">Pipeline Complete</p>
                  <p className="text-sm font-medium text-foreground">Deal ID: {result.deal_id.slice(0, 8)}…</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <MomentumGauge score={result.momentum_score ?? 0} size="sm" label="Deal momentum" />
              </div>
              <div className="ml-auto flex items-center gap-2">
                <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  {totalCount} action{totalCount !== 1 ? "s" : ""} awaiting review
                </span>
              </div>
            </div>

            {/* Review cards */}
            <div className="space-y-3">
              {result.drafted_actions.map((action, i) => (
                <ReviewCard
                  key={action.approval_id}
                  action={action}
                  onSend={handleSend}
                  onHold={handleHold}
                  index={i}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!result && !runMutation.isPending && !runMutation.isError && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-20 text-center"
        >
          <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-4">
            <ClipboardCheck className="w-7 h-7 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground">Queue is empty</p>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            Select a scenario and run the pipeline above. Threshold will draft artifacts and nudges for your review.
          </p>
        </motion.div>
      )}
    </div>
  )
}
