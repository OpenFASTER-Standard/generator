import cytoscape from "cytoscape"
import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Checkbox } from "@/components/ui/checkbox"
import { useFocus } from "@/lib/focus"
import { apiGet, XSDO_DOCUMENTATION } from "@/lib/api"
import type { AuditResponse, DocumentationResponse, ProvenanceRecord, StructureResponse } from "@/lib/api"

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

function SubjectLineage({ subjectUri, languages }: { subjectUri: string; languages: Record<string, string> }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [records, setRecords] = useState<Record<string, ProvenanceRecord | null>>({})

  useEffect(() => {
    let cancelled = false
    Promise.all(
      Object.entries(languages).map(async ([lang, text]) => {
        const params = new URLSearchParams({ subject: subjectUri, predicate: XSDO_DOCUMENTATION, value: text, lang })
        const record = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
        return [lang, record] as const
      }),
    ).then((entries) => {
      if (!cancelled) setRecords(Object.fromEntries(entries))
    })
    return () => {
      cancelled = true
    }
  }, [subjectUri, languages])

  const setContainer = (node: HTMLDivElement | null) => {
    containerRef.current = node
    if (!node) return
    const elements: cytoscape.ElementDefinition[] = [{ data: { id: subjectUri, label: subjectUri } }]
    for (const [lang, record] of Object.entries(records)) {
      if (!record) continue
      const sourceId = record.sourceUri
      elements.push({ data: { id: sourceId, label: sourceId } })
      elements.push({ data: { id: `${lang}-edge`, source: sourceId, target: subjectUri, label: "wasDerivedFrom" } })
    }
    cytoscape({
      container: node,
      elements,
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 8, "background-color": "#0b5fff" } },
        { selector: "edge", style: { label: "data(label)", "font-size": 6, "curve-style": "bezier", "target-arrow-shape": "triangle" } },
      ],
      layout: { name: "breadthfirst", directed: true },
    })
  }

  return <div ref={setContainer} data-testid="lineage-graph-container" className="h-96 w-full rounded border" />
}

export function GraphView({ structure, documentation, pending, search }: GraphViewProps) {
  const navigate = useNavigate()
  const { subject } = useFocus()

  // NOTE: all hooks below must run unconditionally on every render, so the
  // subject-focus early return sits *after* them, not before (the brief's
  // literal placement put the early return before these useState/useMemo
  // calls, which would violate the Rules of Hooks -- React would throw
  // "Rendered fewer hooks than expected" the moment this component
  // re-renders switching between a focused subject and the type grid,
  // since a different number of hooks would run each time).
  const [namespace, setNamespace] = useState<string | null>(null)
  const [visibleStatuses, setVisibleStatuses] = useState<Set<DocStatus>>(
    new Set(["matched", "unmatched", "ambiguous", "englishOnly"]),
  )

  const pendingSubjects = useMemo(() => new Set(pending.map((p) => p.targetSubject)), [pending])

  if (subject) {
    const entry =
      documentation.matched.find((e) => e.uri === subject) ??
      documentation.unmatched.find((e) => e.uri === subject) ??
      documentation.ambiguous.find((e) => e.uri === subject) ??
      documentation.englishOnly.find((e) => e.uri === subject)
    if (entry) {
      return <SubjectLineage subjectUri={subject} languages={entry.languages} />
    }
  }

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
