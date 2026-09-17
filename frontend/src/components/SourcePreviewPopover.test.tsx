import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { SourcePreviewPopover } from "@/components/SourcePreviewPopover"

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe("SourcePreviewPopover", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("fetches and shows a PDF citation image on hover, not click", async () => {
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

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" lang="en" />)
    await userEvent.hover(screen.getByText("hello"))

    expect(await screen.findByRole("img")).toBeInTheDocument()
  })

  it("shows a plain note when no provenance is recorded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" />)
    await userEvent.hover(screen.getByText("hello"))

    expect(await screen.findByText(/no source recorded/i)).toBeInTheDocument()
  })

  it("marks the value as backed by a source with a distinct visual style", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ sourceUri: "citation:pdf?path=/a.pdf&page=5", generatedAt: "t" }),
      }),
    )

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" />)

    expect(screen.getByText("hello")).toHaveClass("underline")
  })
})
