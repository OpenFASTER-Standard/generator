import { useEffect, useState } from "react"
import { apiGet } from "@/lib/api"
import { useFocus } from "@/lib/focus"
import { getPlugin } from "@/sourcePlugins/registry"
import { parseSourceUri } from "@/lib/sourceLocator"
import type { ProvenanceRecord } from "@/lib/api"

interface ReverseLookupRow {
  subject: string
  predicate: string
  object: string
}

interface InspectorProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

export function Inspector({ subject, predicate, value, lang }: InspectorProps) {
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)
  const [related, setRelated] = useState<ReverseLookupRow[]>([])
  const { setFocus } = useFocus()

  useEffect(() => {
    setRecord(undefined)
    setRelated([])
    const params = new URLSearchParams({ subject, predicate, value })
    if (lang) params.set("lang", lang)
    apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`).then(setRecord)
  }, [subject, predicate, value, lang])

  useEffect(() => {
    if (!record) return
    const locator = parseSourceUri(record.sourceUri)
    if (!locator) return
    const lookupParams =
      locator.kind === "pdf"
        ? new URLSearchParams({ kind: "pdf", path: locator.path, page: String(locator.page) })
        : new URLSearchParams({ kind: "xsd", file: locator.file, component: locator.component })
    apiGet<ReverseLookupRow[]>(`/sources/lookup?${lookupParams.toString()}`).then((rows) =>
      setRelated(rows.filter((row) => !(row.subject === subject && row.predicate === predicate))),
    )
  }, [record, subject, predicate])

  if (record === undefined) return <p className="text-sm text-muted-foreground">Loading...</p>
  if (record === null) return <p className="text-sm text-muted-foreground">No source recorded.</p>

  const locator = parseSourceUri(record.sourceUri)
  const plugin = locator ? getPlugin(locator.kind) : undefined

  return (
    <div className="space-y-3 rounded border p-3">
      {plugin && locator ? plugin.renderLocator(locator) : <p className="text-xs">No source recorded.</p>}
      {related.length > 0 && (
        <div>
          <p className="text-xs font-medium">{related.length} other facts from this same source:</p>
          <ul className="mt-1 space-y-1">
            {related.map((row, index) => (
              <li key={index}>
                <button
                  type="button"
                  className="text-xs text-primary underline"
                  onClick={() => setFocus({ mode: "living-text", subject: row.subject, predicate: row.predicate })}
                >
                  {row.object}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
