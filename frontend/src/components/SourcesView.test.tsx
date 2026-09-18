import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SourcesView } from "@/components/SourcesView"

const FILES = [
  { path: "/repo/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd", kind: "xsd", githubUrl: "https://github.com/Org/repo/blob/main/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd" },
  { path: "/repo/mikadiv-fm/sources/khb/annex.pdf", kind: "pdf", githubUrl: "https://github.com/Org/repo/blob/main/mikadiv-fm/sources/khb/annex.pdf" },
]

describe("SourcesView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lists every real source file with its repo-relative path as a real GitHub link", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => FILES }))

    render(<SourcesView />)

    const xsdLink = await screen.findByRole("link", { name: "mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd" })
    expect(xsdLink).toHaveAttribute("href", FILES[0].githubUrl)
    expect(xsdLink).toHaveAttribute("target", "_blank")

    const pdfLink = screen.getByRole("link", { name: "mikadiv-fm/sources/khb/annex.pdf" })
    expect(pdfLink).toHaveAttribute("href", FILES[1].githubUrl)

    // Not the local filesystem path leaking through anywhere.
    expect(screen.queryByText(FILES[0].path)).not.toBeInTheDocument()
  })

  it("falls back to the raw path for a file with no known GitHub source", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ path: "/tmp/outside-the-repo.xsd", kind: "xsd", githubUrl: null }],
      }),
    )

    render(<SourcesView />)

    expect(await screen.findByText("/tmp/outside-the-repo.xsd")).toBeInTheDocument()
    expect(screen.queryByRole("link")).not.toBeInTheDocument()
  })
})
