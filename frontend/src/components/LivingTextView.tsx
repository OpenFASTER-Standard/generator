import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InlineCorrection } from "@/components/InlineCorrection"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { Inspector } from "@/components/Inspector"
import { ProposeCorrectionInline } from "@/components/ProposeCorrectionInline"
import { SourcePreviewPopover } from "@/components/SourcePreviewPopover"
import { useFocus } from "@/lib/focus"
import { DOC_STATUS_LABELS } from "@/lib/docStatusLabels"
import { XSDO_DOCUMENTATION } from "@/lib/api"
import type { DocEntry, DocumentationResponse } from "@/lib/api"

const GROUP_KEYS: (keyof DocumentationResponse)[] = ["matched", "unmatched", "ambiguous", "englishOnly"]

function findEntry(documentation: DocumentationResponse, subject: string): DocEntry | undefined {
  for (const key of GROUP_KEYS) {
    const entry = documentation[key].find((candidate) => candidate.uri === subject)
    if (entry) return entry
  }
  return undefined
}

interface LivingTextViewProps {
  documentation: DocumentationResponse
  pending: PendingCorrection[]
  reviewer: string
  search: string
  onDecided: () => void
}

const GROUPS: { key: keyof DocumentationResponse; variant: "default" | "secondary" | "destructive" | "outline" }[] = [
  { key: "matched", variant: "default" },
  { key: "unmatched", variant: "secondary" },
  { key: "ambiguous", variant: "destructive" },
  { key: "englishOnly", variant: "outline" },
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
  const { subject, predicate, lang } = useFocus()

  // Click-to-pin (SourcePreviewPopover's onClick) puts {subject, predicate,
  // lang} into the URL-addressable focus, but the Inspector itself needs
  // the actual documented `value` text too (the /provenance lookup is
  // keyed on subject+predicate+value+lang, same as the hover preview) --
  // look it up from the documentation payload already in hand rather than
  // stashing value in the URL/focus model.
  const focusedEntry = subject ? findEntry(documentation, subject) : undefined
  const focusedValue = focusedEntry && lang ? focusedEntry.languages[lang] : undefined

  return (
    <div>
      {subject && predicate && lang && focusedValue !== undefined && (
        <div data-testid="inspector-panel" className="mb-6">
          <Inspector subject={subject} predicate={predicate} value={focusedValue} lang={lang} />
        </div>
      )}
      {GROUPS.map(({ key, variant }) => {
        const entries = documentation[key].filter((entry) => matchesSearch(entry.name, search))
        if (entries.length === 0) return null
        const { label, description } = DOC_STATUS_LABELS[key]
        return (
          <section key={key} className="mb-8">
            <h3 className="mb-1 flex items-center gap-2 text-lg font-semibold">
              {label} <Badge variant={variant}>{entries.length}</Badge>
            </h3>
            <p className="mb-2 text-xs text-muted-foreground">{description}</p>
            {entries.map((entry) => (
              <DocEntryCard key={entry.uri} entry={entry} pending={pending} reviewer={reviewer} onDecided={onDecided} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
