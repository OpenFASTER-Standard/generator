import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
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
  Checkbox,
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Alert,
  AlertDescription,
} from "@openfaster-standard/ui"
import { fetchCandidates, submitCitation, type Candidate, type CandidatesResponse } from "../api"

function FamilyCandidates({
  family,
  candidates,
  onCite,
}: {
  family: string
  candidates: Candidate[]
  onCite: (family: string, candidate: Candidate) => void
}) {
  const [filter, setFilter] = useState("")

  const filtered = useMemo(() => {
    const needle = filter.toLowerCase()
    if (!needle) return candidates
    return candidates.filter(
      (c) => c.tag.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle) || c.xpath.toLowerCase().includes(needle)
    )
  }, [filter, candidates])

  return (
    <div>
      <Input placeholder="Filter candidates..." value={filter} onChange={(e) => setFilter(e.target.value)} />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tag</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>XPath</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((candidate) => (
            <TableRow key={candidate.xpath}>
              <TableCell>{candidate.tag}</TableCell>
              <TableCell>{candidate.name}</TableCell>
              <TableCell>{candidate.xpath}</TableCell>
              <TableCell>
                <Button type="button" onClick={() => onCite(family, candidate)}>
                  Cite this
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function AddCitationView() {
  const navigate = useNavigate()
  const [candidatesByFamily, setCandidatesByFamily] = useState<CandidatesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [citeTarget, setCiteTarget] = useState<{ family: string; candidate: Candidate } | null>(null)
  const [factKey, setFactKey] = useState("")
  const [author, setAuthor] = useState("")
  const [comment, setComment] = useState("")
  const [isCorrection, setIsCorrection] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    fetchCandidates()
      .then(setCandidatesByFamily)
      .catch((e) => setError(e.message))
  }, [])

  function openCiteDialog(family: string, candidate: Candidate) {
    setCiteTarget({ family, candidate })
    setFactKey("")
    setAuthor("")
    setComment("")
    setIsCorrection(false)
    setSubmitError(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!citeTarget) return
    submitCitation({
      family: citeTarget.family,
      xpath: citeTarget.candidate.xpath,
      fact_key: factKey,
      author,
      comment,
      is_correction: isCorrection,
    })
      .then(({ fact_key }) => navigate(`/pages/${encodeURIComponent(fact_key)}`))
      .catch((err) => setSubmitError(err.message))
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load candidates: {error}</AlertDescription>
      </Alert>
    )
  }

  if (candidatesByFamily === null) {
    return <p>Loading...</p>
  }

  const families = Object.keys(candidatesByFamily).sort()
  if (families.length === 0) {
    return <p>No citable families in the current corpus snapshot.</p>
  }

  return (
    <div>
      <h2>Add citation</h2>
      <Accordion>
        {families.map((family) => (
          <AccordionItem key={family} value={family}>
            <AccordionTrigger>
              {family} ({candidatesByFamily[family].length} candidates)
            </AccordionTrigger>
            <AccordionContent>
              <FamilyCandidates family={family} candidates={candidatesByFamily[family]} onCite={openCiteDialog} />
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>

      <Dialog open={citeTarget !== null} onOpenChange={(open) => !open && setCiteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {citeTarget && `${citeTarget.family}: ${citeTarget.candidate.tag} ${citeTarget.candidate.name} (${citeTarget.candidate.xpath})`}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <Label htmlFor="fact-key-input">Fact key</Label>
            <Input id="fact-key-input" required value={factKey} onChange={(e) => setFactKey(e.target.value)} />

            <Label htmlFor="author-input">Author</Label>
            <Input id="author-input" required value={author} onChange={(e) => setAuthor(e.target.value)} />

            <Label htmlFor="comment-input">Comment</Label>
            <Input id="comment-input" value={comment} onChange={(e) => setComment(e.target.value)} />

            <Label htmlFor="is-correction-input">Is correction</Label>
            <Checkbox id="is-correction-input" checked={isCorrection} onCheckedChange={(checked) => setIsCorrection(checked === true)} />

            <Button type="submit">Submit citation</Button>
            {submitError && (
              <Alert variant="destructive">
                <AlertDescription>Failed to submit citation: {submitError}</AlertDescription>
              </Alert>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
