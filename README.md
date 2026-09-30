# OpenFASTER Generator

Part of [OpenFASTER](https://openfaster.org). Built from scratch against
real [`ontologies`](https://github.com/OpenFASTER-Standard/ontologies)
source material (Germany's MiKaDiv-FM regulatory schema: XSDs + BZSt
guidance PDFs) and externally researched prior art -- not built on or
migrating from any prior code in this repo's own history. See
`docs/specs/` for the full design record, one sub-project at a time.

## Layout

- `annotation_model/` -- the current core model: turns a citation of a
  real source span into a W3C Web Annotation + PROV-O + SHACL property
  shape, committed as Turtle to an explicitly-required git-backed target
  store (never a default). Supersedes `reference_model`/
  `references_catalog`/`staleness_sweep` below, which are listed here as
  they exist today but are dead code pending a follow-up migration plan
  -- do not extend them. See
  `docs/specs/2026-09-30-core-semantic-annotation-model-design.md`.
  `annotation_model/transform/` turns a registered `(SPARQL query,
  renderer, min_rows)` transformation into rendered output (Jinja2 text
  or an `openpyxl` workbook) by querying a graph built from the shapes
  above. See
  `docs/specs/2026-09-30-declarative-transformation-design.md`.
- `reference_model/` -- a format-agnostic `Reference` (citation) model:
  records exactly what real source span (an XSD element, a PDF page
  region) backs a fact, precise enough to re-locate later and soundly
  flag when it may have changed. See
  `docs/specs/2026-09-23-source-reference-model-design.md`.
- `staleness_sweep/` -- batches `reference_model`'s own `check_reference()`
  across many `Reference`s at once against the real, snapshot-versioned
  `ontologies` corpus. See `docs/specs/2026-09-23-staleness-sweep-design.md`.
- `review_surfacing/` -- classifies a sweep's results into what a human
  reviewer needs to see first (what's flagged, and what kind of drift).
  See `docs/specs/2026-09-23-review-surfacing-design.md`.
- `review_recording/` -- turns a reviewer's decision into a plain, real
  cited JSON document, through the same `reference_model` machinery
  already built for XSDs and PDFs. See
  `docs/specs/2026-09-23-review-recording-design.md`.
- `review_consultation/` -- consults previously-recorded review decisions
  to suppress drift a human has already approved, scoped to the exact
  fingerprint they reviewed. See
  `docs/specs/2026-09-24-review-consultation-design.md`.
- `references_catalog/` -- reads and writes the references catalog: a
  page (`fact_key`) has an ordered history of immutable revisions. See
  `docs/specs/2026-09-25-catalog-revision-history-design.md`.
- `discovery/` -- mechanically discovers citable candidates in a real
  XSD file, and lists them across the whole corpus. See
  `docs/specs/2026-09-25-xsd-discovery-design.md`.
- `citation_workflow/` -- connects candidate discovery to the catalog:
  turns a human-picked (family, xpath) pair into a fresh, verified
  citation recorded as a new catalog revision. See
  `docs/specs/2026-09-25-citation-workflow-design.md`.
- `review_workflow/` -- orchestrates the review pipeline against the real
  catalog: load current citations, sweep them for drift, filter out
  what's already been reviewed, and record new review decisions back
  onto the catalog. See
  `docs/specs/2026-09-29-webapp-react-rebuild-design.md`.
- `generator_errors/` -- `GeneratorError`, the shared base every domain error in
  this system derives from, so the webapp's HTTP layer can map any of
  them to the right status code uniformly.
- `webapp/` -- serves the catalog as browsable pages with revision
  history, a candidate-browsing + citation-submission interaction layer,
  and the drift-review pipeline, via a React SPA (`webapp/frontend/`)
  backed by six JSON API endpoints. See
  `docs/specs/2026-09-25-catalog-revision-history-design.md`,
  `docs/specs/2026-09-25-citation-workflow-design.md`, and
  `docs/specs/2026-09-29-webapp-react-rebuild-design.md`.
- `alignment/` -- connects a real `annotation_model` property shape to a
  real concept in the separately-governed `institutional-ontology` repo
  via a hand-rolled SSSOM (Simple Standard for Sharing Ontology
  Mappings) reader/validator, so one stored fact can back multiple
  outputs instead of being duplicated per standard. Real mapping data
  lives in `alignments/`. See
  `docs/specs/2026-09-30-alignment-layer-design.md`.

Licensed MIT.
