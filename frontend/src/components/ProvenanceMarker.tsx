import { useState } from "react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { apiGet } from "@/lib/api"
import type { ProvenanceRecord } from "@/lib/api"

interface ProvenanceMarkerProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

function parseCitationUrl(sourceUri: string): URL | null {
  try {
    return new URL(sourceUri.replace(/^citation:/, "https://citation.invalid/"))
  } catch {
    return null
  }
}

export function ProvenanceMarker({ subject, predicate, value, lang }: ProvenanceMarkerProps) {
  const [open, setOpen] = useState(false)
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)

  async function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (nextOpen && record === undefined) {
      const params = new URLSearchParams({ subject, predicate, value })
      if (lang) params.set("lang", lang)
      const result = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
      setRecord(result)
    }
  }

  function renderCitation() {
    if (record === undefined) return <p className="text-xs text-muted-foreground">Loading...</p>
    if (record === null) return <p className="text-xs text-muted-foreground">No source recorded.</p>

    const url = parseCitationUrl(record.sourceUri)
    if (url && record.sourceUri.startsWith("citation:pdf")) {
      const query = new URLSearchParams(url.search)
      return (
        <img
          src={`/api/citations/pdf?${query.toString()}`}
          alt={`Source citation, page ${query.get("page")}`}
          className="max-w-full rounded border"
        />
      )
    }
    if (url && record.sourceUri.startsWith("citation:xsd")) {
      return (
        <p className="text-xs text-muted-foreground">
          From {url.searchParams.get("file")} ({url.searchParams.get("component") ?? "this run"}).
        </p>
      )
    }
    return <p className="text-xs text-muted-foreground">No source recorded.</p>
  }

  return (
    <Collapsible open={open} onOpenChange={handleOpenChange}>
      <CollapsibleTrigger
        render={
          <button
            type="button"
            aria-label="Show provenance"
            className="inline-block size-2 rounded-full bg-muted-foreground/40 align-middle ml-1"
          />
        }
      />
      <CollapsibleContent className="mt-1 rounded border bg-muted/30 p-2">
        {renderCitation()}
      </CollapsibleContent>
    </Collapsible>
  )
}
