import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

// The component imports "../lib/api"; both that specifier and this alias
// resolve to the same module id, so this factory intercepts it.
vi.mock("@/lib/api", () => ({
  sendApprovalNudge: vi.fn().mockResolvedValue({}),
  holdApprovalNudge: vi.fn().mockResolvedValue({}),
}))

import { holdApprovalNudge, sendApprovalNudge } from "@/lib/api"
import ReviewQueue from "@/components/ReviewQueue"

const action = {
  approval_id: "ap-1",
  department: "Finance",
  approver_id: "finance_raj",
  artifact_draft: "Draft artifact body",
  nudge_draft: "Please review this deal",
  prediction: { root_cause: "Slow on discount deals", delay_probability: 0.42 },
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("ReviewQueue", () => {
  it("renders one card per action with prediction context", () => {
    render(<ReviewQueue actions={[action, { ...action, approval_id: "ap-2", department: "Legal" }]} />)
    expect(screen.getByText(/Finance — finance_raj/)).toBeInTheDocument()
    expect(screen.getByText(/Legal — finance_raj/)).toBeInTheDocument()
    expect(screen.getAllByText(/delay risk: 42%/)).toHaveLength(2)
  })

  it("renders the drafted artifact and nudge", () => {
    render(<ReviewQueue actions={[action]} />)
    expect(screen.getByText("Draft artifact body")).toBeInTheDocument()
    expect(screen.getByText("Please review this deal")).toBeInTheDocument()
  })

  it("Send calls the API with the nudge draft and shows sent status", async () => {
    const user = userEvent.setup()
    render(<ReviewQueue actions={[action]} />)

    await user.click(screen.getByRole("button", { name: "Send" }))

    expect(sendApprovalNudge).toHaveBeenCalledWith("ap-1", "Please review this deal")
    expect(await screen.findByText(/Status: sent/)).toBeInTheDocument()
  })

  it("Hold calls the API and shows held status", async () => {
    const user = userEvent.setup()
    render(<ReviewQueue actions={[action]} />)

    await user.click(screen.getByRole("button", { name: "Hold" }))

    expect(holdApprovalNudge).toHaveBeenCalledWith("ap-1")
    expect(await screen.findByText(/Status: held/)).toBeInTheDocument()
    expect(sendApprovalNudge).not.toHaveBeenCalled()
  })

  it("renders nothing gracefully for an empty queue", () => {
    const { container } = render(<ReviewQueue actions={[]} />)
    expect(container.querySelectorAll("button")).toHaveLength(0)
  })
})
