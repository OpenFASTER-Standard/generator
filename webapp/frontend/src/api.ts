// Typed fetch wrappers for every /api/* endpoint webapp/app.py serves.

// Mirrors reference_model.serialize.to_json_dict()'s real output shape for
// reference_model.model.{Leaf,Union} -- a Leaf cites one subject document
// via a selector; a Union has no subject_document/selector/captured_at of
// its own, only `parts` (each a Reference in turn).
export interface LeafReference {
  reference_id: string
  subject_document: { family: string; version: string; retrieval_uri: string }
  selector: { type: string; [key: string]: unknown }
  content_hash: { algorithm: string; digest: string }
  captured_at: string
}

export interface UnionReference {
  parts: Reference[]
  reference_id: string
  content_hash: { algorithm: string; digest: string }
}

export type Reference = LeafReference | UnionReference

export interface ReferenceSummary {
  family: string
  selectorType: string
  referenceId: string
}

// Single source of truth for "what does this Reference look like as three
// summary fields" -- IndexView and PageDetailView each used to derive this
// independently with the same four lines of optional-chaining, which
// (a) silently rendered three blank cells for a Union (no subject_document/
// selector to chain into) and (b) had to be found and fixed in two places
// for any future reference_model shape change.
export function describeReference(reference: Reference): ReferenceSummary {
  if ("parts" in reference) {
    return { family: "(union of multiple sources)", selectorType: "Union", referenceId: reference.reference_id }
  }
  return {
    family: reference.subject_document.family,
    selectorType: reference.selector.type,
    referenceId: reference.reference_id,
  }
}

export interface Revision {
  revision_id: string
  reference: Reference
  author: string
  comment: string
  is_correction: boolean
  created_at: string
}

export interface PageSummary {
  revision_count: number
  current: Revision
}

export type PagesResponse = Record<string, PageSummary>

export interface PageDetail {
  fact_key: string
  current: Revision
  history: Revision[]
}

export interface Candidate {
  tag: string
  name: string
  xpath: string
}

export interface ExcludedCandidate {
  tag: string
  name: string
  xpath: string
  match_count: number
}

export interface FamilyCandidates {
  candidates: Candidate[]
  excluded: ExcludedCandidate[]
}

export type CandidatesResponse = Record<string, FamilyCandidates>

export interface CitationRequest {
  family: string
  xpath: string
  fact_key: string
  author: string
  comment: string
  is_correction: boolean
}

export interface CitationResponse {
  fact_key: string
  revision: Revision
}

export interface FlaggedLeaf {
  leaf: {
    reference_id: string
    subject_document: { family: string; version: string; retrieval_uri: string }
  }
  outcome: { status: string }
  drift_kind: "CONTENT" | "STRUCTURAL"
  fingerprint: string
}

export interface FamilyResolutionFailure {
  family: string
  status: string
}

export interface ReviewResponse {
  flagged: Record<string, FlaggedLeaf[]>
  unresolved_families: FamilyResolutionFailure[]
  excluded_keys: string[]
  deserialization_failures: string[]
}

export interface SubmitReviewRequest {
  fact_key: string
  leaf_reference_id: string
  reviewer: string
  verdict: "approved" | "rejected"
  reasoning: string
}

export interface SubmitReviewResponse {
  fact_key: string
  revision: Revision
}

async function describeErrorBody(response: Response): Promise<string> {
  const text = await response.text()
  try {
    const body = JSON.parse(text)
    if (body && body.detail) {
      return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    }
  } catch {
    // Not JSON (e.g. a plain-text 500) -- fall through to the generic message.
  }
  return `Server returned ${response.status}`
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    throw new Error(await describeErrorBody(response))
  }
  return response.json()
}

export function fetchPages(): Promise<PagesResponse> {
  return apiFetch<PagesResponse>("/api/pages")
}

export function fetchPage(factKey: string): Promise<PageDetail> {
  return apiFetch<PageDetail>(`/api/pages/${encodeURIComponent(factKey)}`)
}

export function fetchCandidates(): Promise<CandidatesResponse> {
  return apiFetch<CandidatesResponse>("/api/candidates")
}

export function submitCitation(body: CitationRequest): Promise<CitationResponse> {
  return apiFetch<CitationResponse>("/api/citations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export function fetchReview(): Promise<ReviewResponse> {
  return apiFetch<ReviewResponse>("/api/review")
}

export function submitReview(body: SubmitReviewRequest): Promise<SubmitReviewResponse> {
  return apiFetch<SubmitReviewResponse>("/api/reviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}
