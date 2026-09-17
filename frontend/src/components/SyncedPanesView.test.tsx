import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SyncedPanesView } from "@/components/SyncedPanesView"

describe("SyncedPanesView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the PDF source by default and lists derived facts after clicking a page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/sources/lookup")) {
          return Promise.resolve({
            ok: true,
            json: async () => [{ subject: "urn:s1", predicate: "urn:p", object: "Derived fact 1" }],
          })
        }
        return Promise.resolve({ ok: true, blob: async () => new Blob() })
      }),
    )

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    await userEvent.click(screen.getByRole("img", { name: /page 1/i }))

    expect(await screen.findByText("Derived fact 1")).toBeInTheDocument()
  })

  it("lets you switch to an XSD source via the source picker", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ content: "<xs:schema/>" }) }))

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(screen.getByRole("option", { name: "/a.xsd" }))

    expect(await screen.findByText(/<xs:schema/)).toBeInTheDocument()
  })
})
