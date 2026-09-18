import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SyncedPanesView } from "@/components/SyncedPanesView"

function stubFetch(overrides: (url: string) => Response | Promise<Response> | undefined) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const overridden = overrides(url)
      if (overridden !== undefined) return Promise.resolve(overridden)
      if (url.includes("/sources/pdf/info")) {
        return Promise.resolve({ ok: true, json: async () => ({ totalPages: 262 }) })
      }
      // Both plugins now auto-fire a real lookup the moment they show a
      // location (so a test that doesn't care about the lookup value --
      // e.g. one only exercising the source picker -- still needs a
      // real, parseable JSON response here, not the raw-image blob
      // fallback apiGet() can't .json() on).
      if (url.includes("/sources/lookup")) {
        return Promise.resolve({ ok: true, json: async () => [] })
      }
      return Promise.resolve({ ok: true, blob: async () => new Blob() })
    }),
  )
}

describe("SyncedPanesView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the PDF source by default and lists real derived facts immediately, with no click needed", async () => {
    stubFetch((url) => {
      if (url.includes("/sources/lookup")) {
        return { ok: true, json: async () => [{ subject: "urn:s1", predicate: "urn:p", object: "Derived fact 1" }] } as Response
      }
      return undefined
    })

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    // Not "click the image to see facts" -- both plugins now look up their
    // starting location automatically, so the right pane should already
    // show real content without any interaction.
    expect(await screen.findByText("Derived fact 1")).toBeInTheDocument()
  })

  it("shows an honest empty state when a location genuinely has no derived facts", async () => {
    stubFetch((url) => {
      if (url.includes("/sources/lookup")) return { ok: true, json: async () => [] } as Response
      return undefined
    })

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    expect(await screen.findByText(/nothing was derived from this exact location/i)).toBeInTheDocument()
  })

  it("lets you page through the PDF, refreshing derived facts for the new page", async () => {
    stubFetch((url) => {
      if (url.includes("/sources/lookup")) {
        const page = new URL(url, "http://x").searchParams.get("page")
        return {
          ok: true,
          json: async () => [{ subject: "urn:s1", predicate: "urn:p", object: `Fact for page ${page}` }],
        } as Response
      }
      return undefined
    })

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    expect(await screen.findByText("Fact for page 1")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled()

    await userEvent.click(screen.getByRole("button", { name: /next/i }))

    expect(await screen.findByText("Fact for page 2")).toBeInTheDocument()
    expect(screen.getByRole("img", { name: /page 2/i })).toBeInTheDocument()
    expect(screen.getByText(/page 2 of 262/i)).toBeInTheDocument()
  })

  it("lets you switch to an XSD source via the source picker", async () => {
    stubFetch((url) => {
      if (url.includes("/sources/xsd/file")) return { ok: true, json: async () => ({ content: "<xs:schema/>" }) } as Response
      return undefined
    })

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(screen.getByRole("option", { name: "/a.xsd" }))

    expect(await screen.findByText(/<xs:schema/)).toBeInTheDocument()
  })

  it("does NOT leave stale derived facts when switching source", async () => {
    stubFetch((url) => {
      if (url.includes("/sources/lookup")) {
        return { ok: true, json: async () => [{ subject: "urn:s1", predicate: "urn:p", object: "Derived fact 1" }] } as Response
      }
      if (url.includes("/sources/xsd/file")) return { ok: true, json: async () => ({ content: "<xs:schema/>" }) } as Response
      return undefined
    })

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    expect(await screen.findByText("Derived fact 1")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(screen.getByRole("option", { name: "/a.xsd" }))

    await screen.findByText(/<xs:schema/)
    expect(screen.queryByText("Derived fact 1")).not.toBeInTheDocument()
  })
})
