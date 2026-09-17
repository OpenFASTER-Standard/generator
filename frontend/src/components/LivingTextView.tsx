import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InlineCorrection } from "@/components/InlineCorrection"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { ProposeCorrectionInline } from "@/components/ProposeCorrectionInline"
import { SourcePreviewPopover } from "@/components/SourcePreviewPopover"
import { XSDO_DOCUMENTATION } from "@/lib/api"
import type { DocEntry, DocumentationResponse } from "@/lib/api"

interface LivingTextViewProps {
  documentation: DocumentationResponse
  pending: PendingCorrection[]
  reviewer: string
  search: string
  onDecided: () => void
}

const GROUPS: { key: keyof DocumentationResponse; label: string; variant: "default" | "secondary" | "destructive" | "outline" }[] = [
  { key: "matched", label: "Matched", variant: "default" },
  { key: "unmatched", label: "Unmatched", variant: "secondary" },
  { key: "ambiguous", label: "Ambiguous", variant: "destructive" },
  { key: "englishOnly", label: "English-only", variant: "outline" },
]

function matchesSearch(name: string, search: string): boolean {
  return !search || name.toLowerCase().includes(search.toLowerCase())
}

function DocEntryCard({
  entry, pending, reviewer, onDecided,
}: { entry: DocEntry; pending: PendingCorrection[]; reviewer: string; onDecided: () => void }) {
  return (
    <Card id={`doc:${entry.uri}`} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{entry.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {Object.entries(entry.languages).map(([lang, text]) => (
          <div key={lang}>
            {lang.toUpperCase()}:{" "}
            <SourcePreviewPopover subject={entry.uri} predicate={XSDO_DOCUMENTATION} value={text} lang={lang} />{" "}
            <ProposeCorrectionInline
              subject={entry.uri} predicate={XSDO_DOCUMENTATION} language={lang} currentValue={text}
              reviewer={reviewer} onProposed={onDecided}
            />
          </div>
        ))}
        {(() => {
          const correctionForThisEntry = pending.find((c) => c.targetSubject === entry.uri)
          return (
            correctionForThisEntry && (
              <InlineCorrection correction={correctionForThisEntry} reviewer={reviewer} onDecided={onDecided} />
            )
          )
        })()}
        {entry.issues?.map((issue, index) => (
          <div key={index} className="text-destructive text-xs">
            {issue.kind}: {issue.detail}
          </div>
        ))}
        {entry.candidates && (
          <ul className="list-disc pl-4 text-xs text-muted-foreground">
            {entry.candidates.map((candidate, index) => (
              <li key={index}>{candidate}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function LivingTextView({ documentation, pending, reviewer, search, onDecided }: LivingTextViewProps) {
  return (
    <div>
      {GROUPS.map(({ key, label, variant }) => {
        const entries = documentation[key].filter((entry) => matchesSearch(entry.name, search))
        if (entries.length === 0) return null
        return (
          <section key={key} className="mb-8">
            <h3 className="mb-2 flex items-center gap-2 text-lg font-semibold">
              {label} <Badge variant={variant}>{entries.length}</Badge>
            </h3>
            {entries.map((entry) => (
              <DocEntryCard key={entry.uri} entry={entry} pending={pending} reviewer={reviewer} onDecided={onDecided} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
