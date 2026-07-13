import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

vi.mock("@/hooks/use-twins", () => ({ useTwins: vi.fn() }))

import TwinsPage from "@/app/(app)/twins/page"
import { useTwins } from "@/hooks/use-twins"
import type { BehavioralTwin } from "@/types/twin"

const twin: BehavioralTwin = {
  approver_id: "finance_raj",
  department: "Finance",
  avg_turnaround_days: 3.2,
  fastest_responding_format: "one-pager",
  slowest_trigger: "x",
  total_deals_reviewed: 14,
  last_updated: "2026-07-10T09:00:00Z",
}

function mockUseTwins(state: {
  data: BehavioralTwin[] | undefined
  isLoading: boolean
  error: Error | null
}) {
  vi.mocked(useTwins).mockReturnValue({
    ...state,
    refetch: vi.fn(),
    isFetching: false,
  } as unknown as ReturnType<typeof useTwins>)
}

describe("TwinsPage", () => {
  it("keeps showing cached twins when a background poll fails", () => {
    mockUseTwins({ data: [twin], isLoading: false, error: new Error("net") })
    render(<TwinsPage />)

    // Both, not either: cached content survives the failed poll AND the
    // failure is surfaced.
    expect(screen.getByText("finance_raj")).toBeInTheDocument()
    expect(screen.getByText(/Failed to load twins/)).toBeInTheDocument()
  })

  it("does not claim 'no twins seeded' when data is just unavailable", () => {
    mockUseTwins({ data: undefined, isLoading: false, error: null })
    render(<TwinsPage />)

    expect(screen.queryByText(/No twins seeded/)).not.toBeInTheDocument()
    expect(screen.queryByText("finance_raj")).not.toBeInTheDocument()
  })

  it("shows the seeded empty state only for a loaded empty list", () => {
    mockUseTwins({ data: [], isLoading: false, error: null })
    render(<TwinsPage />)

    expect(screen.getByText("No twins seeded")).toBeInTheDocument()
  })
})
