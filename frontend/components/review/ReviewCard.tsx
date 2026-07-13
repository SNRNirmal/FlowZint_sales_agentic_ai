"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Send, PauseCircle, ChevronDown, ChevronUp,
  AlertTriangle, Brain, FileText, MessageSquare, CheckCircle2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { DraftedAction } from "@/types/review"

export type CardStatus = "idle" | "sending" | "holding" | "sent" | "held" | "error"

interface ReviewCardProps {
  action: DraftedAction
  status: CardStatus
  error?: string
  onSend: (id: string, text: string) => void
  onHold: (id: string) => void
  index: number
}

export function ReviewCard({ action, status, error, onSend, onHold, index }: ReviewCardProps) {
  const [expanded, setExpanded] = React.useState(true)
  const [nudgeText, setNudgeText] = React.useState(action.nudge_draft)

  const delayProb = action.prediction.delay_probability
  const delayPct = typeof delayProb === "number" ? Math.round(delayProb * 100) : null
  const riskColor =
    delayPct == null ? "text-muted-foreground"
    : delayPct >= 70 ? "text-red-400"
    : delayPct >= 40 ? "text-amber-400"
    : "text-emerald-400"
  const riskBg =
    delayPct == null ? "bg-muted border-border"
    : delayPct >= 70 ? "bg-red-500/10 border-red-500/20"
    : delayPct >= 40 ? "bg-amber-500/10 border-amber-500/20"
    : "bg-emerald-500/10 border-emerald-500/20"

  const done = status === "sent" || status === "held"
  const busy = status === "sending" || status === "holding"

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08 }}
      className={cn(
        "bg-card border rounded-xl overflow-hidden transition-all",
        done ? "border-border opacity-60" : "border-border hover:border-primary/30"
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-4 px-5 py-4 cursor-pointer" onClick={() => setExpanded((e) => !e)}>
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Brain className="w-4 h-4 text-primary" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-foreground">{action.approver_id}</span>
            <Badge variant="outline" className="text-xs px-2 py-0">{action.department}</Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {action.prediction.root_cause || "Risk analysis complete"}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className={cn("text-sm font-bold tabular-nums", riskColor)}>
            {delayPct == null ? "—" : `${delayPct}%`}
          </span>
          <span className={cn("text-xs px-2 py-0.5 rounded-full border font-medium", riskBg)}>
            delay risk
          </span>
          {done && (
            <span className="flex items-center gap-1 text-xs text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {status}
            </span>
          )}
          {expanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />
          }
        </div>
      </div>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4 border-t border-border pt-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI-Generated Artifact</span>
                </div>
                <pre className="w-full text-xs text-foreground bg-background border border-border rounded-lg p-4 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
                  {action.artifact_draft || "No artifact generated."}
                </pre>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Nudge Message</span>
                  <span className="text-xs text-primary ml-auto">Editable before sending</span>
                </div>
                <Textarea
                  value={nudgeText}
                  onChange={(e) => setNudgeText(e.target.value)}
                  disabled={done || busy}
                  className="text-sm bg-background border-border min-h-[80px] resize-y"
                  placeholder="Nudge message will appear here after pipeline runs..."
                />
              </div>

              {action.prediction.root_cause && (
                <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-500/5 border border-amber-500/15">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-amber-400">Risk Analysis</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{action.prediction.root_cause}</p>
                  </div>
                </div>
              )}

              {status === "error" && (
                <div role="alert" className="flex items-start gap-2.5 p-3 rounded-lg bg-destructive/5 border border-destructive/20">
                  <AlertTriangle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                  <p className="text-xs text-destructive">{error || "Action failed."} Try again.</p>
                </div>
              )}

              {!done && (
                <div className="flex items-center gap-2 pt-1">
                  <Button
                    onClick={() => onSend(action.approval_id, nudgeText)}
                    disabled={busy || !nudgeText.trim()}
                    size="sm"
                    className="gap-2"
                  >
                    {status === "sending" ? "Sending…" : (<><Send className="w-3.5 h-3.5" />Send to Approver</>)}
                  </Button>
                  <Button
                    onClick={() => onHold(action.approval_id)}
                    disabled={busy}
                    variant="outline"
                    size="sm"
                    className="gap-2"
                  >
                    {status === "holding" ? "Holding…" : (<><PauseCircle className="w-3.5 h-3.5" />Hold</>)}
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
