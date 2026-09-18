import { useEffect, useState } from "react"
import { apiGet } from "@/lib/api"
import type { PdfLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

function PdfPage({ locator, onLocatorClick }: { locator: PdfLocator; onLocatorClick: (l: PdfLocator) => void }) {
  const [page, setPage] = useState(locator.page)
  const [totalPages, setTotalPages] = useState<number | null>(null)

  // The path this component was told to open, not the page -- switching
  // to a different PDF resets to its own starting page; navigating pages
  // within the SAME PDF must not re-trigger this.
  useEffect(() => {
    setPage(locator.page)
    apiGet<{ totalPages: number }>(`/sources/pdf/info?path=${encodeURIComponent(locator.path)}`).then((result) =>
      setTotalPages(result.totalPages),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locator.path])

  // A page is only useful to look at once you know what it produced --
  // fetch that the moment a page becomes current (on load and on
  // Prev/Next), not only after an explicit click on the image itself.
  useEffect(() => {
    onLocatorClick({ kind: "pdf", path: locator.path, page })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locator.path, page])

  function goToPage(next: number) {
    if (next < 1) return
    if (totalPages !== null && next > totalPages) return
    setPage(next)
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => goToPage(page - 1)}
          disabled={page <= 1}
          className="rounded border px-2 py-1 text-xs disabled:opacity-40"
        >
          ← Prev
        </button>
        <span className="text-xs text-muted-foreground">
          Page {page}
          {totalPages !== null ? ` of ${totalPages}` : ""}
        </span>
        <button
          type="button"
          onClick={() => goToPage(page + 1)}
          disabled={totalPages !== null && page >= totalPages}
          className="rounded border px-2 py-1 text-xs disabled:opacity-40"
        >
          Next →
        </button>
      </div>
      <img
        src={`/api/sources/pdf/page?path=${encodeURIComponent(locator.path)}&page=${page}`}
        alt={`Page ${page}`}
        className="w-full cursor-pointer rounded border"
        onClick={() => onLocatorClick({ kind: "pdf", path: locator.path, page })}
      />
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
