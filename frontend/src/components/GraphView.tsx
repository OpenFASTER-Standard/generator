import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Checkbox } from "@/components/ui/checkbox"
import type { AuditResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

type DocStatus = "matched" | "unmatched" | "ambiguous" | "englishOnly"

interface GraphViewProps {
  structure: StructureResponse
  documentation: DocumentationResponse
  audit: AuditResponse
  pending: { targetSubject: string }[]
  search: string
}

function statusOf(uri: string, documentation: DocumentationResponse): DocStatus | null {
  for (const status of ["matched", "unmatched", "ambiguous", "englishOnly"] as const) {
    if (documentation[status].some((entry) => entry.uri === uri)) return status
  }
  return null
}

const STATUS_COLOR: Record<DocStatus, string> = {
  matched: "bg-green-500", unmatched: "bg-gray-400", ambiguous: "bg-red-500", englishOnly: "bg-blue-400",
}

export function GraphView({ structure, documentation, pending, search }: GraphViewProps) {
  const navigate = useNavigate()
  const [namespace, setNamespace] = useState<string | null>(null)
  const [visibleStatuses, setVisibleStatuses] = useState<Set<DocStatus>>(
    new Set(["matched", "unmatched", "ambiguous", "englishOnly"]),
  )

  const pendingSubjects = useMemo(() => new Set(pending.map((p) => p.targetSubject)), [pending])

  function toggleStatus(status: DocStatus) {
    setVisibleStatuses((previous) => {
      const next = new Set(previous)
      if (next.has(status)) next.delete(status)
      else next.add(status)
      return next
    })
  }

  const statusFilters = (
    <div className="mb-4 flex gap-4">
      {(["matched", "unmatched", "ambiguous", "englishOnly"] as const).map((status) => (
        <label key={status} className="flex items-center gap-1 text-sm">
          <Checkbox
            checked={visibleStatuses.has(status)}
            onCheckedChange={() => toggleStatus(status)}
            aria-label={status}
          />
          {status}
        </label>
      ))}
    </div>
  )

  if (namespace === null) {
    const namespaces = Object.keys(structure).filter((ns) => !search || ns.toLowerCase().includes(search.toLowerCase()))
    return (
      <div>
        {statusFilters}
        <div className="grid grid-cols-3 gap-4">
          {namespaces.map((ns) => (
            <button
              key={ns}
              onClick={() => setNamespace(ns)}
              className="rounded border p-4 text-left text-sm hover:bg-accent"
            >
              {ns}
            </button>
          ))}
        </div>
      </div>
    )
  }

  const block = structure[namespace]
  const allTypes = [...block.complexTypes, ...block.simpleTypes].filter((type) => {
    const status = statusOf(type.uri, documentation)
    return status === null || visibleStatuses.has(status)
  })

  return (
    <div>
      <button onClick={() => setNamespace(null)} className="mb-4 text-sm text-primary underline">
        ← All namespaces
      </button>
      {statusFilters}
      <div className="grid grid-cols-4 gap-3">
        {allTypes.map((type) => {
          const status = statusOf(type.uri, documentation)
          return (
            <button
              key={type.uri}
              onClick={() => navigate(`/graph/${encodeURIComponent(type.uri)}`)}
              className="flex items-center gap-2 rounded border p-2 text-left text-sm hover:bg-accent"
            >
              <span className={`size-2 rounded-full ${status ? STATUS_COLOR[status] : "bg-muted"}`} />
              {type.name ?? "(anonymous)"}
              {pendingSubjects.has(type.uri) && <span className="text-xs text-amber-600">●</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
