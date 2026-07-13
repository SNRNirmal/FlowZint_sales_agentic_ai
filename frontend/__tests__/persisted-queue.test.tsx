import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

vi.mock("@/hooks/use-pending-approvals", () => ({
  usePendingApprovals: vi.fn(),
}))

import { usePendingApprovals, type PendingApproval } from "@/hooks/use-pending-approvals"
import { PersistedQueue } from "@/components/review/PersistedQueue"

const deal = (id: string, customer_name: string) => ({
  id,
  customer_name,
  value: 50000,
  discount_percent: 10,
  product_type: "standard",
  customer_segment: "smb",
  stage: "proposal_sent",
  momentum_score: 75,
  status: "active" as const,
  created_at: "2026-07-12T00:00:00",
})

const rows: PendingApproval[] = [
  {
    deal: deal("d-1", "Acme"),
    approval: {
      id: "ap-1",
      deal_id: "d-1",
      department: "Finance",
      approver_id: "finance_raj",
      status: "pending",
      predicted_delay_days: 2,
      actual_delay_days: null,
      artifact_format_used: null,
    },
  },
  {
    deal: deal("d-2", "Globex"),
    approval: {
      id: "ap-2",
      deal_id: "d-2",
      department: "Legal",
      approver_id: "legal_sam",
      status: "pending",
      predicted_delay_days: null,
      actual_delay_days: null,
      artifact_format_used: null,
    },
  },
]

const mockHook = (value: { data: PendingApproval[] | undefined; isLoading: boolean }) =>
  vi
    .mocked(usePendingApprovals)
    .mockReturnValue(value as unknown as ReturnType<typeof usePendingApprovals>)

beforeEach(() => {
  vi.clearAllMocks()
})

describe("PersistedQueue", () => {
  it("renders a row per pending approval with deal context", () => {
    mockHook({ data: rows, isLoading: false })
    render(<PersistedQueue excludeIds={[]} />)

    expect(screen.getByText(/Acme/)).toBeInTheDocument()
    expect(screen.getByText(/Globex/)).toBeInTheDocument()
    expect(screen.getByText(/2d predicted delay/)).toBeInTheDocument()
    // ap-2 has predicted_delay_days: null — ap-1's must be the only delay text.
    expect(screen.getAllByText(/predicted delay/)).toHaveLength(1)
  })

  it("excludes approvals from the live run", () => {
    mockHook({ data: rows, isLoading: false })
    render(<PersistedQueue excludeIds={["ap-1"]} />)

    expect(screen.queryByText(/Acme/)).not.toBeInTheDocument()
    expect(screen.getByText(/Globex/)).toBeInTheDocument()
  })

  it("renders nothing while loading or when everything is excluded", () => {
    mockHook({ data: undefined, isLoading: true })
    const loading = render(<PersistedQueue excludeIds={[]} />)
    expect(loading.container).toBeEmptyDOMElement()

    mockHook({ data: rows, isLoading: false })
    const excluded = render(<PersistedQueue excludeIds={["ap-1", "ap-2"]} />)
    expect(excluded.container).toBeEmptyDOMElement()
  })
})
