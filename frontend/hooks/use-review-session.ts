import { z } from "zod"
import { WebhookResponseSchema, type WebhookResponse } from "@/types/api"

export const REVIEW_SESSION_KEY = "threshold.review.v1"

// Only settled outcomes are persisted; in-flight states rehydrate as idle.
const StoredStatusSchema = z.enum(["sent", "held"])
const StoredSessionSchema = z.object({
  result: WebhookResponseSchema,
  statuses: z.record(z.string(), StoredStatusSchema),
})

export type StoredReviewSession = {
  result: WebhookResponse
  statuses: Record<string, "sent" | "held">
}

// The mirror is best-effort by design: storage access can throw (quota
// exceeded, storage disabled) and must never take the app down with it.
export function loadReviewSession(): StoredReviewSession | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(REVIEW_SESSION_KEY)
    if (!raw) return null
    const parsed = StoredSessionSchema.safeParse(JSON.parse(raw))
    return parsed.success ? parsed.data : null
  } catch {
    return null
  }
}

export function saveReviewSession(session: StoredReviewSession): void {
  if (typeof window === "undefined") return
  try {
    sessionStorage.setItem(REVIEW_SESSION_KEY, JSON.stringify(session))
  } catch {
    // best-effort mirror — ignore storage failures
  }
}

export function clearReviewSession(): void {
  if (typeof window === "undefined") return
  try {
    sessionStorage.removeItem(REVIEW_SESSION_KEY)
  } catch {
    // best-effort mirror — ignore storage failures
  }
}
