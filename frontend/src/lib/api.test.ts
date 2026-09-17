import { afterEach, describe, expect, it, vi } from "vitest"
import { apiGet, apiPost, toUrlSafeBase64 } from "@/lib/api"

describe("apiGet", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("fetches from /api and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hello: "world" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await apiGet<{ hello: string }>("/structure")

    expect(fetchMock).toHaveBeenCalledWith("/api/structure", undefined)
    expect(result).toEqual({ hello: "world" })
  })

  it("throws with the status code on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    )

    await expect(apiGet("/missing")).rejects.toThrow("404")
  })
})

describe("apiPost", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("sends a JSON body with the reviewer header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ correctionUri: "urn:x" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await apiPost<{ correctionUri: string }>(
      "/corrections",
      { targetSubject: "urn:s" },
      "julian",
    )

    expect(fetchMock).toHaveBeenCalledWith("/api/corrections", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Reviewer": "julian" },
      body: JSON.stringify({ targetSubject: "urn:s" }),
    })
    expect(result).toEqual({ correctionUri: "urn:x" })
  })
})

describe("toUrlSafeBase64", () => {
  it("produces the same alphabet as Python's base64.urlsafe_b64encode, not plain btoa()", () => {
    // Bytes 255,255,255,254,253 -- chosen because standard base64 of them
    // is "/////v0=" (real, confirmed via Python's base64.b64encode), which
    // would silently break as a URL path segment. Python's own
    // base64.urlsafe_b64encode of the same bytes is "_____v0=" -- this
    // must match exactly, since the backend decodes with
    // base64.urlsafe_b64decode.
    const text = String.fromCharCode(255, 255, 255, 254, 253)

    const result = toUrlSafeBase64(text)

    expect(result).toBe("_____v0=")
    expect(result).not.toMatch(/[+/]/)
  })
})
