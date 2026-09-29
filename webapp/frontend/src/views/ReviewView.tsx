import { useEffect, useState } from "react"
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Input,
  Label,
  Textarea,
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Alert,
  AlertDescription,
} from "@openfaster-standard/ui"
import { LoadingSkeleton } from "../components/LoadingSkeleton"
import { fetchReview, submitReview, type FlaggedLeaf, type ReviewResponse } from "../api"

interface ReviewTarget {
  factKey: string
  leaf: FlaggedLeaf
}

export function ReviewView() {
  const [review, setReview] = useState<ReviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [target, setTarget] = useState<ReviewTarget | null>(null)
  const [reviewer, setReviewer] = useState("")
  const [reasoning, setReasoning] = useState("")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchReview()
      .then(setReview)
      .catch((e) => setError(e.message))
  }, [])

  function openReviewDialog(factKey: string, leaf: FlaggedLeaf) {
    setTarget({ factKey, leaf })
    setReviewer("")
    setReasoning("")
    setSubmitError(null)
  }

  function handleVerdict(verdict: "approved" | "rejected") {
    if (!target || submitting) return
    if (!reviewer.trim() || !reasoning.trim()) {
      setSubmitError("Reviewer and reasoning are both required")
      return
    }
    setSubmitting(true)
    submitReview({
      fact_key: target.factKey,
      leaf_reference_id: target.leaf.leaf.reference_id,
      reviewer,
      verdict,
      reasoning,
    })
      .then(() => {
        setReview((prev) => {
          if (!prev) return prev
          const remaining = (prev.flagged[target.factKey] ?? []).filter(
            (l) => l.leaf.reference_id !== target.leaf.leaf.reference_id
          )
          const nextFlagged = { ...prev.flagged }
          if (remaining.length === 0) {
            delete nextFlagged[target.factKey]
          } else {
            nextFlagged[target.factKey] = remaining
          }
          return { ...prev, flagged: nextFlagged }
        })
        setTarget(null)
      })
      .catch((e) => setSubmitError(e.message))
      .finally(() => setSubmitting(false))
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load review data: {error}</AlertDescription>
      </Alert>
    )
  }

  if (review === null) {
    return <LoadingSkeleton />
  }

  const factKeys = Object.keys(review.flagged).sort()

  return (
    <div>
      <h2>Drift review</h2>

      {review.unresolved_families.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            {review.unresolved_families.length} famil{review.unresolved_families.length === 1 ? "y" : "ies"} could not
            be resolved against the current corpus snapshot and were skipped:{" "}
            {review.unresolved_families.map((f) => f.family).join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {review.deserialization_failures.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            {review.deserialization_failures.length} catalog entr
            {review.deserialization_failures.length === 1 ? "y is" : "ies are"} corrupted and cannot be checked:{" "}
            {review.deserialization_failures.join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {review.excluded_keys.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            {review.excluded_keys.length} page{review.excluded_keys.length === 1 ? "" : "s"} could not be checked
            this run because a family it cites didn't resolve: {review.excluded_keys.join(", ")}
          </AlertDescription>
        </Alert>
      )}

      {factKeys.length === 0 ? (
        <p>Nothing flagged for review.</p>
      ) : (
        <Accordion>
          {factKeys.map((factKey) => (
            <AccordionItem key={factKey} value={factKey}>
              <AccordionTrigger>
                {factKey} ({review.flagged[factKey].length} flagged)
              </AccordionTrigger>
              <AccordionContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Drift kind</TableHead>
                      <TableHead>Fingerprint</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {review.flagged[factKey].map((leaf) => (
                      <TableRow key={leaf.leaf.reference_id}>
                        <TableCell>{leaf.drift_kind}</TableCell>
                        <TableCell>{leaf.fingerprint}</TableCell>
                        <TableCell>
                          <Button type="button" onClick={() => openReviewDialog(factKey, leaf)}>
                            Review
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}

      <Dialog open={target !== null} onOpenChange={(open) => !open && setTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{target && `${target.factKey}: ${target.leaf.drift_kind} drift`}</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => e.preventDefault()}>
            <Label htmlFor="reviewer-input">Reviewer</Label>
            <Input id="reviewer-input" required value={reviewer} onChange={(e) => setReviewer(e.target.value)} />

            <Label htmlFor="reasoning-input">Reasoning</Label>
            <Textarea id="reasoning-input" required value={reasoning} onChange={(e) => setReasoning(e.target.value)} />

            <Button
              type="button"
              disabled={submitting || !reviewer.trim() || !reasoning.trim()}
              onClick={() => handleVerdict("approved")}
            >
              Approve
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={submitting || !reviewer.trim() || !reasoning.trim()}
              onClick={() => handleVerdict("rejected")}
            >
              Reject
            </Button>
            {submitError && (
              <Alert variant="destructive">
                <AlertDescription>Failed to submit review: {submitError}</AlertDescription>
              </Alert>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
