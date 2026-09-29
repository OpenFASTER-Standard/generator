import { describe, expect, it, vi, beforeEach } from "vitest"
import {
  fetchPages,
  fetchPage,
  fetchCandidates,
  fetchReview,
  submitCitation,
  submitReview,
  describeReference,
  type LeafReference,
  type UnionReference,
} from "./api"

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn())
})

describe("fetchPages", () => {
  it("GETs /api/pages and returns the parsed JSON", async () => {
    const body = { "some-key": { revision_count: 1, current: {} } }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchPages()
    // Asserts only the path -- apiFetch's second argument is whatever the
    // caller happened to pass (undefined for a bare GET), an incidental
    // implementation detail not worth pinning (a future default
    // `init = {}` would break a stricter assertion for no observable
    // behavior change).
    expect((fetch as any).mock.calls[0][0]).toBe("/api/pages")
    expect(result).toEqual(body)
  })

  it("throws with the server's error detail on a non-ok response", async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false, status: 500, text: async () => JSON.stringify({ detail: "boom" }),
    })
    await expect(fetchPages()).rejects.toThrow("boom")
  })

  it("falls back to a generic message when the error body isn't JSON", async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false, status: 502, text: async () => "<html>Bad Gateway</html>",
    })
    await expect(fetchPages()).rejects.toThrow("Server returned 502")
  })
})

describe("fetchPage", () => {
  it("GETs /api/pages/:factKey, encoding the fact key", async () => {
    const body = { fact_key: "a/b", current: {}, history: [] }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchPage("a/b")
    expect(fetch).toHaveBeenCalledWith("/api/pages/a%2Fb", undefined)
    expect(result).toEqual(body)
  })
})

describe("fetchCandidates", () => {
  it("GETs /api/candidates and returns the parsed JSON", async () => {
    const body = { Family: { candidates: [], excluded: [] } }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchCandidates()
    expect(fetch).toHaveBeenCalledWith("/api/candidates", undefined)
    expect(result).toEqual(body)
  })
})

describe("fetchReview", () => {
  it("GETs /api/review and returns the parsed JSON", async () => {
    const body = { flagged: {}, unresolved_families: [], excluded_keys: [], deserialization_failures: [] }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchReview()
    expect(fetch).toHaveBeenCalledWith("/api/review", undefined)
    expect(result).toEqual(body)
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

describe("submitReview", () => {
  it("POSTs the review body as JSON", async () => {
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => ({ fact_key: "k", revision: {} }) })
    await submitReview({ fact_key: "k", leaf_reference_id: "r", reviewer: "r", verdict: "approved", reasoning: "x" })
    expect(fetch).toHaveBeenCalledWith("/api/reviews", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fact_key: "k", leaf_reference_id: "r", reviewer: "r", verdict: "approved", reasoning: "x" }),
    }))
  })
})

describe("describeReference", () => {
  it("describes a Leaf reference via its own subject_document/selector/reference_id", () => {
    const leaf: LeafReference = {
      reference_id: "id1",
      subject_document: { family: "MiKaDiv_FM", version: "1.02", retrieval_uri: "/x.xsd" },
      selector: { type: "XPathSelector", value: "/x" },
      content_hash: { algorithm: "sha256", digest: "abc" },
      captured_at: "2026-01-01T00:00:00Z",
    }
    expect(describeReference(leaf)).toEqual({
      family: "MiKaDiv_FM",
      selectorType: "XPathSelector",
      referenceId: "id1",
    })
  })

  it("describes a Union reference without rendering three blank cells", () => {
    const union: UnionReference = {
      parts: [],
      reference_id: "union-id",
      content_hash: { algorithm: "sha256", digest: "abc" },
    }
    const result = describeReference(union)
    expect(result.referenceId).toBe("union-id")
    expect(result.family).not.toBe("")
    expect(result.selectorType).toBe("Union")
  })
})
