import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { LineageGraph } from "@/components/LineageGraph"

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
