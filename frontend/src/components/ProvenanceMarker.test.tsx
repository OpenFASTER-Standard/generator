import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProvenanceMarker } from "@/components/ProvenanceMarker"

// See LineageGraph.test.tsx's own comment: jsdom cannot create a real 2D
// canvas context, a Cytoscape+jsdom limitation unrelated to this
// component's own logic. ProvenanceMarker now renders LineageGraph
// (its "View lineage" trigger), so this file needs the same mock.
vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({ destroy: vi.fn() })),
}))

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

  it("opens the lineage graph from the expanded citation panel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sourceUri: "citation:xsd?file=/a.xsd&component=%7Bns%7DType",
          generatedAt: "2026-09-15T14:00:00Z",
        }),
      }),
    )

    render(<ProvenanceMarker subject="urn:s" predicate="urn:p" value="hello" lang="de" />)
    await userEvent.click(screen.getByRole("button", { name: "Show provenance" }))
    await screen.findByText(/from \/a\.xsd/i)

    await userEvent.click(screen.getByRole("button", { name: /view lineage/i }))

    expect(await screen.findByTestId("lineage-graph-container")).toBeInTheDocument()
  })
})
