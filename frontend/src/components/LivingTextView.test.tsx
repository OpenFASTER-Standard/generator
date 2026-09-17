import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { LivingTextView } from "@/components/LivingTextView"
import type { DocumentationResponse } from "@/lib/api"

const documentation: DocumentationResponse = {
  matched: [{ uri: "urn:s1", name: "Matched1", languages: { de: "Deutsch.", en: "English." } }],
  unmatched: [{ uri: "urn:s2", name: "Unmatched1", languages: { de: "Nur Deutsch." } }],
  ambiguous: [],
  englishOnly: [],
}

describe("LivingTextView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders matched and unmatched entries, with an inline pending correction shown", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))
    const pending = [{ correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Neu.", proposer: "julian" }]

    render(
      <MemoryRouter>
        <LivingTextView documentation={documentation} pending={pending} reviewer="someone-else" search="" onDecided={() => {}} />
      </MemoryRouter>,
    )

    expect(screen.getByText("Matched1")).toBeInTheDocument()
    expect(screen.getByText("Unmatched1")).toBeInTheDocument()
    expect(screen.getByText("Neu.")).toBeInTheDocument()
  })
})
