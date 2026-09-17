import type { AuditResponse } from "@/lib/api"

interface AuditViewProps {
  audit: AuditResponse
}

export function AuditView({ audit }: AuditViewProps) {
  return (
    <div>
      <div className="mb-6 flex gap-8">
        <div>
          <p className="max-w-md text-xs text-muted-foreground">
            PDF-matching pass over every named construct in the schema (elements, attributes, types) -- documented or not.
          </p>
          <p>
            attachment: attached={audit.attachment.attached}, ambiguous={audit.attachment.ambiguous}, unmatched={audit.attachment.unmatched}
          </p>
        </div>
        <div>
          <p className="max-w-md text-xs text-muted-foreground">
            Same matching, restricted to constructs that actually carry German documentation -- the number that matters for translation completeness.
          </p>
          <p>
            coverage: total={audit.coverage.total}, attached={audit.coverage.attached}, ambiguous={audit.coverage.ambiguous}, unmatched={audit.coverage.unmatched}
          </p>
        </div>
      </div>
      <ul className="space-y-1">
        {audit.issues.map((issue, index) => (
          <li key={index} className="text-sm">
            [{issue.kind}]{" "}
            {issue.subjectUri ? (
              <a href={`#doc:${issue.subjectUri}`} className="text-primary underline">
                {issue.subjectName}
              </a>
            ) : (
              issue.subjectName
            )}{" "}
            -- {issue.detail}
          </li>
        ))}
      </ul>
    </div>
  )
}
