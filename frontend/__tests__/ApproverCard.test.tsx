import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import ApproverCard from "@/components/ApproverCard"

const twin = {
  approver_id: "finance_raj",
  department: "Finance",
  avg_turnaround_days: 3.2,
  fastest_responding_format: "one-pager",
  slowest_trigger: "missing discount justification",
  total_deals_reviewed: 14,
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
})
