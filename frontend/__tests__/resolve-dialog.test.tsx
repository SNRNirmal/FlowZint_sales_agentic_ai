import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

vi.mock("@/lib/api", () => ({
  resolveApproval: vi.fn().mockResolvedValue({ status: "approved", new_momentum_score: 87 }),
}))

import { resolveApproval } from "@/lib/api"
import { ResolveDialog } from "@/components/deals/ResolveDialog"

function renderDialog() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ResolveDialog approvalId="ap-1" approverId="finance_raj" />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe("ResolveDialog", () => {
  it("submits the outcome and shows the recomputed momentum", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    await user.type(screen.getByLabelText(/actual delay/i), "2.5")
    await user.type(screen.getByLabelText(/artifact format/i), "one-pager")
    await user.click(screen.getByRole("button", { name: /save outcome/i }))

    expect(resolveApproval).toHaveBeenCalledWith("ap-1", {
      actual_delay_days: 2.5,
      artifact_format_used: "one-pager",
      delay_reason: "",
    })
    expect(await screen.findByText(/momentum now 87/i)).toBeInTheDocument()
  })

  it("does not submit without required fields", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    expect(screen.getByRole("button", { name: /save outcome/i })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: /save outcome/i }))

    expect(resolveApproval).not.toHaveBeenCalled()
  })

  it("rejects a negative delay", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    await user.type(screen.getByLabelText(/actual delay/i), "-3")
    await user.type(screen.getByLabelText(/artifact format/i), "one-pager")

    expect(screen.getByRole("button", { name: /save outcome/i })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: /save outcome/i }))
    expect(resolveApproval).not.toHaveBeenCalled()
  })

  it("reset on close clears the success panel", async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    await user.type(screen.getByLabelText(/actual delay/i), "2.5")
    await user.type(screen.getByLabelText(/artifact format/i), "one-pager")
    await user.click(screen.getByRole("button", { name: /save outcome/i }))
    expect(await screen.findByText(/momentum now 87/i)).toBeInTheDocument()

    await user.keyboard("{Escape}")

    await user.click(screen.getByRole("button", { name: /record outcome/i }))
    expect(screen.getByLabelText<HTMLInputElement>(/actual delay/i).value).toBe("")
    expect(screen.queryByText(/momentum now/i)).not.toBeInTheDocument()
  })
})
