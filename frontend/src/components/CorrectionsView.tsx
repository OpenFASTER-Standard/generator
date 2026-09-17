import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiPost, toUrlSafeBase64 } from "@/lib/api"

interface PendingCorrection {
  correctionUri: string
  targetSubject: string
  proposedValue: string
  proposer: string
}

interface CorrectionsViewProps {
  pending: PendingCorrection[]
  reviewer: string
  onDecided: () => void
}

function DecisionDialog({
  correction, outcome, reviewer, onDecided,
}: { correction: PendingCorrection; outcome: "approve" | "reject"; reviewer: string; onDecided: () => void }) {
  const [reason, setReason] = useState("")
  const [open, setOpen] = useState(false)
  const disabled = correction.proposer === reviewer

  async function confirm() {
    await apiPost(`/corrections/${toUrlSafeBase64(correction.correctionUri)}/${outcome}`, { reason }, reviewer)
    setOpen(false)
    onDecided()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant={outcome === "approve" ? "default" : "destructive"} disabled={disabled} size="sm" />}
      >
        {outcome === "approve" ? "Approve" : "Reject"}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{outcome === "approve" ? "Approve" : "Reject"} correction</DialogTitle>
        </DialogHeader>
        <textarea
          className="w-full rounded border p-2 text-sm"
          placeholder="Reason (optional)"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <DialogFooter>
          <Button onClick={confirm}>Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function CorrectionsView({ pending, reviewer, onDecided }: CorrectionsViewProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Field</TableHead>
          <TableHead>Proposed value</TableHead>
          <TableHead>Proposer</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {pending.map((correction) => (
          <TableRow key={correction.correctionUri}>
            <TableCell>{correction.targetSubject}</TableCell>
            <TableCell>{correction.proposedValue}</TableCell>
            <TableCell>{correction.proposer}</TableCell>
            <TableCell className="flex gap-2">
              <DecisionDialog correction={correction} outcome="approve" reviewer={reviewer} onDecided={onDecided} />
              <DecisionDialog correction={correction} outcome="reject" reviewer={reviewer} onDecided={onDecided} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
