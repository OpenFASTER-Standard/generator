import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Badge,
  Alert,
  AlertDescription,
} from "@openfaster-standard/ui"
import { fetchPage, type PageDetail } from "../api"

export function PageDetailView() {
  const { factKey } = useParams<{ factKey: string }>()
  const [page, setPage] = useState<PageDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!factKey) return
    fetchPage(factKey)
      .then(setPage)
      .catch((e) => setError(e.message))
  }, [factKey])

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load this page: {error}</AlertDescription>
      </Alert>
    )
  }

  if (page === null) {
    return <p>Loading...</p>
  }

  const reference = page.current.reference
  const family = reference?.subject_document?.family ?? ""
  const selectorType = reference?.selector?.type ?? ""
  const referenceId = reference?.reference_id ?? ""

  return (
    <div>
      <h2>{page.fact_key}</h2>
      <p>
        {family} / {selectorType} / {referenceId}
      </p>
      <h3>History</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Author</TableHead>
            <TableHead>Comment</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...page.history].reverse().map((revision) => (
            <TableRow key={revision.revision_id}>
              <TableCell>{revision.created_at}</TableCell>
              <TableCell>{revision.author}</TableCell>
              <TableCell>
                {revision.comment}
                {revision.is_correction && <Badge variant="destructive">Correction</Badge>}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
