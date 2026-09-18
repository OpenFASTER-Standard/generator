import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { TripleCountsView } from "@/components/TripleCountsView"

const SUMMARY = {
  total: 100,
  categories: [
    {
      key: "documentation" as const,
      label: "Documentation text",
      count: 40,
      predicates: [{ predicate: "https://purl.openfaster.org/xsdo/documentation", label: "xsdo:documentation", count: 40 }],
    },
    {
      key: "provenance" as const,
      label: "Provenance & citations",
      count: 35,
      predicates: [
        { predicate: "http://www.w3.org/ns/prov#hasProvenanceRecord", label: "prov:hasProvenanceRecord", count: 20 },
        { predicate: "http://www.w3.org/ns/prov#wasDerivedFrom", label: "prov:wasDerivedFrom", count: 15 },
      ],
    },
    {
      key: "structural" as const,
      label: "Structural schema facts",
      count: 25,
      predicates: [
        { predicate: "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", label: "rdf:type", count: 15 },
        { predicate: "https://purl.openfaster.org/xsdo/type", label: "xsdo:type", count: 10 },
      ],
    },
  ],
}

describe("TripleCountsView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the real total and a legend for every category", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => SUMMARY }))

    render(<TripleCountsView />)

    expect(await screen.findByText(/100 triples/)).toBeInTheDocument()
    expect(screen.getByText("Documentation text")).toBeInTheDocument()
    expect(screen.getByText("Provenance & citations")).toBeInTheDocument()
    expect(screen.getByText("Structural schema facts")).toBeInTheDocument()
  })

  it("shows a table view with every real predicate, label, count, and share -- not just the treemap", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => SUMMARY }))

    render(<TripleCountsView />)
    await screen.findByText(/100 triples/)

    await userEvent.click(screen.getByRole("button", { name: /show as table/i }))

    // Not just the two label collisions ("type") disambiguated -- the
    // actual real distinguishing labels this store produces, each with
    // its own real count on the same row.
    const rdfTypeRow = screen.getByText("rdf:type").closest("tr")!
    expect(within(rdfTypeRow).getByText("15")).toBeInTheDocument()
    const xsdoTypeRow = screen.getByText("xsdo:type").closest("tr")!
    expect(within(xsdoTypeRow).getByText("10")).toBeInTheDocument()
  })

  it("shows a real tooltip with the exact count and share on hovering a tile", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => SUMMARY }))

    render(<TripleCountsView />)
    await screen.findByText(/100 triples/)

    const img = screen.getByRole("img", { name: /treemap/i })
    const firstTile = img.querySelector("rect")!
    await userEvent.hover(firstTile)

    expect(await screen.findByText(/triples \(\d+\.\d%\)/)).toBeInTheDocument()
  })
})
