import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { LineageGraph } from "@/components/LineageGraph"

// jsdom cannot create a real 2D canvas context (a known Cytoscape+jsdom
// limitation, not something this component's own logic can fix -- see
// LineageGraph.tsx's own comment on why initialization moved to a ref
// callback). Verifying Cytoscape's internal canvas rendering isn't this
// component's job; mocking it here confirms this component wires a real
// container and calls the library, without depending on jsdom having a
// real canvas backend.
vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({ destroy: vi.fn() })),
}))

describe("LineageGraph", () => {
  it("renders a graph container when open with a real source", () => {
    render(
      <LineageGraph
        open
        onOpenChange={() => {}}
        subject="urn:s"
        predicate="urn:p"
        sourceUri="citation:xsd?file=/a.xsd&component=%7Bns%7DType"
      />,
    )

    expect(screen.getByTestId("lineage-graph-container")).toBeInTheDocument()
  })
})
