import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

describe("test harness", () => {
  it("renders JSX into jsdom", () => {
    render(<div>harness works</div>)
    expect(screen.getByText("harness works")).toBeInTheDocument()
  })
})
