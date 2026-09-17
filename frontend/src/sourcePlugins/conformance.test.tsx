import { render } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PLUGINS } from "@/sourcePlugins/registry"
import type { PdfLocator, XsdLocator } from "@/lib/sourceLocator"

const SAMPLE_LOCATORS: Record<string, PdfLocator | XsdLocator> = {
  pdf: { kind: "pdf", path: "/a.pdf", page: 5, bbox: [1, 2, 3, 4] },
  xsd: { kind: "xsd", file: "/a.xsd", component: "{urn:ns}Type" },
}

describe("source plugin conformance", () => {
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
  }

  it("has both real plugins registered", () => {
    expect(Object.keys(PLUGINS).sort()).toEqual(["pdf", "xsd"])
  })
})
