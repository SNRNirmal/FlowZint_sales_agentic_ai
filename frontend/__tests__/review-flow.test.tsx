import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/api", () => ({
  sendApprovalNudge: vi.fn().mockResolvedValue({ status: "sent", approval_id: "ap-1" }),
  holdApprovalNudge: vi.fn().mockResolvedValue({ status: "held", approval_id: "ap-1" }),
  triggerDemoDeal: vi.fn(),
  fetchDeals: vi.fn().mockResolvedValue([]),
  fetchDeal: vi.fn(),
  resolveApproval: vi.fn(),
}))

import { holdApprovalNudge, sendApprovalNudge } from "@/lib/api"
import { REVIEW_SESSION_KEY } from "@/hooks/use-review-session"
import ReviewPage from "@/app/(app)/review/page"

const action = (id: string, department: string) => ({
  approval_id: id,
  department,
  approver_id: "finance_raj",
  prediction: { root_cause: "Slow on discount deals", delay_probability: 0.42 },
  artifact_draft: "Draft artifact body",
  nudge_draft: "Please review this deal",
  review_status: "awaiting_human_review",
})

const storedRun = (
  actions: ReturnType<typeof action>[],
  statuses: Record<string, "sent" | "held"> = {},
) =>
  JSON.stringify({
    result: { deal_id: "d-1", momentum_score: 70, drafted_actions: actions },
    statuses,
  })

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReviewPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe("review flow", () => {
  it("hydrates a stored run from sessionStorage on mount", () => {
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()
    expect(screen.getByText("finance_raj")).toBeInTheDocument()
    expect(screen.getByText("Draft artifact body")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Please review this deal")).toBeInTheDocument()
  })

  it("shows the empty state when nothing is stored", () => {
    renderPage()
    expect(screen.getByText(/queue is empty/i)).toBeInTheDocument()
  })

  it("Send calls the API with the (editable) nudge text and marks the card sent", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))

    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findByText(/^sent$/i)).toBeInTheDocument()
  })

  it("Hold calls the API and marks the card held without sending", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /hold/i }))

    expect(holdApprovalNudge).toHaveBeenCalledWith("ap-1")
    expect(await screen.findByText(/^held$/i)).toBeInTheDocument()
    expect(sendApprovalNudge).not.toHaveBeenCalled()
  })

  it("tracks status per card, not globally", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      REVIEW_SESSION_KEY,
      storedRun([action("ap-1", "Finance"), action("ap-2", "Legal")]),
    )
    renderPage()

    await user.click(screen.getAllByRole("button", { name: /send to approver/i })[0])

    expect(sendApprovalNudge).toHaveBeenCalledTimes(1)
    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findAllByText(/^sent$/i)).toHaveLength(1)
  })

  it("persists settled statuses back to the mirror", async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))
    await screen.findByText(/^sent$/i)

    const stored = JSON.parse(sessionStorage.getItem(REVIEW_SESSION_KEY)!)
    expect(stored.statuses["ap-1"]).toBe("sent")
  })

  it("hydrates settled card statuses from the mirror", () => {
    sessionStorage.setItem(
      REVIEW_SESSION_KEY,
      storedRun([action("ap-1", "Finance")], { "ap-1": "sent" }),
    )
    renderPage()

    expect(screen.getByText(/^sent$/i)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /send to approver/i })).not.toBeInTheDocument()
  })

  it("does not persist in-flight statuses", async () => {
    const user = userEvent.setup()
    vi.mocked(sendApprovalNudge).mockReturnValueOnce(new Promise<never>(() => {}))
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))

    const stored = JSON.parse(sessionStorage.getItem(REVIEW_SESSION_KEY)!)
    expect(stored.statuses["ap-1"]).toBeUndefined()
    expect(Object.values(stored.statuses)).not.toContain("sending")
  })

  it("error path recovers to a retryable card", async () => {
    const user = userEvent.setup()
    vi.mocked(sendApprovalNudge).mockRejectedValueOnce(new Error("boom"))
    sessionStorage.setItem(REVIEW_SESSION_KEY, storedRun([action("ap-1", "Finance")]))
    renderPage()

    await user.click(screen.getByRole("button", { name: /send to approver/i }))
    expect(await screen.findByText(/boom/)).toBeInTheDocument()

    const sendButton = screen.getByRole("button", { name: /send to approver/i })
    expect(sendButton).not.toBeDisabled()

    await user.click(sendButton)
    expect(await screen.findByText(/^sent$/i)).toBeInTheDocument()
  })
})
