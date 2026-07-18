"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Play, ClipboardCheck, Loader2, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { triggerDemoDeal, fetchDealStatus, fetchDealResult } from "@/lib/api"
import { useSendNudge, useHoldNudge } from "@/hooks/use-review-actions"
import {
  loadReviewSession, saveReviewSession, clearReviewSession,
} from "@/hooks/use-review-session"
import { ReviewCard, type CardStatus } from "@/components/review/ReviewCard"
import { PersistedQueue } from "@/components/review/PersistedQueue"
import { DealContextBanner } from "@/components/review/DealContextBanner"
import { MomentumGauge } from "@/components/dashboard/MomentumGauge"
import { PageHeader } from "@/components/shared/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { WebhookResult, DealStatus } from "@/types/api"

// ─── Default form state ────────────────────────────────────────────────────
// These fields drive the POST /webhooks/crm payload. No values are
// pre-filled with invented company names or hardcoded numerics.
const EMPTY_FORM = {
  customer_name: "",
  value: "",
  discount_percent: "",
  product_type: "standard",
  customer_segment: "mid-market",
  stage: "proposal_sent",
}

export default function ReviewPage() {
  const [form, setForm] = React.useState(EMPTY_FORM)
  const [result, setResult] = React.useState<WebhookResult | null>(null)
  const [pollStatus, setPollStatus] = React.useState<DealStatus | null>(null)
  const [statuses, setStatuses] = React.useState<Record<string, CardStatus>>({})
  const [errors, setErrors] = React.useState<Record<string, string>>({})

  // Hydrate the last run (and settled statuses) after mount. Reading
  // sessionStorage during render would make the server-rendered HTML (always
  // the empty state) mismatch the first client render.
  React.useEffect(() => {
    const session = loadReviewSession()
    if (session) {
      setResult(session.result)
      setStatuses(session.statuses)
    }
  }, [])

  // Late mutation settles must persist against the *current* run, not the one
  // captured by the click-time closure — otherwise a settle after Clear or a
  // new Run would resurrect or overwrite the wrong session mirror.
  const resultRef = React.useRef(result)
  React.useEffect(() => {
    resultRef.current = result
  }, [result])

  const sendMutation = useSendNudge()
  const holdMutation = useHoldNudge()

  const persist = (nextResult: WebhookResult, nextStatuses: Record<string, CardStatus>) => {
    const settled = Object.fromEntries(
      Object.entries(nextStatuses).filter(([, s]) => s === "sent" || s === "held"),
    ) as Record<string, "sent" | "held">
    saveReviewSession({ result: nextResult, statuses: settled })
  }

  // Validate that the form contains enough data to trigger the pipeline.
  const canRun =
    form.customer_name.trim() !== "" &&
    form.value.trim() !== "" &&
    Number.isFinite(Number(form.value)) &&
    Number(form.value) > 0 &&
    form.discount_percent.trim() !== "" &&
    Number.isFinite(Number(form.discount_percent)) &&
    Number(form.discount_percent) >= 0 &&
    Number(form.discount_percent) <= 100

  const runMutation = useMutation({
    mutationFn: async () => {
      setPollStatus(null);
      const accepted = await triggerDemoDeal({
        customer_name: form.customer_name.trim(),
        value: Number(form.value),
        discount_percent: Number(form.discount_percent),
        product_type: form.product_type,
        customer_segment: form.customer_segment,
        stage: form.stage,
      })
      while (true) {
        await new Promise(r => setTimeout(r, 2000))
        const st = await fetchDealStatus(accepted.deal_id)
        setPollStatus(st)
        if (st.status === "failed") {
          throw new Error(st.error || "Pipeline failed")
        }
        if (st.status === "completed") {
          return await fetchDealResult(accepted.deal_id)
        }
      }
    },
    onSuccess: (data) => {
      setResult(data)
      setStatuses({})
      setErrors({})
      persist(data, {})
    },
  })

  const setCardStatus = (id: string, status: CardStatus, errorMsg?: string) => {
    setStatuses((prev) => {
      const next = { ...prev, [id]: status }
      const current = resultRef.current
      if (current && current.drafted_actions.some((a) => a.approval_id === id)) {
        persist(current, next)
      }
      return next
    })
    setErrors((prev) => ({ ...prev, [id]: errorMsg ?? "" }))
  }

  // mutateAsync, not mutate-with-callbacks: TanStack Query drops per-mutate
  // callbacks when a later mutate supersedes an in-flight one on the same
  // mutation instance, which would strand the earlier card in "sending".
  const handleSend = (id: string, text: string) => {
    setCardStatus(id, "sending")
    sendMutation
      .mutateAsync({ id, text })
      .then(() => setCardStatus(id, "sent"))
      .catch((err) => setCardStatus(id, "error", err instanceof Error ? err.message : "Send failed"))
  }

  const handleHold = (id: string) => {
    setCardStatus(id, "holding")
    holdMutation
      .mutateAsync(id)
      .then(() => setCardStatus(id, "held"))
      .catch((err) => setCardStatus(id, "error", err instanceof Error ? err.message : "Hold failed"))
  }

  const handleClear = () => {
    setResult(null)
    setPollStatus(null)
    setStatuses({})
    setErrors({})
    clearReviewSession()
  }

  const field = (key: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const totalCount = result?.drafted_actions.length ?? 0
  const settledCount = Object.values(statuses).filter((s) => s === "sent" || s === "held").length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Human Review Queue"
        description="Nothing Threshold drafts reaches a real approver until you explicitly send it."
      />

      {/* Deal input panel */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-1">
          <Play className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Pipeline Simulator</h2>
        </div>
        <p className="text-xs text-muted-foreground mb-5">
          Enter real deal parameters and run the full Threshold AI pipeline. Review the output before anything is sent.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-5">
          {/* Customer name */}
          <div className="space-y-1.5">
            <Label htmlFor="customer-name" className="text-xs text-muted-foreground">Customer name</Label>
            <Input
              id="customer-name"
              placeholder="e.g. Acme Corp"
              value={form.customer_name}
              onChange={field("customer_name")}
              disabled={runMutation.isPending}
            />
          </div>

          {/* Deal value */}
          <div className="space-y-1.5">
            <Label htmlFor="deal-value" className="text-xs text-muted-foreground">Deal value ($)</Label>
            <Input
              id="deal-value"
              type="number"
              min="0"
              placeholder="e.g. 75000"
              value={form.value}
              onChange={field("value")}
              disabled={runMutation.isPending}
            />
          </div>

          {/* Discount */}
          <div className="space-y-1.5">
            <Label htmlFor="discount" className="text-xs text-muted-foreground">Discount (%)</Label>
            <Input
              id="discount"
              type="number"
              min="0"
              max="100"
              step="0.5"
              placeholder="e.g. 12"
              value={form.discount_percent}
              onChange={field("discount_percent")}
              disabled={runMutation.isPending}
            />
          </div>

          {/* Product type */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Product type</Label>
            <Select
              value={form.product_type}
              onValueChange={(v) => setForm((p) => ({ ...p, product_type: v }))}
              disabled={runMutation.isPending}
            >
              <SelectTrigger className="bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="standard">Standard</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Customer segment */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Customer segment</Label>
            <Select
              value={form.customer_segment}
              onValueChange={(v) => setForm((p) => ({ ...p, customer_segment: v }))}
              disabled={runMutation.isPending}
            >
              <SelectTrigger className="bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="smb">SMB</SelectItem>
                <SelectItem value="mid-market">Mid-Market</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Stage */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Deal stage</Label>
            <Select
              value={form.stage}
              onValueChange={(v) => setForm((p) => ({ ...p, stage: v }))}
              disabled={runMutation.isPending}
            >
              <SelectTrigger className="bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="proposal_sent">Proposal Sent</SelectItem>
                <SelectItem value="verbal_agreement">Verbal Agreement</SelectItem>
                <SelectItem value="negotiation">Negotiation</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !canRun}
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
              onClick={handleClear}
              className="gap-2 text-muted-foreground"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Clear results
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
            className="bg-primary/5 border border-primary/20 rounded-xl p-6 flex flex-col gap-4"
          >
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">
                  {pollStatus ? `Pipeline running: ${pollStatus.current_node || "starting"}` : "Threshold pipeline starting…"}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {pollStatus?.progress != null ? `Progress: ${pollStatus.progress}%` : "Detecting approvals, predicting friction, drafting artifacts and nudges."}
                </p>
              </div>
            </div>
            {pollStatus?.progress != null && (
              <div className="h-1.5 w-full bg-primary/20 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-500 ease-in-out" 
                  style={{ width: `${pollStatus.progress}%` }} 
                />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error state */}
      {runMutation.isError && (
        <div role="alert" className="p-4 rounded-xl border border-destructive/20 bg-destructive/5 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-destructive shrink-0" />
          <p className="text-sm text-destructive">
            AI provider unavailable: {runMutation.error?.message}
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
            <DealContextBanner
              customerName={form.customer_name}
              value={form.value}
              productType={form.product_type}
              customerSegment={form.customer_segment}
              momentumScore={result.momentum_score}
              totalApprovals={result.drafted_actions.length}
            />

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
                  {settledCount}/{totalCount} actioned
                </span>
              </div>
            </div>

            {/* Review cards */}
            <div className="space-y-3">
              {result.drafted_actions.map((action, i) => (
                <ReviewCard
                  key={action.approval_id}
                  action={action}
                  status={statuses[action.approval_id] ?? "idle"}
                  error={errors[action.approval_id]}
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
            Fill in the deal details above and run the pipeline. Threshold will draft artifacts and nudges for your review.
          </p>
        </motion.div>
      )}

      {/* Persisted layer: pending approvals from earlier runs (server truth) */}
      <PersistedQueue excludeIds={result?.drafted_actions.map((a) => a.approval_id) ?? []} />
    </div>
  )
}
