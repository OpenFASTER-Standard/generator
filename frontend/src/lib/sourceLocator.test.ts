import { describe, expect, it } from "vitest"
import { parseSourceUri } from "@/lib/sourceLocator"

describe("parseSourceUri", () => {
  it("parses a PDF locator with a bbox", () => {
    const locator = parseSourceUri(
      "citation:pdf?path=/a/b.pdf&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179",
    )
    expect(locator).toEqual({
      kind: "pdf", path: "/a/b.pdf", page: 196, bbox: [137.64, 610.179, 223.878, 619.179],
    })
  })

  it("parses a PDF locator without a bbox", () => {
    const locator = parseSourceUri("citation:pdf?path=/a/b.pdf&page=5")
    expect(locator).toEqual({ kind: "pdf", path: "/a/b.pdf", page: 5 })
  })

  it("parses an XSD locator", () => {
    const locator = parseSourceUri("citation:xsd?file=/a/b.xsd&component=%7Burn%3Ans%7DTypeName")
    expect(locator).toEqual({ kind: "xsd", file: "/a/b.xsd", component: "{urn:ns}TypeName" })
  })

  it("returns null for an unrecognized scheme", () => {
    expect(parseSourceUri("https://example.org/x")).toBeNull()
  })
})
