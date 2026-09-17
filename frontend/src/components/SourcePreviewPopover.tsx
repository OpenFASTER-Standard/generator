import { useState } from "react"
import { useFocus } from "@/lib/focus"
import { getPlugin } from "@/sourcePlugins/registry"
import { parseSourceUri } from "@/lib/sourceLocator"
import { apiGet } from "@/lib/api"
import type { ProvenanceRecord } from "@/lib/api"

interface SourcePreviewPopoverProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

export function SourcePreviewPopover({ subject, predicate, value, lang }: SourcePreviewPopoverProps) {
  const [open, setOpen] = useState(false)
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)
  const { setFocus } = useFocus()

  async function handleHover() {
    setOpen(true)
    if (record === undefined) {
      const params = new URLSearchParams({ subject, predicate, value })
      if (lang) params.set("lang", lang)
      const result = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
      setRecord(result)
    }
  }

  function renderPreview() {
    if (record === undefined) return <p className="text-xs text-muted-foreground">Loading...</p>
    if (record === null) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    const locator = parseSourceUri(record.sourceUri)
    if (!locator) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    const plugin = getPlugin(locator.kind)
    if (!plugin) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    return plugin.renderLocator(locator)
  }

  return (
    <span className="relative inline-block">
      <span
        className="underline decoration-dotted decoration-muted-foreground/60 cursor-help"
        onMouseEnter={handleHover}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setFocus({ mode: "living-text", subject, predicate, lang })}
      >
        {value}
      </span>
      {open && (
        <span className="absolute z-20 mt-1 block w-max max-w-sm rounded border bg-popover p-2 shadow-md">
          {renderPreview()}
        </span>
      )}
    </span>
  )
}
