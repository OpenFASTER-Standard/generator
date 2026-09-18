import { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiGet } from "@/lib/api"
import { getPlugin } from "@/sourcePlugins/registry"
import { repoRelativePath } from "@/lib/sourceFileLabel"
import type { SourceFileInfo } from "@/lib/api"
import type { SourceLocator } from "@/lib/sourceLocator"

interface DerivedFactRow {
  subject: string
  predicate: string
  object: string
}

function locatorFor(file: SourceFileInfo): SourceLocator {
  return file.kind === "pdf"
    ? { kind: "pdf", path: file.path, page: 1 }
    : { kind: "xsd", file: file.path, component: "" }
}

export function SyncedPanesView() {
  const [files, setFiles] = useState<SourceFileInfo[] | undefined>(undefined)
  const [activePath, setActivePath] = useState<string | undefined>(undefined)
  // undefined = "haven't heard back yet for the current location" (either
  // just switched source, or the auto-lookup on load/page-change hasn't
  // resolved) -- kept distinct from [] ("asked, and this exact location
  // really produced nothing") so the empty state can say something honest
  // instead of a generic "click to see" prompt that both plugins now make
  // redundant by looking something up the moment they show a location.
  const [derived, setDerived] = useState<DerivedFactRow[] | undefined>(undefined)

  useEffect(() => {
    apiGet<SourceFileInfo[]>("/sources/files").then((result) => {
      setFiles(result)
      setActivePath((current) => current ?? result[0]?.path)
    })
  }, [])

  const active = files?.find((file) => file.path === activePath)

  // Switching the active source must clear any facts derived from a click
  // in the *previous* source -- otherwise a stale right-pane result looks
  // like it belongs to the newly active document even though nothing has
  // been clicked there yet. Mirrors Inspector.tsx's own reset-on-identity-
  // change pattern for its analogous `related` state.
  useEffect(() => {
    setDerived(undefined)
  }, [activePath])

  async function handleLocatorClick(locator: SourceLocator) {
    const params =
      locator.kind === "pdf"
        ? new URLSearchParams({ kind: "pdf", path: locator.path, page: String(locator.page) })
        : new URLSearchParams({ kind: "xsd", file: locator.file, component: locator.component })
    const rows = await apiGet<DerivedFactRow[]>(`/sources/lookup?${params.toString()}`)
    setDerived(rows)
  }

  if (files === undefined || !active) {
    return <p className="text-sm text-muted-foreground">Loading sources…</p>
  }

  const plugin = getPlugin(active.kind)

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <Select value={activePath} onValueChange={(value) => value && setActivePath(value)}>
          <SelectTrigger className="mb-2 w-full">
            <SelectValue>
              {(value: string | null) => {
                const file = files.find((f) => f.path === value)
                return file ? repoRelativePath(file) : null
              }}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {files.map((file) => (
              <SelectItem key={file.path} value={file.path}>
                {repoRelativePath(file)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {plugin && plugin.renderWhole(locatorFor(active), handleLocatorClick)}
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
