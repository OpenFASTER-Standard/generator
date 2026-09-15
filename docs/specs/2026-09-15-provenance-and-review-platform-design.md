# Provenance & Review Platform — Design

Sub-project 3b, Phase 2, of `/work/openfaster-restructuring/STATUS.md`.
Phase 1 (a self-contained static `report.html`, see
`2026-09-15-generator-output-report-design.md`) is complete, merged, and
remains useful as a record of what shipped — but this phase supersedes
its architecture wholesale, per explicit operator direction ("you're not
bound to any previous decisions, you can always build your absolute
dream world"). In particular, Phase 1's own Non-Goal — "No server, no CI
automation, no history/diffing" — is explicitly reversed here.

## Context

Phase 1 gave the operator a way to see what the generator produced.
Using it surfaced a deeper need: seeing a value isn't the same as
trusting it. Concretely, the operator asked, in order:

1. Fix concrete clarity bugs (stale labels, an unexplained-looking audit
   number split, a real-but-alarming-looking DIN 91379 regex).
2. A way to verify the *correspondence* between the official XSD and what
   the generator produced — not just look at the parsed result in
   isolation.
3. Full **provenance** for every piece of data, across (at least) three
   sources that will each keep growing: the official XSDs, the official
   English annex PDF, and the operator's own human corrections (typo
   fixes, added missing translations) — which must survive the pipeline
   being re-run against a newer XSD/PDF version without being silently
   lost or silently misapplied.
4. A "dream world" verification experience: real inline evidence (an
   actual PDF page crop, an actual XSD fragment) rather than re-typed
   citations; a navigable lineage graph; provenance of *why* a match was
   made, not just that it was; diffing across pipeline runs; a real
   maker-checker review workflow for corrections.

This document designs all of that as one project, per explicit operator
instruction to treat it as such rather than a staged sequence of
separate sub-projects.

## Non-Goals

- **Not a general-purpose RDF/provenance browser.** Scoped to this
  project's own `xsdo:` vocabulary, documentation/correction data, and
  the two real source types (XSD, annex PDF) — not arbitrary graphs, not
  SPARQL exposed directly to the operator.
- **No fabricated confidence scores.** The PDF matcher is exact-name
  lookup, not a fuzzy/ML matcher — there is no real continuous signal to
  attach a number to. Reasoning provenance is categorical (unique /
  ambiguous / unmatched) plus the real candidate list, not an invented
  float.
- **No real authentication/SSO.** This runs locally for a small, trusted
  review group. Reviewer identity is a small configured list picked from
  a dropdown, not passwords or sessions.
- **No exact line numbers for XSD citations in this first cut.**
  `xmlschema` parses via stdlib `ElementTree`, which drops source line
  info; recovering it needs a separate `lxml` pass matching by
  construct name. The fragment + exact source file is real, useful
  provenance on its own — line numbers are a fast-follow, not a blocker.
- **`extraction/`'s own parsing logic is untouched.** `extract()` and
  `attach_english_documentation()` keep their existing signatures and
  tests; only where their *output* is loaded (a persistent store instead
  of an in-memory `Graph` handed straight to a report generator) changes.
- **No distributed/multi-instance deployment.** One embedded Oxigraph
  store file, one service process, run locally on demand — not a
  clustered or multi-tenant system.
- **No email/Slack notifications for pending reviews.** The Corrections
  worklist view is the mechanism; push notifications are a real future
  enhancement, not built speculatively now.

## Architecture

```
generator/
  extraction/          # unchanged: extract(), attach_english_documentation(), audits
  store/                # NEW: the persistent Oxigraph-backed graph store
    __init__.py
    database.py         # open/create the store; rdflib.Graph(store="Oxigraph") wrapper
    runs.py              # write a new graph:run-<ts>, list/diff runs
  provenance/           # NEW: this project's PROV-O usage + RDF-star helpers
    __init__.py
    vocab.py             # PROV namespace + the specific predicates actually used
    record.py            # attach/read a provenance quoted-triple for one fact
  review/                # NEW: correction proposals + maker-checker approval
    __init__.py
    shapes.ttl            # SHACL shapes: status enum, proposer != approver, etc.
    corrections.py         # propose/approve/reject, staleness detection
  citations/             # NEW: real inline evidence capture
    __init__.py
    pdf_citation.py         # pdfplumber page crop -> PNG blob
    xsd_citation.py          # xmlschema .elem -> exact source fragment + file
  webapp/                # NEW: the FastAPI service
    __init__.py
    main.py                  # app + startup (opens the store)
    routes_structure.py       # /api/structure, /declarations, /documentation, /audit
    routes_provenance.py       # /api/provenance/*, /api/citations/*
    routes_runs.py              # /api/runs, /api/runs/{a}/diff/{b}
    routes_corrections.py        # /api/corrections, .../approve, .../reject
  frontend/               # NEW: React + Vite + Tailwind + shadcn/ui (on Base UI)
    src/
      components/           # glance marker, expand panel, diff view, lineage graph
      pages/                  # Structure / Documentation / Audit / Corrections / Runs
    (built to static assets, served by webapp or via its own dev server)
```

Verified feasible directly, not assumed:

- `pyoxigraph` (embeddable, transactional, real SPARQL 1.1 Query+Update,
  named graphs, RDF-star quoted triples) installs clean and behaves
  exactly as needed for named-graph-per-run storage, aggregate queries
  (`GROUP BY`/`COUNT`), and per-fact provenance via quoted triples — all
  confirmed live against real queries during this design.
- `oxrdflib` lets existing code keep using the plain `rdflib.Graph` API
  (`.subjects()`, `.objects()`, `.value()`) backed by that same Oxigraph
  store — confirmed live. This means `reporting/data.py`'s existing,
  tested `build_structure`/`build_declarations`/etc. need **no rewrite**,
  only a change to which named graph they read.
- `pyshacl` installs clean and is a real, current, actively maintained
  SHACL engine — used to enforce the integrity constraints a SQL schema
  would otherwise give for free (status enums, proposer ≠ approver).
- Real SPARQL diff between two named graphs (`FILTER NOT EXISTS`) was run
  against synthetic data and correctly produced only the added/removed
  triples, excluding unchanged ones.
- `pdfplumber` (already a dependency) can extract word-level bounding
  boxes with page numbers and crop+render a page region to a real PNG —
  confirmed against the actual annex PDF, produced a legible crop, no new
  dependency needed.
- `xmlschema`'s parsed type/element objects expose `.elem` (a stdlib
  `ElementTree` element); `ET.tostring(t.elem)` gives the exact source
  fragment, and `t.schema.source.url` gives the exact real file it came
  from — confirmed against the real corpus (e.g. `MeldepflichtigeStelleType`
  is actually defined in `MiKaDiv_FM_Personentypen_1.02.xsd`, not the root
  file extraction is pointed at — previously invisible information).

## Data model

**Named graphs**, one Oxigraph store file (analogous to one SQLite file):

- `graph:run-<ISO-timestamp>` — one per extraction run, immutable once
  written. Carries the full `xsdo:` graph `extract()` +
  `attach_english_documentation()` produce, plus run metadata (source
  XSD/PDF paths and content hashes) in a small `graph:runs-index`.
  **Provenance quads for that run's own facts live in this same named
  graph**, not a separate one (refined during planning: a provenance
  record is meaningless without the specific run it describes anyway, so
  named-graph-per-run already gives provenance the isolation a separate
  `graph:prov` would have added no real value over).
- `graph:corrections` — append-only. Correction proposals and
  approval/rejection decisions. Never edited or deleted in place; a
  change is always a new record.
- `current` is not stored — it's computed: the latest `graph:run-*` with
  any *approved* correction from `graph:corrections` overlaid.

**Provenance**, using real PROV-O terms via RDF-star (verified live,
no reification bloat):

```turtle
<< :WIdNr xsdo:documentation "Kurze Wirtschafts-ID."@de >>
    prov:wasDerivedFrom  <citation:xsd/MiKaDiv_FM_Personentypen_1.02.xsd#frag-...> ;
    prov:generatedAtTime "2026-09-15T14:00:00Z"^^xsd:dateTime .
```

Structural facts (content models, cardinalities, facets, `xsdo:extends`,
required/optional attribute uses) get **one blanket citation per run**
(the run's own source-file/hash metadata), not per-triple records — they
have exactly one possible source (the current official XSD's normative
declarations) and no legitimate correction path; per-triple provenance
there would be overhead with no real payoff. Prose fields (German
documentation, English documentation, and any future free-text field)
get real per-fact provenance records, since they are genuinely
multi-source and genuinely correctable.

**Corrections**, as PROV-O revisions:

```turtle
:correction-42
    a review:Correction ;
    review:targetSubject :WIdNrTwo ; review:targetPredicate xsdo:documentation ;
    review:targetLanguage "de" ;
    review:proposedValue "Eine viel längere Wirtschafts-Identifikationsnummer." ;
    prov:wasRevisionOf << :WIdNrTwo xsdo:documentation "Eine viel, viel, ..."@de >> ;
    prov:wasAttributedTo :reviewer-julian ;
    review:reason "Fixed a run-on repetition." ;
    prov:generatedAtTime "2026-09-15T15:00:00Z"^^xsd:dateTime ;
    review:status "proposed" .

:approval-42
    a review:Decision ; review:decides :correction-42 ;
    review:outcome "approved" ; prov:wasAttributedTo :reviewer-someone-else ;
    prov:generatedAtTime "2026-09-16T09:00:00Z"^^xsd:dateTime .
```

SHACL shapes (`review/shapes.ttl`) enforce: `review:status` is one of
`proposed`/`approved`/`rejected`; every `review:Decision`'s
`prov:wasAttributedTo` differs from the `review:Correction` it decides;
a `review:Correction` has exactly one `targetSubject`/`targetPredicate`.

## Run history, diffing, and staleness

- Diffing two runs is the verified `FILTER NOT EXISTS` pattern over their
  two named graphs — no bespoke diff algorithm, real SPARQL.
- **Staleness detection**: when a new run lands, for every *approved*
  correction, compare its `prov:wasRevisionOf` value against that same
  (subject, predicate, language) in the new run's graph. If the new raw
  value differs from what the correction was made against, the
  correction is flagged `stale` (a computed status, not stored) —
  surfaced with the same visual weight as a merge conflict, never
  silently re-applied or silently dropped.
- A new proposal for a field with an existing `proposed`-status
  correction automatically supersedes it (the old one becomes `rejected`
  with `review:reason "superseded by a newer proposal"`), so stale
  duplicate proposals cannot pile up.

## Citations & matcher reasoning

- **PDF citations**: `citations/pdf_citation.py` takes a page number +
  bounding box (already available from `pdfplumber`'s word extraction)
  and produces a cropped PNG, stored as a blob referenced by a
  `citation:pdf/...` URI used in `prov:wasDerivedFrom`.
- **XSD citations**: `citations/xsd_citation.py` takes an `xmlschema`
  type/element object, serializes `.elem` via `ET.tostring`, and records
  the source file (`t.schema.source.url`) alongside it as a
  `citation:xsd/...` URI.
- **Matcher reasoning**: `attach_english_documentation` is extended to
  record, for *every* documented subject (not only ambiguous ones), the
  real decision category (`unique_match` / `ambiguous` / `no_candidates`)
  plus the full candidate list, each candidate carrying its own real PDF
  citation. An ambiguous case then shows exactly which page each
  competing candidate came from, not just bare strings.

## Service / API layer

FastAPI app (`webapp/main.py`) opening the store via
`rdflib.Graph(store="Oxigraph")` (verified: existing `reporting/data.py`
logic keeps working against it near-unchanged).

- `GET /api/structure|declarations|documentation|audit` — same shapes as
  Phase 1's report, now live-queried against `current` instead of baked
  into a static file.
- `GET /api/provenance/{subject}/{predicate}` — the RDF-star provenance
  lookup for one fact.
- `GET /api/citations/pdf/{citation_id}.png`, `/api/citations/xsd/{citation_id}`
  — serve the stored citation blobs.
- `GET /api/runs`, `GET /api/runs/{a}/diff/{b}` — run history and diff.
- `POST /api/corrections`, `POST /api/corrections/{id}/approve|reject` —
  the review workflow, through the SHACL-validated write path.
- `GET /api/lineage/{subject}/{predicate}` — a small, focused derivation
  chain for the lineage graph view (source → run → correction → current),
  not the whole corpus.

Reviewer identity: a small configured list of names, picked client-side
and sent as a header on write requests — no password/session system.

## Frontend

React + Vite + TypeScript + Tailwind + shadcn/ui (on Base UI primitives),
built to static assets served by `webapp`.

- **Glance marker**: a small colored `Badge`/dot after each field
  (neutral = XSD-only, blue = PDF-attached, amber = corrected, red =
  stale) — a Base UI `Tooltip` for a one-line hover hint, and a click
  target opening the full panel.
- **Expand panel**: an inline `Collapsible` (never a modal, so scroll
  position in a long list is preserved) showing a `Card` with the source
  type, the real citation (syntax-highlighted XSD fragment, or the actual
  cropped PDF page image, both click-through to the full page/file in a
  `Dialog`), and a relative timestamp (`Tooltip` for the exact ISO time).
- **Track-changes diff**: word-level diff (old struck through, new
  highlighted) inside the same panel when a correction exists; author and
  reason via `HoverCard`; a stale correction gets a destructive-variant
  `Alert`, not just another badge.
- **Lineage graph**: a "View full lineage" link opens a `Sheet`/`Dialog`
  containing a small, focused Cytoscape.js DAG for that one field, styled
  with the same category colors as the glance markers.
- **Corrections worklist**: a sortable/filterable `Table` (Field,
  Proposed value, Proposer, Age, Status, Actions) — Approve/Reject
  disabled when the viewer is the proposer (the maker-checker rule
  enforced visibly, not only server-side), opening a small `Dialog` for
  an optional comment on decision.
- **Page shell**: top-level `Tabs` (Structure / Documentation / Audit /
  Corrections / Runs), a reviewer-identity `Select`, and the existing
  plain-text search `Input`.

## Testing strategy

- `store/`, `provenance/`, `review/`: unit tests against a temp Oxigraph
  store file — named-graph write/read, RDF-star provenance round-trip,
  the verified diff query, SHACL rejecting an invalid write (e.g. a
  self-approval attempt), and the staleness-detection logic against a
  synthetic "value changed between runs" fixture.
- `citations/`: unit tests using the real annex PDF and real XSD fixtures
  already used by `extraction/`'s own tests — assert a real, non-empty
  PNG comes back for a known bounding box, and a known substring appears
  in the captured XSD fragment.
- `webapp/`: FastAPI `TestClient` integration tests per route, against a
  small seeded store.
- `frontend/`: component tests (Vitest + React Testing Library) for the
  glance-marker/expand-panel/diff logic; a Playwright pass against the
  real running app for the same kind of live sanity check Phase 1 already
  used (nav renders, a real citation image loads, approve/reject actually
  changes the worklist).
- One real, whole-corpus run: extract the real MiKaDiv-FM family, load it
  into a fresh store, hit the real API endpoints, confirm sane real data
  and at least one real citation round-trips end to end.

## Definition of Done

- `python -m webapp serve` opens (or creates) the store, runs extraction
  if no runs exist yet, and serves the real MiKaDiv-FM corpus through the
  new frontend.
- Every documentation fact shows a working glance marker and expand
  panel. Every subject with attached English text (any construct, local
  or global) gets a real PDF-crop citation. Every *globally-named*
  construct (a named `complexType`/`simpleType`/global element — 138 of
  377 real documented subjects, confirmed) with German text gets a real
  XSD-fragment citation. The remaining locally-scoped declarations (239
  of 377 — element/attribute declarations nested inside a type) get
  German provenance only as "this run, this file" rather than an exact
  fragment, since recovering their exact source component needs
  `extraction/`'s own internals (which mint their URIs) to track that
  mapping — a real, explicitly scoped-out follow-up, not a silent gap
  (see Plan C's own Task 18 for the confirmed numbers and reasoning).
- A correction can be proposed, approved by a *different* reviewer, and
  is reflected in `current`; a self-approval attempt is rejected; a
  correction whose source value changed in a later run shows as `stale`.
- Diffing two runs shows real added/removed facts.
- `extraction/`'s existing tests are unaffected and still pass unchanged.
