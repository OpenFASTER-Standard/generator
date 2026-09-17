import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { GraphView } from "@/components/GraphView"
import type { AuditResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

const structure: StructureResponse = {
  "https://example.org/ns1": {
    complexTypes: [
      {
        uri: "https://example.org/ns1#TypeA", name: "TypeA", abstract: false, extends: null,
        contentModel: { kind: "Sequence", particles: [] }, attributeUses: [], identityConstraints: [],
      },
    ],
    simpleTypes: [],
  },
}
const documentation: DocumentationResponse = {
  matched: [{ uri: "https://example.org/ns1#TypeA", name: "TypeA", languages: { de: "x", en: "y" } }],
  unmatched: [], ambiguous: [], englishOnly: [],
}
const audit: AuditResponse = {
  attachment: { attached: 1, ambiguous: 0, unmatched: 0 },
  coverage: { total: 1, attached: 1, ambiguous: 0, unmatched: 0 },
  issues: [],
}

describe("GraphView", () => {
  it("starts at the namespace-level overview", () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    expect(screen.getByText("https://example.org/ns1")).toBeInTheDocument()
  })

  it("zooming into a namespace shows its types", async () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByText("https://example.org/ns1"))

    expect(await screen.findByText("TypeA")).toBeInTheDocument()
  })

  it("has an unmatched-status filter toggle", () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    expect(screen.getByRole("checkbox", { name: /unmatched/i })).toBeInTheDocument()
  })
})
