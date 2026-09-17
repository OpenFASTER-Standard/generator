import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DocumentationView } from "@/components/DocumentationView"
import type { DocumentationResponse } from "@/lib/api"

const documentation: DocumentationResponse = {
  matched: [
    {
      uri: "urn:s1", name: "Matched1", languages: { de: "Deutsch.", en: "English." },
      issues: [{ kind: "length_ratio", detail: "ratio=9.99" }],
    },
  ],
  unmatched: [{ uri: "urn:s2", name: "Unmatched1", languages: { de: "Nur Deutsch." } }],
  ambiguous: [
    { uri: "urn:s3", name: "Ambiguous1", languages: { de: "Mehrdeutig." }, candidates: ["A", "B"] },
  ],
  englishOnly: [],
}

describe("DocumentationView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders all 3 non-empty groups with their real content", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))
    render(<DocumentationView documentation={documentation} search="" />)

    expect(screen.getByText("Matched1")).toBeInTheDocument()
    expect(screen.getByText(/length_ratio/)).toBeInTheDocument()
    expect(screen.getByText("Unmatched1")).toBeInTheDocument()
    expect(screen.getByText("Ambiguous1")).toBeInTheDocument()
    expect(screen.getByText("A")).toBeInTheDocument()
    expect(screen.getByText("B")).toBeInTheDocument()
  })
})
