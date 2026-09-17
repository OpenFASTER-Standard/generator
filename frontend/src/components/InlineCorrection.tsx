import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiPost, toUrlSafeBase64 } from "@/lib/api"

export interface PendingCorrection {
  correctionUri: string
  targetSubject: string
  proposedValue: string
  proposer: string
}

interface InlineCorrectionProps {
  correction: PendingCorrection
  reviewer: string
  onDecided: () => void
}

export function InlineCorrection({ correction, reviewer, onDecided }: InlineCorrectionProps) {
  const [reason, setReason] = useState("")
  const disabled = correction.proposer === reviewer

  async function decide(outcome: "approve" | "reject") {
    await apiPost(`/corrections/${toUrlSafeBase64(correction.correctionUri)}/${outcome}`, { reason }, reviewer)
    onDecided()
  }

  return (
    <div className="mt-1 rounded border border-amber-400 bg-amber-50 p-2 text-sm dark:bg-amber-950">
      <p>
        Proposed by {correction.proposer}: <ins className="bg-green-100 dark:bg-green-900">{correction.proposedValue}</ins>
      </p>
      <input
        className="mt-1 w-full rounded border p-1 text-xs"
        placeholder="Reason (optional)"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="mt-1 flex gap-2">
        <Button size="sm" disabled={disabled} onClick={() => decide("approve")}>
          Approve
        </Button>
        <Button size="sm" variant="destructive" disabled={disabled} onClick={() => decide("reject")}>
          Reject
        </Button>
      </div>
    </div>
  )
}
