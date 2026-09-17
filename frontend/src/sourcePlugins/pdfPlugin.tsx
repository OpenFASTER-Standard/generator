import type { PdfLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

function PdfPage({ locator, onLocatorClick }: { locator: PdfLocator; onLocatorClick: (l: PdfLocator) => void }) {
  return (
    <div>
      <img
        src={`/api/sources/pdf/page?path=${encodeURIComponent(locator.path)}&page=${locator.page}`}
        alt={`Page ${locator.page}`}
        className="w-full cursor-pointer rounded border"
        onClick={() => onLocatorClick({ kind: "pdf", path: locator.path, page: locator.page })}
      />
      <p className="text-xs text-muted-foreground">Page {locator.page}</p>
    </div>
  )
}

export const pdfPlugin: SourcePlugin<PdfLocator> = {
  kind: "pdf",
  renderLocator(locator) {
    if (!locator.bbox) return <p className="text-xs text-muted-foreground">Page {locator.page} (no exact region).</p>
    const [x0, top, x1, bottom] = locator.bbox
    const params = new URLSearchParams({
      path: locator.path, page: String(locator.page),
      x0: String(x0), top: String(top), x1: String(x1), bottom: String(bottom),
    })
    return (
      <img
        src={`/api/citations/pdf?${params.toString()}`}
        alt={`Source citation, page ${locator.page}`}
        className="max-w-full rounded border"
      />
    )
  },
  renderWhole(locator, onLocatorClick) {
    return <PdfPage locator={locator} onLocatorClick={onLocatorClick} />
  },
}
