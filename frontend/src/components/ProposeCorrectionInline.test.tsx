import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProposeCorrectionInline } from "@/components/ProposeCorrectionInline"

describe("ProposeCorrectionInline", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lets a reviewer edit and submit a new proposed value", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ correctionUri: "urn:c1" }) })
    vi.stubGlobal("fetch", fetchMock)
    const onProposed = vi.fn()

    render(
      <ProposeCorrectionInline
        subject="urn:s" predicate="urn:p" language="de" currentValue="Original."
        reviewer="julian" onProposed={onProposed}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: /edit/i }))
    const textbox = screen.getByRole("textbox")
    await userEvent.clear(textbox)
    await userEvent.type(textbox, "Corrected.")
    await userEvent.click(screen.getByRole("button", { name: /propose/i }))

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/corrections",
      expect.objectContaining({ method: "POST" }),
    )
    expect(onProposed).toHaveBeenCalled()
  })
})
