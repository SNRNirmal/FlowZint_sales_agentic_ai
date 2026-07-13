import { describe, expect, it, vi } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import * as React from "react"

vi.mock("@/lib/api", () => ({
  fetchDeals: vi.fn().mockResolvedValue([
    { id: "d-1", customer_name: "A", value: 1, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 90, status: "active", created_at: "2026-07-12T00:00:00" },
    { id: "d-2", customer_name: "B", value: 2, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 80, status: "active", created_at: "2026-07-12T00:00:00" },
  ]),
  fetchDeal: vi.fn().mockImplementation(async (id: string) => ({
    deal: { id, customer_name: id === "d-1" ? "A" : "B", value: 1, discount_percent: 0, product_type: "standard", customer_segment: "smb", stage: "s", momentum_score: 90, status: "active", created_at: "2026-07-12T00:00:00" },
    approvals: [
      { id: `${id}-ap-pending`, deal_id: id, department: "Finance", approver_id: "finance_raj", status: "pending", predicted_delay_days: 2, actual_delay_days: null, artifact_format_used: null },
      { id: `${id}-ap-approved`, deal_id: id, department: "Legal", approver_id: "legal_sam", status: "approved", predicted_delay_days: 1, actual_delay_days: 1, artifact_format_used: "redline" },
    ],
  })),
}))

import { usePendingApprovals } from "@/hooks/use-pending-approvals"

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe("usePendingApprovals", () => {
  it("flattens pending approvals across all deals, with their deal attached", async () => {
    const { result } = renderHook(() => usePendingApprovals(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0].approval.status).toBe("pending")
    expect(result.current.data![0].deal.id).toBe("d-1")
    expect(result.current.data![1].approval.status).toBe("pending")
    expect(result.current.data![1].deal.id).toBe("d-2")
  })
})
