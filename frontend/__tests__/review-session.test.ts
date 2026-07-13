import { beforeEach, describe, expect, it } from "vitest"
import { loadReviewSession, saveReviewSession, clearReviewSession, REVIEW_SESSION_KEY } from "@/hooks/use-review-session"

const result = {
  deal_id: "d-1",
  momentum_score: 70,
  drafted_actions: [
    {
      approval_id: "ap-1",
      department: "Finance",
      approver_id: "finance_raj",
      prediction: { root_cause: "Slow on discounts", delay_probability: 0.42 },
      artifact_draft: "Artifact",
      nudge_draft: "Nudge",
      review_status: "awaiting_human_review",
    },
  ],
}

beforeEach(() => sessionStorage.clear())

describe("review session mirror", () => {
  it("round-trips a run and its card statuses", () => {
    saveReviewSession({ result, statuses: { "ap-1": "sent" } })
    expect(loadReviewSession()).toEqual({ result, statuses: { "ap-1": "sent" } })
  })

  it("returns null when nothing is stored", () => {
    expect(loadReviewSession()).toBeNull()
  })

  it("discards corrupt JSON instead of throwing", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, "{not json")
    expect(loadReviewSession()).toBeNull()
  })

  it("discards payloads that fail schema validation", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, JSON.stringify({ result: { deal_id: 1 }, statuses: {} }))
    expect(loadReviewSession()).toBeNull()
  })

  it("clears the mirror", () => {
    saveReviewSession({ result, statuses: {} })
    clearReviewSession()
    expect(loadReviewSession()).toBeNull()
  })
})
