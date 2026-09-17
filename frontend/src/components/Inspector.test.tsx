import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { Inspector } from "@/components/Inspector"

describe("Inspector", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the citation and the reverse-lookup list of other facts from the same source", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/provenance")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ sourceUri: "citation:pdf?path=/a.pdf&page=196", generatedAt: "t" }),
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => [
            { subject: "urn:other1", predicate: "urn:doc", object: "Other fact 1" },
            { subject: "urn:other2", predicate: "urn:doc", object: "Other fact 2" },
          ],
        })
      }),
    )

    render(
      <MemoryRouter>
        <Inspector subject="urn:s" predicate="urn:doc" value="hello" lang="en" />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/2 other facts/i)).toBeInTheDocument()
  })
})
