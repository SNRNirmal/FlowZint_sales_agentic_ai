import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ApproverCard } from "@/components/twins/ApproverCard"

const twin = {
  approver_id: "finance_raj",
  department: "Finance",
  avg_turnaround_days: 3.2,
  fastest_responding_format: "one-pager",
  slowest_trigger: "missing discount justification",
  total_deals_reviewed: 14,
  last_updated: "2026-07-10T09:00:00Z",
}

describe("ApproverCard", () => {
  it("shows the approver identity", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText("finance_raj")).toBeInTheDocument()
    expect(screen.getByText("Finance")).toBeInTheDocument()
  })

  it("shows the behavioral statistics", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/3.2 days/)).toBeInTheDocument()
    expect(screen.getByText(/Responds fastest to: one-pager/)).toBeInTheDocument()
    expect(screen.getByText(/Slows down on: missing discount justification/)).toBeInTheDocument()
  })

  it("shows the sample size behind the twin", () => {
    render(<ApproverCard twin={twin} />)
    expect(screen.getByText(/14 deals reviewed/)).toBeInTheDocument()
  })

  it("shows when the Learning Agent last updated the twin", () => {
    render(<ApproverCard twin={twin} />)
    const updated = screen.getByText(/Updated/)
    expect(updated).toBeInTheDocument()
    expect(updated.textContent).not.toMatch(/Invalid Date/)
  })

  it("falls back gracefully for an unparseable date", () => {
    render(<ApproverCard twin={{ ...twin, last_updated: "not-a-date" }} />)
    expect(screen.getByText(/Updated recently/)).toBeInTheDocument()
  })
})
