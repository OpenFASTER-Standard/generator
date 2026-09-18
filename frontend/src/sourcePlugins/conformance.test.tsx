import { fireEvent, render, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { PLUGINS } from "@/sourcePlugins/registry"
import type { PdfLocator, XsdLocator } from "@/lib/sourceLocator"

const SAMPLE_LOCATORS: Record<string, PdfLocator | XsdLocator> = {
  pdf: { kind: "pdf", path: "/a.pdf", page: 5, bbox: [1, 2, 3, 4] },
  xsd: { kind: "xsd", file: "/a.xsd", component: "{urn:ns}Type" },
}

// XsdWhole fetches the raw file content via apiGet before it can render any
// clickable spans -- give it a small, real-shaped XSD whose one top-level
// named component ("Type", in the same "urn:ns" targetNamespace as
// SAMPLE_LOCATORS.xsd above) findComponentSpans can actually find, so the
// round-trip test below has something real to click.
const SAMPLE_XSD_CONTENT =
  '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:ns">\n' +
  '  <xs:complexType name="Type">\n' +
  "    <xs:sequence/>\n" +
  "  </xs:complexType>\n" +
  "</xs:schema>"

// Fires the real, plugin-specific "click something clickable" gesture for
// each kind's own renderWhole output, per the design spec's own conformance
// requirement to "render a locator; round-trip a click back to a locator" --
// PDF's whole-view is a single clickable <img> (page-level granularity),
// XSD's is one or more clickable <span>s with qnames (component-level).
const CLICK_TARGETS: Record<string, (container: HTMLElement) => HTMLElement | null> = {
  pdf: (container) => container.querySelector("img"),
  xsd: (container) => container.querySelector("span.cursor-pointer"),
}

describe("source plugin conformance", () => {
  afterEach(() => vi.unstubAllGlobals())

  for (const [kind, plugin] of Object.entries(PLUGINS)) {
    it(`${kind} plugin's renderLocator renders something without throwing`, () => {
      const locator = SAMPLE_LOCATORS[kind]
      expect(() => render(<div>{plugin.renderLocator(locator as never)}</div>)).not.toThrow()
    })

    it(`${kind} plugin's renderWhole accepts an onLocatorClick callback without throwing`, () => {
      const locator = SAMPLE_LOCATORS[kind]
      const onLocatorClick = vi.fn()
      expect(() =>
        render(<div>{plugin.renderWhole(locator as never, onLocatorClick)}</div>),
      ).not.toThrow()
    })

    it(`${kind} plugin's own kind matches its registry key`, () => {
      expect(plugin.kind).toBe(kind)
    })

    it(`${kind} plugin's renderWhole round-trips a real click back into a locator`, async () => {
      if (kind === "xsd") {
        vi.stubGlobal(
          "fetch",
          vi.fn().mockResolvedValue({ ok: true, json: async () => ({ content: SAMPLE_XSD_CONTENT }) }),
        )
      }

      const locator = SAMPLE_LOCATORS[kind]
      const onLocatorClick = vi.fn()
      const { container } = render(<div>{plugin.renderWhole(locator as never, onLocatorClick)}</div>)

      const target = await waitFor(() => {
        const element = CLICK_TARGETS[kind](container)
        expect(element).not.toBeNull()
        return element as HTMLElement
      })
      fireEvent.click(target)

      expect(onLocatorClick).toHaveBeenCalledTimes(1)
      const clicked = onLocatorClick.mock.calls[0][0]
      expect(clicked.kind).toBe(kind)

      if (kind === "pdf") {
        // Page-level granularity: clicking the whole-page image round-trips
        // the same page number the plugin was given, not a sub-region.
        expect(clicked.page).toBe((locator as PdfLocator).page)
      } else if (kind === "xsd") {
        // Component-level granularity: clicking a specific span round-trips
        // that span's own real qname (from the fetched file content), not
        // just an echo of the locator's original component.
        expect(clicked.component).toBe("{urn:ns}Type")
      }
    })
  }

  it("has both real plugins registered", () => {
    expect(Object.keys(PLUGINS).sort()).toEqual(["pdf", "xsd"])
  })
})
