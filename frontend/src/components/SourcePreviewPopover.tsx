import { useState } from "react"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
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
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)
  const { setFocus } = useFocus()

  // The hand-rolled version of this (a plain absolutely-positioned <span>)
  // rendered INSIDE whichever <Card> the documented entry lives in --
  // Card's own base styling includes `overflow-hidden` (needed elsewhere,
  // to round image corners), which silently clipped any preview taller
  // than the card's remaining space, confirmed live. HoverCard
  // (@base-ui/react's PreviewCard) portals its content to the document
  // body and repositions to avoid viewport/collision issues automatically,
  // which also solves this for free.
  async function handleOpenChange(open: boolean) {
    if (!open || record !== undefined) return
    const params = new URLSearchParams({ subject, predicate, value })
    if (lang) params.set("lang", lang)
    const result = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
    setRecord(result)
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
    <HoverCard onOpenChange={handleOpenChange}>
      <HoverCardTrigger
        delay={0}
        render={
          <span
            className="underline decoration-dotted decoration-muted-foreground/60 cursor-help"
            onClick={() => setFocus({ mode: "living-text", subject, predicate, lang })}
          >
            {value}
          </span>
        }
      />
      <HoverCardContent className="w-max max-w-lg max-h-[70vh] overflow-auto">
        {renderPreview()}
      </HoverCardContent>
    </HoverCard>
  )
}
