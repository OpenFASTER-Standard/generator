import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiPost } from "@/lib/api"

interface ProposeCorrectionInlineProps {
  subject: string
  predicate: string
  language: string
  currentValue: string
  reviewer: string
  onProposed: () => void
}

export function ProposeCorrectionInline({
  subject, predicate, language, currentValue, reviewer, onProposed,
}: ProposeCorrectionInlineProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(currentValue)
  const [reason, setReason] = useState("")

  if (!editing) {
    return (
      <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => setEditing(true)}>
        Edit
      </Button>
    )
  }

  async function submit() {
    await apiPost(
      "/corrections",
      {
        targetSubject: subject, targetPredicate: predicate, targetLanguage: language,
        proposedValue: value, priorValue: currentValue, reason,
      },
      reviewer,
    )
    setEditing(false)
    onProposed()
  }

  const dirty = value !== currentValue

  return (
    <div className="mt-1 space-y-1">
      <textarea className="w-full rounded border p-1 text-xs" value={value} onChange={(event) => setValue(event.target.value)} />
      {dirty && (
        <input
          className="w-full rounded border p-1 text-xs"
          placeholder="Reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      )}
      <Button size="sm" onClick={submit}>
        Propose
      </Button>
    </div>
  )
}
