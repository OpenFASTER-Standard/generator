import { describe, expect, it, vi, beforeEach } from "vitest"
import { fetchPages, submitCitation } from "./api"

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn())
})

describe("fetchPages", () => {
  it("GETs /api/pages and returns the parsed JSON", async () => {
    const body = { "some-key": { revision_count: 1, current: {} } }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchPages()
    expect(fetch).toHaveBeenCalledWith("/api/pages", undefined)
    expect(result).toEqual(body)
  })

  it("throws with the server's error detail on a non-ok response", async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false, status: 500, text: async () => JSON.stringify({ detail: "boom" }),
    })
    await expect(fetchPages()).rejects.toThrow("boom")
  })
})

describe("submitCitation", () => {
  it("POSTs the citation body as JSON", async () => {
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => ({ fact_key: "k", revision: {} }) })
    await submitCitation({ family: "f", xpath: "x", fact_key: "k", author: "a", comment: "c", is_correction: false })
    expect(fetch).toHaveBeenCalledWith("/api/citations", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }))
  })
})
