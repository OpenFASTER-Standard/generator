# Provenance Platform — Plan D: React/shadcn-ui Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static `report.html` frontend with a real React
app served by `webapp/`: glance markers and expand panels with real
inline citations, a track-changes diff for corrections, a corrections
worklist with maker-checker approve/reject, run history/diffing, and a
focused per-field lineage graph.

**Architecture:** Vite + React + TypeScript + Tailwind v4 + shadcn/ui on
Base UI primitives, built to static assets. The app talks to the
`webapp` FastAPI service (Plan C) over relative `/api/...` paths — same
origin once built and served by `webapp`, so no CORS configuration is
needed.

**Tech Stack:** `vite`, `react`, `typescript`, `tailwindcss` v4,
`shadcn` CLI (`-b base`, Base UI primitives), `cytoscape` (lineage
graph), `vitest` + `@testing-library/react` (component tests).

**Spec:** `generator/docs/specs/2026-09-15-provenance-and-review-platform-design.md`

**Depends on:** Plans A, B, and C must all be merged first (the frontend
is a pure consumer of `webapp`'s `/api/...` endpoints).

## Global Constraints

- Lives at `generator/frontend/` — a separate Node project alongside the
  Python packages, not a Python package itself; not added to
  `pyproject.toml`.
- **Every scaffold command below was run and verified live before being
  written into this plan** (a real 12-component Base UI shadcn install,
  a real production build, and a real Vitest+RTL component test all
  passed) — including two real, confirmed gotchas: (1) TypeScript's
  `bundler` module resolution mode requires `paths` in `tsconfig.json`
  **without** `baseUrl` (the older `baseUrl`+`paths` pairing is
  deprecated in current TypeScript and breaks the build); (2) the
  `shadcn` CLI resolves the `@/` import alias by reading the **root**
  `tsconfig.json`'s own `compilerOptions.paths` directly — declaring the
  alias only in `tsconfig.app.json` (the file that actually applies to
  `src/`, per the project-references split `npm create vite` generates)
  is not enough; without it in the root file too, `shadcn add` silently
  writes components into a literal `./@/...` directory instead of
  `./src/...`.
- API calls always go through `frontend/src/lib/api.ts` — no raw
  `fetch()` calls scattered through components, so the base path and
  error handling stay in one place.
- No component fetches data on its own — each page component fetches
  once and passes data down, so tests can render with fixed data instead
  of mocking `fetch` everywhere.
- **Base UI components use a `render` prop to swap their rendered
  element, not Radix's `asChild` pattern** — confirmed directly against
  real shadcn-generated code (`DialogPrimitive.Close render={<Button
  variant="outline" />}>Close</DialogPrimitive.Close>`) and verified with
  a real `tsc --noEmit` type-check before being written into this plan.
  `asChild` is not a prop on these components at all; every trigger
  component in this plan (`DialogTrigger`, `CollapsibleTrigger`) uses
  `render={<Element .../>}` with the label/content as `children`, not
  `asChild` wrapping a child element.
- A correction's URI is embedded in a URL path segment
  base64-encoded — always via `toUrlSafeBase64` (Task 19), never plain
  `btoa()`, since the backend decodes with Python's
  `base64.urlsafe_b64decode` (`-`/`_` alphabet, not `+`/`/`).

---

### Task 19: Scaffold + API client

**Files:**
- Create: `frontend/` (full Vite project — exact commands below)
- Create: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.ts`

**Interfaces:**
- Produces: `frontend/src/lib/api.ts` exporting `apiGet<T>(path: string): Promise<T>`, `apiPost<T>(path: string, body: unknown, reviewer: string): Promise<T>`, and the TypeScript types below (all later tasks import from this one file).

- [ ] **Step 1: Scaffold the Vite + React + TypeScript project**

From `/work/generator`:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Add Tailwind v4**

```bash
npm install -D tailwindcss @tailwindcss/vite
```

Replace `frontend/src/index.css`'s entire contents with:

```css
@import "tailwindcss";
```

- [ ] **Step 3: Wire the `@/` import alias — both `vite.config.ts` and BOTH tsconfig files**

Replace `frontend/vite.config.ts`:

```typescript
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
})
```

Add to `frontend/tsconfig.app.json`'s `compilerOptions` (alongside the
existing `"moduleResolution": "bundler"` line — **no `baseUrl`**, see
this plan's Global Constraints):

```json
    "paths": {
      "@/*": ["./src/*"]
    },
```

Replace `frontend/tsconfig.json`'s entire contents (the root file —
**required**, not optional, see this plan's Global Constraints):

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

- [ ] **Step 4: Initialize shadcn/ui on Base UI**

```bash
npx shadcn@latest init -t vite -b base -p nova -y
```

Expected output ends with `Project initialization completed.` and
creates `frontend/components.json`, `frontend/src/lib/utils.ts`,
`frontend/src/components/ui/button.tsx`, and rewrites
`frontend/src/index.css` with the full design-token theme.

- [ ] **Step 5: Add every shadcn component this plan uses**

```bash
npx shadcn@latest add badge card collapsible dialog sheet table tabs select tooltip hover-card alert input -y
```

Expected: 12 files created under `frontend/src/components/ui/`. The
CLI will print a reminder that `tooltip` needs a `TooltipProvider`
wrapping the app — handled in Task 20.

- [ ] **Step 6: Add test tooling and Cytoscape**

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
npm install cytoscape @types/cytoscape
```

Create `frontend/vitest.config.ts`:

```typescript
import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/vitest-setup.ts"],
  },
})
```

Create `frontend/src/vitest-setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest"
```

Add to `frontend/package.json`'s `"scripts"`:

```json
    "test": "vitest run",
```

- [ ] **Step 7: Write the failing test for the API client**

`frontend/src/lib/api.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest"
import { apiGet, apiPost, toUrlSafeBase64 } from "@/lib/api"

describe("apiGet", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("fetches from /api and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hello: "world" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await apiGet<{ hello: string }>("/structure")

    expect(fetchMock).toHaveBeenCalledWith("/api/structure", undefined)
    expect(result).toEqual({ hello: "world" })
  })

  it("throws with the status code on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }),
    )

    await expect(apiGet("/missing")).rejects.toThrow("404")
  })
})

describe("apiPost", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("sends a JSON body with the reviewer header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ correctionUri: "urn:x" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await apiPost<{ correctionUri: string }>(
      "/corrections",
      { targetSubject: "urn:s" },
      "julian",
    )

    expect(fetchMock).toHaveBeenCalledWith("/api/corrections", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Reviewer": "julian" },
      body: JSON.stringify({ targetSubject: "urn:s" }),
    })
    expect(result).toEqual({ correctionUri: "urn:x" })
  })
})

describe("toUrlSafeBase64", () => {
  it("produces the same alphabet as Python's base64.urlsafe_b64encode, not plain btoa()", () => {
    // Bytes 255,255,255,254,253 -- chosen because standard base64 of them
    // is "/////v0=" (real, confirmed via Python's base64.b64encode), which
    // would silently break as a URL path segment. Python's own
    // base64.urlsafe_b64encode of the same bytes is "_____v0=" -- this
    // must match exactly, since the backend decodes with
    // base64.urlsafe_b64decode.
    const text = String.fromCharCode(255, 255, 255, 254, 253)

    const result = toUrlSafeBase64(text)

    expect(result).toBe("_____v0=")
    expect(result).not.toMatch(/[+/]/)
  })
})
```

- [ ] **Step 8: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/lib/api.test.ts
```

Expected: FAIL — `frontend/src/lib/api.ts` doesn't exist yet.

- [ ] **Step 9: Implement `frontend/src/lib/api.ts`**

```typescript
const API_BASE = "/api"

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
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
```

- [ ] **Step 10: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/lib/api.test.ts
```

Expected: PASS (3 tests).

- [ ] **Step 11: Confirm the project builds**

```bash
cd frontend && npm run build
```

Expected: completes with no TypeScript errors, produces `frontend/dist/`.

- [ ] **Step 12: `.gitignore` and commit**

Add to `/work/generator/.gitignore` (create it if it doesn't exist):

```
frontend/node_modules/
frontend/dist/
```

```bash
cd /work/generator
git add frontend/ .gitignore
git commit -m "Scaffold frontend: Vite + React + TS + Tailwind v4 + shadcn/ui (Base UI) + API client"
```

---

### Task 20: Page shell — nav tabs, reviewer picker, search

**Files:**
- Create: `frontend/src/components/PageShell.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/PageShell.test.tsx`

**Interfaces:**
- Produces:
  - `frontend/src/lib/reviewer.ts` — `useReviewer(): [string, (name: string) => void]` (a small hook backed by `localStorage`, so the picked reviewer persists across reloads)
  - `PageShell` component: props `{ activeTab: string; onTabChange: (tab: string) => void; search: string; onSearchChange: (value: string) => void; children: React.ReactNode }`, renders `TooltipProvider` (wrapping the whole app, per the shadcn CLI's own reminder from Task 19), a `Tabs` bar (Structure/Documentation/Audit/Corrections/Runs), a reviewer `Select`, and a search `Input`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/PageShell.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { PageShell } from "@/components/PageShell"

describe("PageShell", () => {
  it("renders all 5 nav tabs and calls onTabChange when one is clicked", async () => {
    const onTabChange = vi.fn()
    render(
      <PageShell activeTab="structure" onTabChange={onTabChange} search="" onSearchChange={() => {}}>
        <div>content</div>
      </PageShell>,
    )

    for (const label of ["Structure", "Documentation", "Audit", "Corrections", "Runs"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument()
    }

    await userEvent.click(screen.getByRole("tab", { name: "Documentation" }))
    expect(onTabChange).toHaveBeenCalledWith("documentation")
  })

  it("renders its children", () => {
    render(
      <PageShell activeTab="structure" onTabChange={() => {}} search="" onSearchChange={() => {}}>
        <div>real content</div>
      </PageShell>,
    )
    expect(screen.getByText("real content")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm install -D @testing-library/user-event && npx vitest run src/components/PageShell.test.tsx
```

Expected: FAIL — `frontend/src/components/PageShell.tsx` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/lib/reviewer.ts` and `frontend/src/components/PageShell.tsx`**

`frontend/src/lib/reviewer.ts`:

```typescript
import { useState } from "react"

const STORAGE_KEY = "provenance-platform:reviewer"

export function useReviewer(): [string, (name: string) => void] {
  const [reviewer, setReviewerState] = useState(
    () => window.localStorage.getItem(STORAGE_KEY) ?? "",
  )

  function setReviewer(name: string) {
    window.localStorage.setItem(STORAGE_KEY, name)
    setReviewerState(name)
  }

  return [reviewer, setReviewer]
}
```

`frontend/src/components/PageShell.tsx`:

```tsx
import type { ReactNode } from "react"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useReviewer } from "@/lib/reviewer"

const TABS: { key: string; label: string }[] = [
  { key: "structure", label: "Structure" },
  { key: "documentation", label: "Documentation" },
  { key: "audit", label: "Audit" },
  { key: "corrections", label: "Corrections" },
  { key: "runs", label: "Runs" },
]

// A small, fixed reviewer list -- appropriate for this project's real
// scale (an internal review team, not public signup). Add a name here
// when a new reviewer joins.
const REVIEWERS = ["julian", "someone-else"]

interface PageShellProps {
  activeTab: string
  onTabChange: (tab: string) => void
  search: string
  onSearchChange: (value: string) => void
  children: ReactNode
}

export function PageShell({ activeTab, onTabChange, search, onSearchChange, children }: PageShellProps) {
  const [reviewer, setReviewer] = useReviewer()

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-screen">
        <nav className="sticky top-0 z-10 flex items-center gap-4 border-b bg-background px-4 py-3">
          <Tabs value={activeTab} onValueChange={onTabChange}>
            <TabsList>
              {TABS.map((tab) => (
                <TabsTrigger key={tab.key} value={tab.key}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Input
            placeholder="Filter by name..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="ml-auto max-w-64"
          />
          <Select value={reviewer} onValueChange={(value) => value && setReviewer(value)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Reviewing as..." />
            </SelectTrigger>
            <SelectContent>
              {REVIEWERS.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </TooltipProvider>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/PageShell.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Wire `PageShell` into `frontend/src/App.tsx`**

Replace `frontend/src/App.tsx`:

```tsx
import { useState } from "react"
import { PageShell } from "@/components/PageShell"

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      <p className="text-muted-foreground">
        {activeTab} page -- wired up in later tasks.
      </p>
    </PageShell>
  )
}
```

- [ ] **Step 6: Confirm the project still builds**

```bash
cd frontend && npm run build
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/reviewer.ts frontend/src/components/PageShell.tsx frontend/src/components/PageShell.test.tsx frontend/src/App.tsx frontend/package.json frontend/package-lock.json
git commit -m "Add page shell: nav tabs, reviewer picker, search"
```

---

### Task 21: Structure + Declarations pages

**Files:**
- Create: `frontend/src/components/StructureView.tsx`
- Test: `frontend/src/components/StructureView.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `StructureView` component: props `{ structure: StructureResponse; declarations: DeclarationsResponse; search: string }` — renders each namespace's complex/simple types as a `Card` per construct, a content-model summary, attribute uses, identity constraints, and facets/patterns/enumeration for simple types; filters by `search` (case-insensitive substring on name).

- [ ] **Step 1: Write the failing test**

`frontend/src/components/StructureView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { StructureView } from "@/components/StructureView"
import type { DeclarationsResponse, StructureResponse } from "@/lib/api"

const structure: StructureResponse = {
  "https://example.org/test": {
    complexTypes: [
      {
        uri: "https://example.org/test#WidgetType",
        name: "WidgetType",
        abstract: false,
        extends: null,
        contentModel: { kind: "Sequence", particles: [] },
        attributeUses: [],
        identityConstraints: [],
      },
    ],
    simpleTypes: [
      {
        uri: "https://example.org/test#CodeType",
        name: "CodeType",
        facets: { maxLength: 10 },
        enumeration: [],
        patterns: [],
        unionMembers: [],
      },
    ],
  },
}
const declarations: DeclarationsResponse = {}

describe("StructureView", () => {
  it("renders every complex and simple type", () => {
    render(<StructureView structure={structure} declarations={declarations} search="" />)

    expect(screen.getByText("WidgetType")).toBeInTheDocument()
    expect(screen.getByText("CodeType")).toBeInTheDocument()
    expect(screen.getByText(/maxLength=10/)).toBeInTheDocument()
  })

  it("filters by a case-insensitive name substring", () => {
    render(<StructureView structure={structure} declarations={declarations} search="widget" />)

    expect(screen.getByText("WidgetType")).toBeInTheDocument()
    expect(screen.queryByText("CodeType")).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/StructureView.test.tsx
```

Expected: FAIL — `StructureView` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/components/StructureView.tsx`**

```tsx
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ComplexType, DeclarationsResponse, SimpleType, StructureResponse } from "@/lib/api"

interface StructureViewProps {
  structure: StructureResponse
  declarations: DeclarationsResponse
  search: string
}

function matchesSearch(name: string | null, search: string): boolean {
  if (!search) return true
  return (name ?? "").toLowerCase().includes(search.toLowerCase())
}

function ComplexTypeCard({ type }: { type: ComplexType }) {
  return (
    <Card id={type.uri} className="mb-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {type.name ?? "(anonymous)"}
          {type.abstract && <Badge variant="outline">abstract</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        {type.extends && <div>extends {type.extends}</div>}
        <div>{type.contentModel.kind} ({type.contentModel.particles.length} particle(s))</div>
        {type.attributeUses.length > 0 && (
          <div>{type.attributeUses.length} attribute use(s)</div>
        )}
        {type.identityConstraints.length > 0 && (
          <div>{type.identityConstraints.length} identity constraint(s)</div>
        )}
      </CardContent>
    </Card>
  )
}

function SimpleTypeCard({ type }: { type: SimpleType }) {
  const facetsText = Object.entries(type.facets)
    .map(([key, value]) => `${key}=${value}`)
    .join(", ")
  return (
    <Card id={type.uri} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{type.name ?? "(anonymous)"}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        {facetsText && <div>facets: {facetsText}</div>}
        {type.patterns.map((pattern, index) => (
          <code key={index} className="block break-all rounded bg-muted p-2 font-mono text-xs">
            {pattern}
          </code>
        ))}
        {type.enumeration.length > 0 && <div>enumeration: {type.enumeration.join(", ")}</div>}
      </CardContent>
    </Card>
  )
}

export function StructureView({ structure, search }: StructureViewProps) {
  return (
    <div>
      {Object.entries(structure).map(([namespace, block]) => {
        const complexTypes = block.complexTypes.filter((t) => matchesSearch(t.name, search))
        const simpleTypes = block.simpleTypes.filter((t) => matchesSearch(t.name, search))
        if (complexTypes.length === 0 && simpleTypes.length === 0) return null
        return (
          <section key={namespace} className="mb-8">
            <h3 className="mb-2 border-b pb-1 text-lg font-semibold">{namespace}</h3>
            {complexTypes.map((type) => (
              <ComplexTypeCard key={type.uri} type={type} />
            ))}
            {simpleTypes.map((type) => (
              <SimpleTypeCard key={type.uri} type={type} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/StructureView.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Wire it into `App.tsx` with real data fetching**

Replace `frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react"
import { PageShell } from "@/components/PageShell"
import { StructureView } from "@/components/StructureView"
import { apiGet } from "@/lib/api"
import type { DeclarationsResponse, StructureResponse } from "@/lib/api"

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")
  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [declarations, setDeclarations] = useState<DeclarationsResponse | null>(null)

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DeclarationsResponse>("/declarations").then(setDeclarations)
  }, [])

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      {activeTab === "structure" && structure && declarations && (
        <StructureView structure={structure} declarations={declarations} search={search} />
      )}
      {activeTab !== "structure" && (
        <p className="text-muted-foreground">{activeTab} page -- wired up in later tasks.</p>
      )}
    </PageShell>
  )
}
```

- [ ] **Step 6: Confirm the project builds**

```bash
cd frontend && npm run build
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/StructureView.tsx frontend/src/components/StructureView.test.tsx frontend/src/App.tsx
git commit -m "Add Structure view with search filtering"
```

---

### Task 22: Documentation page — glance marker + expand panel + real citations

**Files:**
- Create: `frontend/src/components/ProvenanceMarker.tsx`
- Create: `frontend/src/components/DocumentationView.tsx`
- Test: `frontend/src/components/ProvenanceMarker.test.tsx`
- Test: `frontend/src/components/DocumentationView.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces:
  - `ProvenanceMarker` component: props `{ subject: string; predicate: string; value: string; lang?: string }` — a small colored `Badge` dot that, on click, fetches `/api/provenance` and expands a `Collapsible` panel showing the real citation (an `<img>` for a `citation:pdf?...` source, a syntax-styled `<code>` block for `citation:xsd?...`, or a plain "recorded, no source locator" note for anything else).
  - `DocumentationView` component: props `{ documentation: DocumentationResponse; search: string }` — renders the 4 groups (Matched/Unmatched/Ambiguous/English-only), each entry showing every language via `ProvenanceMarker`, matched entries' issues, ambiguous entries' candidates.

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/ProvenanceMarker.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProvenanceMarker } from "@/components/ProvenanceMarker"

describe("ProvenanceMarker", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("fetches and shows a PDF citation image on click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sourceUri: "citation:pdf?path=/a.pdf&page=5&x0=1&top=2&x1=3&bottom=4",
          generatedAt: "2026-09-15T14:00:00Z",
        }),
      }),
    )

    render(<ProvenanceMarker subject="urn:s" predicate="urn:p" value="hello" lang="en" />)
    await userEvent.click(screen.getByRole("button"))

    expect(await screen.findByRole("img")).toBeInTheDocument()
  })

  it("shows a plain note when no provenance is recorded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))

    render(<ProvenanceMarker subject="urn:s" predicate="urn:p" value="hello" />)
    await userEvent.click(screen.getByRole("button"))

    expect(await screen.findByText(/no source recorded/i)).toBeInTheDocument()
  })
})
```

`frontend/src/components/DocumentationView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DocumentationView } from "@/components/DocumentationView"
import type { DocumentationResponse } from "@/lib/api"

const documentation: DocumentationResponse = {
  matched: [
    {
      uri: "urn:s1", name: "Matched1", languages: { de: "Deutsch.", en: "English." },
      issues: [{ kind: "length_ratio", detail: "ratio=9.99" }],
    },
  ],
  unmatched: [{ uri: "urn:s2", name: "Unmatched1", languages: { de: "Nur Deutsch." } }],
  ambiguous: [
    { uri: "urn:s3", name: "Ambiguous1", languages: { de: "Mehrdeutig." }, candidates: ["A", "B"] },
  ],
  englishOnly: [],
}

describe("DocumentationView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders all 3 non-empty groups with their real content", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))
    render(<DocumentationView documentation={documentation} search="" />)

    expect(screen.getByText("Matched1")).toBeInTheDocument()
    expect(screen.getByText(/length_ratio/)).toBeInTheDocument()
    expect(screen.getByText("Unmatched1")).toBeInTheDocument()
    expect(screen.getByText("Ambiguous1")).toBeInTheDocument()
    expect(screen.getByText("A")).toBeInTheDocument()
    expect(screen.getByText("B")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/ProvenanceMarker.test.tsx src/components/DocumentationView.test.tsx
```

Expected: FAIL — neither component exists yet.

- [ ] **Step 3: Implement `frontend/src/components/ProvenanceMarker.tsx`**

```tsx
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { apiGet } from "@/lib/api"
import type { ProvenanceRecord } from "@/lib/api"

interface ProvenanceMarkerProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

function parseCitationUrl(sourceUri: string): URL | null {
  try {
    return new URL(sourceUri.replace(/^citation:/, "https://citation.invalid/"))
  } catch {
    return null
  }
}

export function ProvenanceMarker({ subject, predicate, value, lang }: ProvenanceMarkerProps) {
  const [open, setOpen] = useState(false)
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)

  async function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (nextOpen && record === undefined) {
      const params = new URLSearchParams({ subject, predicate, value })
      if (lang) params.set("lang", lang)
      const result = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
      setRecord(result)
    }
  }

  function renderCitation() {
    if (record === undefined) return <p className="text-xs text-muted-foreground">Loading...</p>
    if (record === null) return <p className="text-xs text-muted-foreground">No source recorded.</p>

    const url = parseCitationUrl(record.sourceUri)
    if (url && record.sourceUri.startsWith("citation:pdf")) {
      const query = new URLSearchParams(url.search)
      return (
        <img
          src={`/api/citations/pdf?${query.toString()}`}
          alt={`Source citation, page ${query.get("page")}`}
          className="max-w-full rounded border"
        />
      )
    }
    if (url && record.sourceUri.startsWith("citation:xsd")) {
      return (
        <p className="text-xs text-muted-foreground">
          From {url.searchParams.get("file")} ({url.searchParams.get("component") ?? "this run"}).
        </p>
      )
    }
    return <p className="text-xs text-muted-foreground">No source recorded.</p>
  }

  return (
    <Collapsible open={open} onOpenChange={handleOpenChange}>
      <CollapsibleTrigger
        render={
          <button
            type="button"
            aria-label="Show provenance"
            className="inline-block size-2 rounded-full bg-muted-foreground/40 align-middle ml-1"
          />
        }
      />
      <CollapsibleContent className="mt-1 rounded border bg-muted/30 p-2">
        {renderCitation()}
      </CollapsibleContent>
    </Collapsible>
  )
}
```

Note: `aria-label="Show provenance"` makes the marker a real, accessible
`role="button"` target (matching the test's `getByRole("button")`)
without needing visible text — its whole design purpose is to be a
small, low-weight dot, not a labeled button.

- [ ] **Step 4: Implement `frontend/src/components/DocumentationView.tsx`**

```tsx
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProvenanceMarker } from "@/components/ProvenanceMarker"
import type { DocEntry, DocumentationResponse } from "@/lib/api"

interface DocumentationViewProps {
  documentation: DocumentationResponse
  search: string
}

const GROUPS: { key: keyof DocumentationResponse; label: string; variant: "default" | "secondary" | "destructive" | "outline" }[] = [
  { key: "matched", label: "Matched", variant: "default" },
  { key: "unmatched", label: "Unmatched", variant: "secondary" },
  { key: "ambiguous", label: "Ambiguous", variant: "destructive" },
  { key: "englishOnly", label: "English-only", variant: "outline" },
]

function matchesSearch(name: string, search: string): boolean {
  return !search || name.toLowerCase().includes(search.toLowerCase())
}

function DocEntryCard({ entry }: { entry: DocEntry }) {
  return (
    <Card id={`doc:${entry.uri}`} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{entry.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        {Object.entries(entry.languages).map(([lang, text]) => (
          <div key={lang}>
            {lang.toUpperCase()}: {text}
            <ProvenanceMarker subject={entry.uri} predicate="documentation" value={text} lang={lang} />
          </div>
        ))}
        {entry.issues?.map((issue, index) => (
          <div key={index} className="text-destructive text-xs">
            {issue.kind}: {issue.detail}
          </div>
        ))}
        {entry.candidates && (
          <ul className="list-disc pl-4 text-xs text-muted-foreground">
            {entry.candidates.map((candidate, index) => (
              <li key={index}>{candidate}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function DocumentationView({ documentation, search }: DocumentationViewProps) {
  return (
    <div>
      {GROUPS.map(({ key, label, variant }) => {
        const entries = documentation[key].filter((entry) => matchesSearch(entry.name, search))
        if (entries.length === 0) return null
        return (
          <section key={key} className="mb-8">
            <h3 className="mb-2 flex items-center gap-2 text-lg font-semibold">
              {label} <Badge variant={variant}>{entries.length}</Badge>
            </h3>
            {entries.map((entry) => (
              <DocEntryCard key={entry.uri} entry={entry} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/ProvenanceMarker.test.tsx src/components/DocumentationView.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 6: Wire it into `App.tsx`**

In `frontend/src/App.tsx`, add a `documentation` state fetched the same
way as `structure`/`declarations` (Task 21's pattern), and render
`<DocumentationView documentation={documentation} search={search} />`
when `activeTab === "documentation"`.

- [ ] **Step 7: Confirm the project builds, then commit**

```bash
cd frontend && npm run build
git add frontend/src/components/ProvenanceMarker.tsx frontend/src/components/DocumentationView.tsx frontend/src/components/ProvenanceMarker.test.tsx frontend/src/components/DocumentationView.test.tsx frontend/src/App.tsx
git commit -m "Add Documentation view with click-to-expand real citations"
```

---

### Task 23: Audit page

**Files:**
- Create: `frontend/src/components/AuditView.tsx`
- Test: `frontend/src/components/AuditView.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `AuditView` component: props `{ audit: AuditResponse }` — renders the attachment/coverage counts with the captions from Phase 1 (kept verbatim, still accurate), then the issue list with each issue linking to `#doc:<subjectUri>` when `subjectUri` is present.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/AuditView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AuditView } from "@/components/AuditView"
import type { AuditResponse } from "@/lib/api"

const audit: AuditResponse = {
  attachment: { attached: 294, ambiguous: 68, unmatched: 53 },
  coverage: { total: 380, attached: 294, ambiguous: 68, unmatched: 18 },
  issues: [
    { kind: "untranslated", subjectName: "Foo", detail: "identical text", subjectUri: "urn:foo" },
  ],
}

describe("AuditView", () => {
  it("renders both count blocks with their captions and the issue list", () => {
    render(<AuditView audit={audit} />)

    expect(screen.getByText(/attached=294, ambiguous=68, unmatched=53/)).toBeInTheDocument()
    expect(screen.getByText(/total=380/)).toBeInTheDocument()
    expect(screen.getByText(/every named construct in the schema/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Foo" })).toHaveAttribute("href", "#doc:urn:foo")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/AuditView.test.tsx
```

Expected: FAIL — `AuditView` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/components/AuditView.tsx`**

```tsx
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/components/AuditView.test.tsx
```

Expected: PASS (1 test).

- [ ] **Step 5: Wire into `App.tsx`, confirm build, commit**

Same fetch-and-render pattern as Tasks 21/22.

```bash
cd frontend && npm run build
git add frontend/src/components/AuditView.tsx frontend/src/components/AuditView.test.tsx frontend/src/App.tsx
git commit -m "Add Audit view"
```

---

### Task 24: Corrections worklist — propose, approve, reject

**Files:**
- Create: `frontend/src/components/CorrectionsView.tsx`
- Test: `frontend/src/components/CorrectionsView.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `CorrectionsView` component: props `{ pending: { correctionUri: string; targetSubject: string; proposedValue: string; proposer: string }[]; reviewer: string; onDecided: () => void }` — a `Table` with Approve/Reject buttons (disabled when `reviewer` equals the row's own `proposer`), each opening a `Dialog` for an optional comment before calling `apiPost`.

Note: this task assumes a `GET /api/corrections/pending` listing endpoint
— **not yet built in Plan C**. Add it now as part of this task's own
Step 3 (a small, additive FastAPI route, same shape as Plan C's other
read routes) rather than retrofitting Plan C:

```python
# Append to webapp/routes_corrections.py

@router.get("/corrections/pending")
def list_pending(request: Request):
    results = list(request.app.state.dataset.query(f"""
    PREFIX review: <https://purl.openfaster.org/review/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    SELECT ?correction ?subject ?value ?proposer WHERE {{
      GRAPH <{request.app.state.corrections_graph_uri}> {{
        ?correction a review:Correction ;
                    review:targetSubject ?subject ;
                    review:proposedValue ?value ;
                    prov:wasAttributedTo ?proposer .
        FILTER NOT EXISTS {{ ?decision review:decides ?correction }}
      }}
    }}
    """))
    return [
        {
            "correctionUri": str(row["correction"]), "targetSubject": str(row["subject"]),
            "proposedValue": str(row["value"]), "proposer": str(row["proposer"]).rsplit("-", 1)[-1],
        }
        for row in results
    ]
```

Add a matching backend test to `tests/webapp/test_routes_corrections.py`
before implementing (same TDD discipline as every other backend task —
this is a small addition to Plan C's own file, done here because the
frontend is what surfaced the real need for it):

```python
def test_list_pending_returns_only_undecided_corrections():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        correction_uri = proposal.json()["correctionUri"]

        pending = client.get("/api/corrections/pending")
        assert pending.status_code == 200
        assert any(c["correctionUri"] == correction_uri for c in pending.json())

        client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "ok"}, headers={"X-Reviewer": "someone-else"},
        )

        pending_after = client.get("/api/corrections/pending")
        assert not any(c["correctionUri"] == correction_uri for c in pending_after.json())
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_corrections.py -v`
(FAIL first — no `/pending` route yet — then PASS after adding the route
above), then commit that backend addition on its own:

```bash
cd /work/generator
git add webapp/routes_corrections.py tests/webapp/test_routes_corrections.py
git commit -m "Add GET /api/corrections/pending, needed by the corrections worklist UI"
```

- [ ] **Step 1: Write the failing frontend test**

`frontend/src/components/CorrectionsView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CorrectionsView } from "@/components/CorrectionsView"

const pending = [
  { correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Fixed.", proposer: "julian" },
]

describe("CorrectionsView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("disables approve/reject for the correction's own proposer", () => {
    render(<CorrectionsView pending={pending} reviewer="julian" onDecided={() => {}} />)

    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /reject/i })).toBeDisabled()
  })

  it("lets a different reviewer approve, and calls onDecided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ decisionUri: "urn:d1" }) }))
    const onDecided = vi.fn()

    render(<CorrectionsView pending={pending} reviewer="someone-else" onDecided={onDecided} />)
    await userEvent.click(screen.getByRole("button", { name: /approve/i }))
    await userEvent.click(screen.getByRole("button", { name: /confirm/i }))

    expect(onDecided).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/components/CorrectionsView.test.tsx
```

Expected: FAIL — `CorrectionsView` doesn't exist.

- [ ] **Step 3: (see the backend `/pending` route above, done first)**

- [ ] **Step 4: Implement `frontend/src/components/CorrectionsView.tsx`**

```tsx
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/CorrectionsView.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 6: Wire into `App.tsx`, confirm build, commit**

```bash
cd frontend && npm run build
git add frontend/src/components/CorrectionsView.tsx frontend/src/components/CorrectionsView.test.tsx frontend/src/App.tsx
git commit -m "Add corrections worklist with maker-checker approve/reject"
```

---

### Task 25: Lineage graph + Runs page

**Files:**
- Create: `frontend/src/components/LineageGraph.tsx`
- Create: `frontend/src/components/RunsView.tsx`
- Test: `frontend/src/components/LineageGraph.test.tsx`
- Test: `frontend/src/components/RunsView.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces:
  - `LineageGraph` component: props `{ open: boolean; onOpenChange: (open: boolean) => void; subject: string; predicate: string; sourceUri: string | null }` — a `Sheet` containing a Cytoscape.js graph with 2 nodes ("source" and "current value") and one edge, rendered into a `ref`-attached `div`.
  - `RunsView` component: props `{ runs: RunSummary[] }` — a `Table` of runs plus two `Select`s and a "Diff" button that fetches `/api/runs/{a}/diff/{b}` and shows the result.

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/LineageGraph.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { LineageGraph } from "@/components/LineageGraph"

describe("LineageGraph", () => {
  it("renders a graph container when open with a real source", () => {
    render(
      <LineageGraph
        open
        onOpenChange={() => {}}
        subject="urn:s"
        predicate="urn:p"
        sourceUri="citation:xsd?file=/a.xsd&component=%7Bns%7DType"
      />,
    )

    expect(screen.getByTestId("lineage-graph-container")).toBeInTheDocument()
  })
})
```

`frontend/src/components/RunsView.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RunsView } from "@/components/RunsView"

const runs = [
  { runId: "run-a", createdAt: "2026-09-15T09:00:00Z", xsdPath: "a.xsd", pdfPath: "a.pdf" },
  { runId: "run-b", createdAt: "2026-09-16T09:00:00Z", xsdPath: "b.xsd", pdfPath: "b.pdf" },
]

describe("RunsView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lists every real run", () => {
    render(<RunsView runs={runs} />)
    expect(screen.getByText("run-a")).toBeInTheDocument()
    expect(screen.getByText("run-b")).toBeInTheDocument()
  })

  it("fetches and shows a diff between two selected runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ added: [["s", "p", "new"]], removed: [["s", "p", "old"]] }),
      }),
    )

    render(<RunsView runs={runs} />)
    await userEvent.click(screen.getByRole("button", { name: /diff/i }))

    expect(await screen.findByText(/new/)).toBeInTheDocument()
    expect(await screen.findByText(/old/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/components/LineageGraph.test.tsx src/components/RunsView.test.tsx
```

Expected: FAIL — neither component exists yet.

- [ ] **Step 3: Implement `frontend/src/components/LineageGraph.tsx`**

```tsx
import cytoscape from "cytoscape"
import { useEffect, useRef } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"

interface LineageGraphProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subject: string
  predicate: string
  sourceUri: string | null
}

export function LineageGraph({ open, onOpenChange, subject, predicate, sourceUri }: LineageGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        { data: { id: "source", label: sourceUri ?? "unknown source" } },
        { data: { id: "current", label: `${subject} / ${predicate}` } },
        { data: { id: "edge", source: "source", target: "current", label: "wasDerivedFrom" } },
      ],
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 10, "background-color": "#0b5fff" } },
        { selector: "edge", style: { label: "data(label)", "font-size": 8, "curve-style": "bezier", "target-arrow-shape": "triangle" } },
      ],
      layout: { name: "breadthfirst", directed: true },
    })

    return () => cy.destroy()
  }, [open, subject, predicate, sourceUri])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Lineage</SheetTitle>
        </SheetHeader>
        <div ref={containerRef} data-testid="lineage-graph-container" className="h-96 w-full" />
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 4: Implement `frontend/src/components/RunsView.tsx`**

```tsx
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet } from "@/lib/api"
import type { RunDiffResponse, RunSummary } from "@/lib/api"

interface RunsViewProps {
  runs: RunSummary[]
}

export function RunsView({ runs }: RunsViewProps) {
  const [runA, setRunA] = useState(runs[0]?.runId ?? "")
  const [runB, setRunB] = useState(runs[runs.length - 1]?.runId ?? "")
  const [diff, setDiff] = useState<RunDiffResponse | null>(null)

  async function loadDiff() {
    setDiff(await apiGet<RunDiffResponse>(`/runs/${runA}/diff/${runB}`))
  }

  return (
    <div>
      <Table className="mb-4">
        <TableHeader>
          <TableRow>
            <TableHead>Run</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow key={run.runId}>
              <TableCell>{run.runId}</TableCell>
              <TableCell>{run.createdAt}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center gap-2">
        <Select value={runA} onValueChange={(value) => value && setRunA(value)}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            {runs.map((run) => <SelectItem key={run.runId} value={run.runId}>{run.runId}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={runB} onValueChange={(value) => value && setRunB(value)}>
          <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            {runs.map((run) => <SelectItem key={run.runId} value={run.runId}>{run.runId}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button onClick={loadDiff}>Diff</Button>
      </div>
      {diff && (
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <h4 className="font-semibold">Removed</h4>
            {diff.removed.map((row, index) => <div key={index}>{row.join(" ")}</div>)}
          </div>
          <div>
            <h4 className="font-semibold">Added</h4>
            {diff.added.map((row, index) => <div key={index}>{row.join(" ")}</div>)}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/LineageGraph.test.tsx src/components/RunsView.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 6: Wire everything into `App.tsx`**

Final `frontend/src/App.tsx`, tying together every task in this plan:

```tsx
import { useCallback, useEffect, useState } from "react"
import { AuditView } from "@/components/AuditView"
import { CorrectionsView } from "@/components/CorrectionsView"
import { DocumentationView } from "@/components/DocumentationView"
import { PageShell } from "@/components/PageShell"
import { RunsView } from "@/components/RunsView"
import { StructureView } from "@/components/StructureView"
import { apiGet } from "@/lib/api"
import { useReviewer } from "@/lib/reviewer"
import type {
  AuditResponse, DeclarationsResponse, DocumentationResponse, RunSummary, StructureResponse,
} from "@/lib/api"

interface PendingCorrection {
  correctionUri: string
  targetSubject: string
  proposedValue: string
  proposer: string
}

export default function App() {
  const [activeTab, setActiveTab] = useState("structure")
  const [search, setSearch] = useState("")
  const [reviewer] = useReviewer()

  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [declarations, setDeclarations] = useState<DeclarationsResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)
  const [audit, setAudit] = useState<AuditResponse | null>(null)
  const [pending, setPending] = useState<PendingCorrection[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])

  const refreshPending = useCallback(() => {
    apiGet<PendingCorrection[]>("/corrections/pending").then(setPending)
  }, [])

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DeclarationsResponse>("/declarations").then(setDeclarations)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
    apiGet<AuditResponse>("/audit").then(setAudit)
    apiGet<RunSummary[]>("/runs").then(setRuns)
    refreshPending()
  }, [refreshPending])

  return (
    <PageShell activeTab={activeTab} onTabChange={setActiveTab} search={search} onSearchChange={setSearch}>
      {activeTab === "structure" && structure && declarations && (
        <StructureView structure={structure} declarations={declarations} search={search} />
      )}
      {activeTab === "documentation" && documentation && (
        <DocumentationView documentation={documentation} search={search} />
      )}
      {activeTab === "audit" && audit && <AuditView audit={audit} />}
      {activeTab === "corrections" && (
        <CorrectionsView pending={pending} reviewer={reviewer} onDecided={refreshPending} />
      )}
      {activeTab === "runs" && <RunsView runs={runs} />}
    </PageShell>
  )
}
```

- [ ] **Step 7: Confirm the whole app builds and the full test suite passes**

```bash
cd frontend
npm run build
npx vitest run
```

Expected: build succeeds, all frontend tests pass.

- [ ] **Step 8: Serve the built frontend from `webapp`**

Modify `webapp/main.py` — add, right before `return app` (after every
router is registered):

```python
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
```

(Guarded by `.exists()` so `webapp`'s own backend tests, which never
run `npm run build`, still pass without a `frontend/dist/` directory
present.)

- [ ] **Step 9: End-to-end manual check**

```bash
cd frontend && npm run build
cd /work && python3 -c "
import uvicorn
from webapp.main import create_app
app = create_app(
    '/tmp/manual_check_store',
    '/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd',
    '/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf',
)
uvicorn.run(app, host='127.0.0.1', port=8010)
"
```

Open `http://127.0.0.1:8010/` in a browser (or check with Playwright,
per this project's own established UI-verification convention) and
confirm: all 5 tabs render real data, clicking a documentation entry's
provenance marker shows a real citation, and the corrections worklist
loads. Stop the server (Ctrl-C) and delete `/tmp/manual_check_store`
when done.

- [ ] **Step 10: Commit**

```bash
cd /work/generator
git add frontend/src/components/LineageGraph.tsx frontend/src/components/RunsView.tsx frontend/src/components/LineageGraph.test.tsx frontend/src/components/RunsView.test.tsx frontend/src/App.tsx webapp/main.py
git commit -m "Add lineage graph, runs/diff view, and serve the built frontend from webapp"
```
