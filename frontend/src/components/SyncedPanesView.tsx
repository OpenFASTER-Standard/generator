import { useState } from "react"
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
  const [derived, setDerived] = useState<DerivedFactRow[]>([])

  const active = sources.find((source) => source.key === activeKey) ?? sources[0]
  const plugin = getPlugin(active.locator.kind)

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
        {derived.length === 0 && <p className="text-xs text-muted-foreground">Click the source to see what it produced.</p>}
        <ul className="space-y-1">
          {derived.map((row, index) => (
            <li key={index} className="text-sm">
              {row.object}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
