import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { StructureView } from "@/components/StructureView"
import type { DeclarationsResponse, StructureResponse } from "@/lib/api"

const structure: StructureResponse = {
  "https://example.org/test": {
    complexTypes: [
      {
        uri: "https://example.org/test#WidgetType",
        name: "WidgetType",
        abstract: false,
        extends: null,
        contentModel: { kind: "Sequence", particles: [] },
        attributeUses: [],
        identityConstraints: [],
      },
    ],
    simpleTypes: [
      {
        uri: "https://example.org/test#CodeType",
        name: "CodeType",
        facets: { maxLength: 10 },
        enumeration: [],
        patterns: [],
        unionMembers: [],
      },
    ],
  },
}
const declarations: DeclarationsResponse = {}

describe("StructureView", () => {
  it("renders every complex and simple type", () => {
    render(<StructureView structure={structure} declarations={declarations} search="" />)

    expect(screen.getByText("WidgetType")).toBeInTheDocument()
    expect(screen.getByText("CodeType")).toBeInTheDocument()
    expect(screen.getByText(/maxLength=10/)).toBeInTheDocument()
  })

  it("filters by a case-insensitive name substring", () => {
    render(<StructureView structure={structure} declarations={declarations} search="widget" />)

    expect(screen.getByText("WidgetType")).toBeInTheDocument()
    expect(screen.queryByText("CodeType")).not.toBeInTheDocument()
  })
})
