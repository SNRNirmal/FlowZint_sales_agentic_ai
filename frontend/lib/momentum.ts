export type MomentumBand = "green" | "amber" | "red"

export function getMomentumBand(score: number): MomentumBand {
  if (score >= 80) return "green"
  if (score >= 50) return "amber"
  return "red"
}

export function getMomentumColor(score: number): string {
  const band = getMomentumBand(score)
  return band === "green" ? "#22c55e" : band === "amber" ? "#f59e0b" : "#ef4444"
}

export function getMomentumLabel(score: number): string {
  const band = getMomentumBand(score)
  return band === "green" ? "On Track" : band === "amber" ? "At Risk" : "Stalled"
}

export function getMomentumClasses(score: number): string {
  const band = getMomentumBand(score)
  return band === "green"
    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
    : band === "amber"
    ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
    : "text-red-400 bg-red-500/10 border-red-500/20"
}
