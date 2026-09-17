import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProvenanceMarker } from "@/components/ProvenanceMarker"

describe("ProvenanceMarker", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("fetches and shows a PDF citation image on click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sourceUri: "citation:pdf?path=/a.pdf&page=5&x0=1&top=2&x1=3&bottom=4",
          generatedAt: "2026-09-15T14:00:00Z",
        }),
      }),
    )

    render(<ProvenanceMarker subject="urn:s" predicate="urn:p" value="hello" lang="en" />)
    await userEvent.click(screen.getByRole("button"))

    expect(await screen.findByRole("img")).toBeInTheDocument()
  })

  it("shows a plain note when no provenance is recorded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))

    render(<ProvenanceMarker subject="urn:s" predicate="urn:p" value="hello" />)
    await userEvent.click(screen.getByRole("button"))

    expect(await screen.findByText(/no source recorded/i)).toBeInTheDocument()
  })
})
