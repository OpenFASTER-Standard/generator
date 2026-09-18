import { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiGet } from "@/lib/api"
import { getPlugin } from "@/sourcePlugins/registry"
import type { SourceLocator } from "@/lib/sourceLocator"

interface SyncedPanesViewProps {
  pdfPath: string
  xsdPaths: string[]
}

interface DerivedFactRow {
  subject: string
  predicate: string
  object: string
}

export function SyncedPanesView({ pdfPath, xsdPaths }: SyncedPanesViewProps) {
  const sources = [
    { key: `pdf:${pdfPath}`, label: pdfPath, locator: { kind: "pdf", path: pdfPath, page: 1 } as SourceLocator },
    ...xsdPaths.map((file) => ({
      key: `xsd:${file}`, label: file, locator: { kind: "xsd", file, component: "" } as SourceLocator,
    })),
  ]
  const [activeKey, setActiveKey] = useState(sources[0].key)
  // undefined = "haven't heard back yet for the current location" (either
  // just switched source, or the auto-lookup on load/page-change hasn't
  // resolved) -- kept distinct from [] ("asked, and this exact location
  // really produced nothing") so the empty state can say something honest
  // instead of a generic "click to see" prompt that both plugins now make
  // redundant by looking something up the moment they show a location.
  const [derived, setDerived] = useState<DerivedFactRow[] | undefined>(undefined)

  const active = sources.find((source) => source.key === activeKey) ?? sources[0]
  const plugin = getPlugin(active.locator.kind)

  // Switching the active source must clear any facts derived from a click
  // in the *previous* source -- otherwise a stale right-pane result looks
  // like it belongs to the newly active document even though nothing has
  // been clicked there yet. Mirrors Inspector.tsx's own reset-on-identity-
  // change pattern for its analogous `related` state.
  useEffect(() => {
    setDerived(undefined)
  }, [activeKey])

  async function handleLocatorClick(locator: SourceLocator) {
    const params =
      locator.kind === "pdf"
        ? new URLSearchParams({ kind: "pdf", path: locator.path, page: String(locator.page) })
        : new URLSearchParams({ kind: "xsd", file: locator.file, component: locator.component })
    const rows = await apiGet<DerivedFactRow[]>(`/sources/lookup?${params.toString()}`)
    setDerived(rows)
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <Select value={activeKey} onValueChange={(value) => value && setActiveKey(value)}>
          <SelectTrigger className="mb-2 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sources.map((source) => (
              <SelectItem key={source.key} value={source.key}>
                {source.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {plugin && plugin.renderWhole(active.locator, handleLocatorClick)}
      </div>
      <div>
        <h4 className="mb-2 text-sm font-semibold">Derived from this location</h4>
        {derived === undefined && <p className="text-xs text-muted-foreground">Loading…</p>}
        {derived !== undefined && derived.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Nothing was derived from this exact location. Click elsewhere in the source to check another spot.
          </p>
        )}
        <ul className="space-y-1">
          {derived?.map((row, index) => (
            <li key={index} className="text-sm">
              {row.object}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
