const API_BASE = "/api"

// The real predicate URI documentation facts are stored under -- matching
// XSDO.documentation (extraction/*.py, reporting/data.py). A bare string
// like "documentation" is not an absolute IRI: rdflib's own URIRef/.n3()
// happily accept it, but Oxigraph's SPARQL parser rejects it at query
// time with a raw, uncaught SyntaxError -- confirmed live, this crashed
// GET /api/provenance with a 500 the moment a real Documentation-tab
// citation marker was clicked in a real browser.
export const XSDO_DOCUMENTATION = "https://purl.openfaster.org/xsdo/documentation"

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, undefined)
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown, reviewer: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Reviewer": reviewer },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(`POST ${path} failed: ${response.status} ${JSON.stringify(detail)}`)
  }
  return response.json() as Promise<T>
}

// The backend decodes correction URIs with Python's base64.urlsafe_b64decode
// (an alphabet of -_ instead of +/, with = padding kept) -- plain btoa()
// produces standard base64 and would silently break the moment an encoded
// URI happens to contain a '+' or '/'. Always use this, not btoa(), for
// anything embedded in a URL path segment.
export function toUrlSafeBase64(text: string): string {
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_")
}

// -- Types matching webapp's real JSON shapes (Plan C) --

export interface ContentModelParticleRef {
  ref: string
}
export interface ContentModelParticleNested {
  nested: ContentModel
}
export interface ContentModelParticle {
  minOccurs: number
  maxOccurs: number | "unbounded"
  term: ContentModelParticleRef | ContentModelParticleNested
}
export interface ContentModel {
  kind: "Sequence" | "Choice"
  particles: ContentModelParticle[]
}
export interface AttributeUse {
  required: boolean
  ref: string
}
export interface IdentityConstraint {
  kind: "Key" | "Unique" | "KeyRef"
  selector: string
  fields: string[]
  refer: string | null
}
export interface ComplexType {
  uri: string
  name: string | null
  abstract: boolean
  extends: string | null
  contentModel: ContentModel
  attributeUses: AttributeUse[]
  identityConstraints: IdentityConstraint[]
}
export interface SimpleType {
  uri: string
  name: string | null
  facets: Record<string, number | boolean | string>
  enumeration: string[]
  patterns: string[]
  unionMembers: string[]
}
export interface NamespaceStructure {
  complexTypes: ComplexType[]
  simpleTypes: SimpleType[]
}
export type StructureResponse = Record<string, NamespaceStructure>

export interface Declaration {
  name: string
  kind: "Element" | "Attribute"
  type: string | null
  default: string | null
  fixed: string | null
  documentation: Record<string, string>
}
export type DeclarationsResponse = Record<string, Declaration>

export interface DocIssue {
  kind: string
  detail: string
}
export interface DocEntry {
  uri: string
  name: string
  languages: Record<string, string>
  issues?: DocIssue[]
  candidates?: string[]
}
export interface DocumentationResponse {
  matched: DocEntry[]
  unmatched: DocEntry[]
  ambiguous: DocEntry[]
  englishOnly: DocEntry[]
}

export interface AuditIssue {
  kind: string
  subjectName: string
  detail: string
  subjectUri: string | null
}
export interface AuditCounts {
  attached: number
  ambiguous: number
  unmatched: number
}
export interface AuditResponse {
  attachment: AuditCounts
  coverage: AuditCounts & { total: number }
  issues: AuditIssue[]
}

export interface ProvenanceRecord {
  sourceUri: string
  generatedAt: string
}

export interface RunSummary {
  runId: string
  createdAt: string
  xsdPath: string
  pdfPath: string
}
export interface RunDiffResponse {
  added: [string, string, string][]
  removed: [string, string, string][]
}

export interface ProposeCorrectionRequest {
  targetSubject: string
  targetPredicate: string
  targetLanguage: string
  proposedValue: string
  priorValue: string
  reason: string
}
export interface DecideCorrectionRequest {
  reason: string
}
export interface CorrectionResponse {
  correctionUri: string
}
export interface DecisionResponse {
  decisionUri: string
}
