export interface PdfLocator {
  kind: "pdf"
  path: string
  page: number
  bbox?: [number, number, number, number]
}

export interface XsdLocator {
  kind: "xsd"
  file: string
  component: string
}

export type SourceLocator = PdfLocator | XsdLocator

// Mirrors citations/locator.py's source_uri_to_locator exactly -- same
// scheme, same field names. new URL() can't parse a "citation:" scheme
// directly (no host component), so query params are parsed via
// URLSearchParams against everything after the first "?".
export function parseSourceUri(sourceUri: string): SourceLocator | null {
  const queryStart = sourceUri.indexOf("?")
  if (queryStart === -1) return null
  const scheme = sourceUri.slice(0, queryStart)
  const params = new URLSearchParams(sourceUri.slice(queryStart + 1))

  if (scheme === "citation:pdf") {
    const path = params.get("path")
    const page = params.get("page")
    if (path === null || page === null) return null
    const x0 = params.get("x0")
    const top = params.get("top")
    const x1 = params.get("x1")
    const bottom = params.get("bottom")
    const bbox: [number, number, number, number] | undefined =
      x0 !== null && top !== null && x1 !== null && bottom !== null
        ? [Number(x0), Number(top), Number(x1), Number(bottom)]
        : undefined
    return bbox
      ? { kind: "pdf", path, page: Number(page), bbox }
      : { kind: "pdf", path, page: Number(page) }
  }

  if (scheme === "citation:xsd") {
    const file = params.get("file")
    const component = params.get("component")
    if (file === null || component === null) return null
    return { kind: "xsd", file, component }
  }

  return null
}
