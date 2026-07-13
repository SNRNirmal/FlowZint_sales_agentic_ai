import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const push = vi.hoisted(() => vi.fn())
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
}))

import { LoginForm } from "@/features/auth/components/LoginForm"
import { useAuthStore } from "@/store/useAuthStore"

beforeEach(() => {
  push.mockClear()
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false })
})

describe("LoginForm (one-click demo login)", () => {
  it("renders a single entry button and no credential fields", () => {
    render(<LoginForm />)
    expect(screen.getByRole("button", { name: /enter as sales ops/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
  })

  it("authenticates the store and navigates to the dashboard on click", async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    await user.click(screen.getByRole("button", { name: /enter as sales ops/i }))

    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(push).toHaveBeenCalledWith("/dashboard")
  })
})
