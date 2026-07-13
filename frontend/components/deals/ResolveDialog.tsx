"use client"

import * as React from "react"
import { CheckCircle2, ClipboardCheck } from "lucide-react"
import { useResolveApproval, useResolveInvalidation } from "@/hooks/use-review-actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"

interface ResolveDialogProps {
  approvalId: string
  approverId: string
}

// Records the real outcome of an approval. This is the only UI action that
// exercises the Learning Agent: the backend updates the approver's
// Behavioral Twin, appends to learning_log, and recomputes momentum.
export function ResolveDialog({ approvalId, approverId }: ResolveDialogProps) {
  const [open, setOpen] = React.useState(false)
  const [delayDays, setDelayDays] = React.useState("")
  const [format, setFormat] = React.useState("")
  const [reason, setReason] = React.useState("")

  const resolveMutation = useResolveApproval()
  const invalidateAfterResolve = useResolveInvalidation()

  // Guard against values that would corrupt the twin's rolling average —
  // mirror the backend's bounds (it 422s anything outside 0–365).
  const delay = Number(delayDays)
  const canSubmit =
    delayDays.trim() !== "" && Number.isFinite(delay) && delay >= 0 && delay <= 365 && format.trim() !== ""

  const submit = () => {
    if (resolveMutation.isPending) return
    if (!canSubmit) return
    resolveMutation.mutate({
      id: approvalId,
      payload: {
        actual_delay_days: delay,
        artifact_format_used: format.trim(),
        delay_reason: reason.trim(),
      },
    })
  }

  // Every close path (Done, X, overlay, Escape) routes through here, so the
  // deferred invalidation fires exactly once per successful resolve.
  const reset = (next: boolean) => {
    setOpen(next)
    if (!next) {
      if (resolveMutation.isSuccess) invalidateAfterResolve()
      resolveMutation.reset()
      setDelayDays("")
      setFormat("")
      setReason("")
    }
  }

  return (
    <Dialog open={open} onOpenChange={reset}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <ClipboardCheck className="w-3.5 h-3.5" />
          Record outcome
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Record outcome — {approverId}</DialogTitle>
          <DialogDescription>
            The Learning Agent updates this approver&apos;s Behavioral Twin from what actually happened.
          </DialogDescription>
        </DialogHeader>

        {resolveMutation.isSuccess ? (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="text-sm font-medium text-foreground">Outcome recorded</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Twin updated · momentum now {resolveMutation.data.new_momentum_score}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="actual-delay">Actual delay (days)</Label>
              <Input
                id="actual-delay"
                type="number"
                min="0"
                max="365"
                step="0.5"
                value={delayDays}
                onChange={(e) => setDelayDays(e.target.value)}
                placeholder="e.g. 2.5"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="artifact-format">Artifact format that worked</Label>
              <Input
                id="artifact-format"
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                placeholder="e.g. one-pager"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="delay-reason">Delay reason (optional)</Label>
              <Textarea
                id="delay-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="What actually held it up?"
                className="min-h-[60px]"
              />
            </div>
            {resolveMutation.isError && (
              <p role="alert" className="text-xs text-destructive">
                {resolveMutation.error instanceof Error ? resolveMutation.error.message : "Failed to record outcome."}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          {resolveMutation.isSuccess ? (
            <Button size="sm" onClick={() => reset(false)}>Done</Button>
          ) : (
            <Button size="sm" onClick={submit} disabled={!canSubmit || resolveMutation.isPending}>
              {resolveMutation.isPending ? "Saving…" : "Save outcome"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
