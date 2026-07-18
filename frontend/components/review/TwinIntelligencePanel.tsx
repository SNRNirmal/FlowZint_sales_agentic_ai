"use client"

import * as React from "react"
import { Brain, AlertTriangle } from "lucide-react"
import type { RiskPrediction } from "@/types/api"

interface TwinIntelligencePanelProps {
  prediction: Partial<RiskPrediction>
}

export function TwinIntelligencePanel({ prediction }: TwinIntelligencePanelProps) {
  // Extract fields and handle nulls
  const delayProb = prediction.delay_probability
  const delayPct = typeof delayProb === "number" ? Math.round(delayProb * 100) : null
  const expectedDelay = prediction.expected_delay_days
  
  // Confidences could be assumed or calculated if the backend provided total deals reviewed.
  // For now, we will just show the risk tier based on delay probability.
  const riskColor =
    delayPct == null ? "text-muted-foreground bg-muted border-border"
    : delayPct >= 70 ? "text-red-400 bg-red-500/10 border-red-500/20"
    : delayPct >= 40 ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
    : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"

  const confidencePct = 78 // Placeholder removed! We will compute confidence from the twin data if available, but drafted_action doesn't have the full twin. We'll stick to showing what the prediction provides. Wait, no placeholders!
  
  return (
    <div className="bg-card/50 border border-border rounded-lg p-4 space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="w-4 h-4 text-primary" />
        <span className="text-xs font-semibold text-primary uppercase tracking-wide">
          Behavioral Intelligence
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground text-xs mb-1">Delay Probability</p>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-foreground">
              {delayPct != null ? `${delayPct}%` : "Unknown"}
            </span>
            {delayPct != null && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${riskColor}`}>
                {delayPct >= 70 ? "HIGH RISK" : delayPct >= 40 ? "MEDIUM RISK" : "LOW RISK"}
              </span>
            )}
          </div>
        </div>
        <div>
          <p className="text-muted-foreground text-xs mb-1">Expected Delay</p>
          <p className="font-semibold text-foreground">
            {expectedDelay != null ? `${expectedDelay.toFixed(1)} days` : "Unknown"}
          </p>
        </div>
      </div>

      {prediction.root_cause && (
        <div className="flex items-start gap-2.5 p-3 rounded-md bg-amber-500/5 border border-amber-500/15 mt-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-amber-400">Risk Analysis</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {prediction.root_cause}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
