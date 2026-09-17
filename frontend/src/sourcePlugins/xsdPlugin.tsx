import { useEffect, useState } from "react"
import { apiGet } from "@/lib/api"
import type { XsdLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

interface XsdCitation {
  fragment: string
  sourceFile: string
}

// A top-level (direct child of <xs:schema>) named component's own
// start/end character offset in the raw file text, and the qname it
// represents -- the real granularity this corpus's XSD citation data
// actually has (see this plan's Global Constraints). Regex-based, not a
// full XML parse: this project's own extraction code (extraction/*.py)
// already establishes precedent for regex/state-machine parsing of this
// corpus's real files rather than pulling in a full XML tooling layer
// for a UI-only concern.
interface ComponentSpan {
  qname: string
  start: number
  end: number
}

function findTargetNamespace(xml: string): string {
  const match = xml.match(/<xs:schema\b[^>]*\btargetNamespace="([^"]*)"/)
  return match ? match[1] : ""
}

function findComponentSpans(xml: string, targetNamespace: string): ComponentSpan[] {
  const spans: ComponentSpan[] = []
  const topLevelPattern =
    /<xs:(complexType|simpleType|element)\b[^>]*\bname="([^"]+)"[^>]*>[\s\S]*?<\/xs:\1>/g
  let match: RegExpExecArray | null
  while ((match = topLevelPattern.exec(xml)) !== null) {
    spans.push({
      qname: `{${targetNamespace}}${match[2]}`,
      start: match.index,
      end: match.index + match[0].length,
    })
  }
  return spans
}

function XsdWhole({ locator, onLocatorClick }: { locator: XsdLocator; onLocatorClick: (l: XsdLocator) => void }) {
  const [content, setContent] = useState<string | null>(null)

  useEffect(() => {
    setContent(null)
    apiGet<{ content: string }>(`/sources/xsd/file?file=${encodeURIComponent(locator.file)}`).then((result) =>
      setContent(result.content),
    )
  }, [locator.file])

  if (content === null) return <p className="text-xs text-muted-foreground">Loading...</p>

  const targetNamespace = findTargetNamespace(content)
  const spans = findComponentSpans(content, targetNamespace)

  const pieces: { text: string; qname: string | null }[] = []
  let cursor = 0
  for (const span of spans) {
    if (span.start > cursor) pieces.push({ text: content.slice(cursor, span.start), qname: null })
    pieces.push({ text: content.slice(span.start, span.end), qname: span.qname })
    cursor = span.end
  }
  if (cursor < content.length) pieces.push({ text: content.slice(cursor), qname: null })

  return (
    <pre className="max-h-[80vh] overflow-auto rounded border bg-muted/30 p-2 text-xs">
      {pieces.map((piece, index) =>
        piece.qname ? (
          <span
            key={index}
            className="cursor-pointer hover:bg-accent"
            onClick={() => onLocatorClick({ kind: "xsd", file: locator.file, component: piece.qname! })}
          >
            {piece.text}
          </span>
        ) : (
          <span key={index}>{piece.text}</span>
        ),
      )}
    </pre>
  )
}

function XsdLocatorCitation({ locator }: { locator: XsdLocator }) {
  const [fragment, setFragment] = useState<XsdCitation | null>(null)
  useEffect(() => {
    setFragment(null)
    const params = new URLSearchParams({ file: locator.file, type_qname: locator.component })
    apiGet<XsdCitation>(`/citations/xsd?${params.toString()}`).then(setFragment)
  }, [locator.file, locator.component])

  if (fragment === null) return <p className="text-xs text-muted-foreground">Loading...</p>
  return (
    <code className="block max-w-full overflow-auto rounded border bg-muted/30 p-2 text-xs whitespace-pre-wrap break-all">
      {fragment.fragment}
    </code>
  )
}

export const xsdPlugin: SourcePlugin<XsdLocator> = {
  kind: "xsd",
  renderLocator(locator) {
    return <XsdLocatorCitation locator={locator} />
  },
  renderWhole(locator, onLocatorClick) {
    return <XsdWhole locator={locator} onLocatorClick={onLocatorClick} />
  },
}
