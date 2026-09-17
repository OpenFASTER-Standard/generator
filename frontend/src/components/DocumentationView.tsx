import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProvenanceMarker } from "@/components/ProvenanceMarker"
import { XSDO_DOCUMENTATION } from "@/lib/api"
import type { DocEntry, DocumentationResponse } from "@/lib/api"

interface DocumentationViewProps {
  documentation: DocumentationResponse
  search: string
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

function DocEntryCard({ entry }: { entry: DocEntry }) {
  return (
    <Card id={`doc:${entry.uri}`} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{entry.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {Object.entries(entry.languages).map(([lang, text]) => (
          <div key={lang}>
            {lang.toUpperCase()}: {text}
            <ProvenanceMarker subject={entry.uri} predicate={XSDO_DOCUMENTATION} value={text} lang={lang} />
          </div>
        ))}
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

export function DocumentationView({ documentation, search }: DocumentationViewProps) {
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
              <DocEntryCard key={entry.uri} entry={entry} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
