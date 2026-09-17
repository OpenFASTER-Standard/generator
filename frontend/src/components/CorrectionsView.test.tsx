import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CorrectionsView } from "@/components/CorrectionsView"

const pending = [
  { correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Fixed.", proposer: "julian" },
]

describe("CorrectionsView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("disables approve/reject for the correction's own proposer", () => {
    render(<CorrectionsView pending={pending} reviewer="julian" onDecided={() => {}} />)

    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /reject/i })).toBeDisabled()
  })

  it("lets a different reviewer approve, and calls onDecided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ decisionUri: "urn:d1" }) }))
    const onDecided = vi.fn()

    render(<CorrectionsView pending={pending} reviewer="someone-else" onDecided={onDecided} />)
    await userEvent.click(screen.getByRole("button", { name: /approve/i }))
    await userEvent.click(screen.getByRole("button", { name: /confirm/i }))

    expect(onDecided).toHaveBeenCalled()
  })
})
