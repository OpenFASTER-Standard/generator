import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
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
import { fetchPages, type PagesResponse } from "../api"

export function IndexView() {
  const [pages, setPages] = useState<PagesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPages()
      .then(setPages)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load the page index: {error}</AlertDescription>
      </Alert>
    )
  }

  if (pages === null) {
    return <p>Loading...</p>
  }

  const factKeys = Object.keys(pages)
  if (factKeys.length === 0) {
    return <p>No pages yet.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Page</TableHead>
          <TableHead>Family</TableHead>
          <TableHead>Selector type</TableHead>
          <TableHead>Current reference ID</TableHead>
          <TableHead>Revisions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {factKeys.map((factKey) => {
          const page = pages[factKey]
          const reference = page.current.reference
          const family = reference?.subject_document?.family ?? ""
          const selectorType = reference?.selector?.type ?? ""
          const referenceId = reference?.reference_id ?? ""
          return (
            <TableRow key={factKey}>
              <TableCell>
                <Link to={`/pages/${encodeURIComponent(factKey)}`}>{factKey}</Link>
              </TableCell>
              <TableCell>{family}</TableCell>
              <TableCell>{selectorType}</TableCell>
              <TableCell>
                {referenceId}
                {page.current.is_correction && <Badge variant="destructive">Correction</Badge>}
              </TableCell>
              <TableCell>{page.revision_count}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
