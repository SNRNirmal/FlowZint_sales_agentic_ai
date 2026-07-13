import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const okJson = (payload: unknown) => ({
  ok: true,
  status: 200,
  json: async () => payload,
  text: async () => JSON.stringify(payload),
})

const deal = {
  id: "d-1",
  customer_name: "Northwind",
  value: 180000,
  discount_percent: 18,
  product_type: "custom",
  customer_segment: "enterprise",
  stage: "verbal_agreement",
  momentum_score: 72,
  status: "active",
  created_at: "2026-07-12T10:00:00",
}

describe("lib/api", () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock)
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("parses a valid deals payload", async () => {
    fetchMock.mockResolvedValueOnce(okJson([deal]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).resolves.toEqual([deal])
  })

  it("rejects loudly when the response shape drifts", async () => {
    fetchMock.mockResolvedValueOnce(okJson([{ ...deal, value: "not-a-number" }]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).rejects.toThrow(/Unexpected API response/)
  })

  it("surfaces HTTP errors as ApiError with status and body", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Deal not found" }),
      text: async () => '{"detail":"Deal not found"}',
    })
    const { fetchDeal, ApiError } = await import("@/lib/api")

    let caught: unknown
    try {
      await fetchDeal("missing")
    } catch (err) {
      caught = err
    }

    expect(caught).toBeInstanceOf(ApiError)
    const error = caught as InstanceType<typeof ApiError>
    expect(error.status).toBe(404)
    expect(error.body).toContain("Deal not found")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it("sends the nudge as a query parameter", async () => {
    fetchMock.mockResolvedValueOnce(okJson({ status: "sent", approval_id: "ap-1" }))
    const { sendApprovalNudge } = await import("@/lib/api")
    await sendApprovalNudge("ap-1", "Hello world")
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain("/approvals/ap-1/send?nudge_text=Hello+world")
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST")
  })

  it("retries a GET exactly once on network failure", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(okJson([deal]))
    const { fetchDeals } = await import("@/lib/api")
    await expect(fetchDeals()).resolves.toEqual([deal])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it("never retries a mutation on network failure", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"))
    const { holdApprovalNudge } = await import("@/lib/api")
    await expect(holdApprovalNudge("ap-1")).rejects.toThrow()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
