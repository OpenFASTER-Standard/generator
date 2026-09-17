import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { InlineCorrection } from "@/components/InlineCorrection"

const correction = { correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Fixed.", proposer: "julian" }

describe("InlineCorrection", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the proposed value and disables decisions for the correction's own proposer", () => {
    render(<InlineCorrection correction={correction} reviewer="julian" onDecided={() => {}} />)

    expect(screen.getByText("Fixed.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled()
  })

  it("lets a different reviewer approve and calls onDecided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ decisionUri: "urn:d1" }) }))
    const onDecided = vi.fn()

    render(<InlineCorrection correction={correction} reviewer="someone-else" onDecided={onDecided} />)
    await userEvent.click(screen.getByRole("button", { name: /approve/i }))

    expect(onDecided).toHaveBeenCalled()
  })
})
