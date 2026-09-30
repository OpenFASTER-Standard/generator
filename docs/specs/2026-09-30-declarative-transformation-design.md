# Declarative Transformation Layer — Design

## Summary

A pure, stateless mechanism for turning the annotated RDF graph produced
by the core semantic annotation model (roadmap task 1) into a real
output document — Bikeshed specification markup, an Excel workbook, or
any future output kind — by querying the graph with SPARQL and handing
the results to a registered renderer. This is what lets
`openfaster-spec`'s current hand-written Python Bikeshed/Excel
generators become genuine generated projections of the same annotated
model, rather than a separate, disconnected pipeline.

## Context

This is roadmap task 2, depending on task 1
(`docs/specs/2026-09-30-core-semantic-annotation-model-design.md`,
implemented as the `annotation_model` package). Per this project's
standing rule, nothing here is grounded in what already exists in this
org's code — only in the real annotated-graph interface task 1 actually
produces, and in genuine external prior art.

Two pieces of prior art named during the original 2026-09-30 vision
brainstorm — RML and XSLT — are deliberately **not** used here, on
inspection rather than by default inclusion:

- **RML**'s real job is source-format → RDF (a CSV or XML document
  becoming graph data). That is the opposite direction from what this
  task does, and belongs to task 1's selector registry as a future
  extension (a third selector type, alongside XPath/SVG), not to this
  task.
- **XSLT** is XML-to-XML. Once the canonical representation is RDF/Turtle,
  there is no clean role for it — running XSLT against an RDF/XML
  serialization is a real but awkward, rarely-used path with no natural
  fit here. SPARQL against the graph directly replaces its role for this
  task's purposes.

Two items from task 2's own `task-master` entry — JSON Schema output and
a caching layer — are **not** part of this spec. Both were invented by
`add-task`'s own AI elaboration and never actually agreed; the real,
agreed scope (task-master's concise title/description) names only
Bikeshed and Excel. Caching is also explicitly deferred as premature
optimization with no evidence of a real performance problem yet.

## Core Concepts

### A transformation is `(name, SPARQL SELECT query, renderer, min_rows)`

Registered by name, the same idiom `annotation_model`'s own selector
registry already uses (one resolver per selector type; here, one
renderer per output kind) — adding a new output kind later never touches
an existing one.

- **The query** is always a SPARQL SELECT (not CONSTRUCT) against an
  `rdflib.Graph` — this task turns graph data into human-readable
  documents, not into more RDF. (CONSTRUCT's place is the later
  alignment layer, roadmap task 4, which does produce derived RDF.)
- **The renderer** is one of two kinds, matching what the two named
  outputs actually need:
  - **Text renderer**: the query's result rows are passed to a Jinja2
    template, producing rendered text (Bikeshed markup). Real,
    well-established prior art for exactly "graph → SPARQL-driven
    template → generated documentation": **WIDOCO**, which
    `institutional-ontology`'s own README already names as the tool
    generating its PURL term-redirect docs. Same pattern, different
    output format.
  - **Workbook renderer**: the query's result rows are passed to a plain
    Python function that builds an `openpyxl` workbook directly — there
    is no meaningful "template" for a spreadsheet the way there is for
    text, so forcing this through Jinja2 would be the wrong abstraction.
    `openfaster-spec`'s existing hand-written generator already uses
    `openpyxl` for this; only the data source changes (a SPARQL query
    against the graph, not XSD-derived Python structures).
- **`min_rows`** (default `1`) declares whether an empty result is an
  error for this specific transformation. Most transformations in this
  domain should error on zero rows (a query for "the schema's data
  dictionary" coming back empty means the query or the underlying shape
  is broken) — but some are legitimately allowed to be empty (e.g. "all
  deprecated fields in this schema version," for a version that
  deprecated nothing). This is the same per-check-expectation pattern
  real data-pipeline tools (e.g. dbt's per-test expectations) already
  use for exactly this problem, rather than one global rule that's wrong
  for either case some of the time.

### Provenance flows through, never stripped

A SPARQL query can select a value's `prov:wasDerivedFrom` annotation and
original source URI in the same row as the value itself, since both are
already present in the graph per task 1's model. This layer never
discards that information before a renderer gets to use it — whether a
given template chooses to render an inline citation/footnote is up to
that template, not this layer.

## Data Flow

1. Load one or more shapes into a single `rdflib.Graph` (via task 1's
   `TargetStore.read_shape`, merged if more than one shape is needed for
   a given output).
2. Look up a registered transformation by name.
3. Run its SPARQL SELECT query against the graph.
4. If the result has fewer than `min_rows` rows, raise — a query that
   silently returns too little data is worse than a loud failure, for
   this project's domain.
5. Hand the result rows to the transformation's registered renderer
   (Jinja2 template, or the workbook-building Python function).
6. Return the rendered text or workbook object to the caller.

## Error Handling

- A syntactically invalid SPARQL query fails immediately with a clear
  error naming the transformation, not a bare rdflib parse exception.
- Fewer than `min_rows` result rows raises a specific, named error (not
  a silent empty output) — see `min_rows` above.
- A renderer (template or Python function) that itself raises during
  rendering propagates with the transformation's name attached, so a
  failure in a specific named transformation is never confused with a
  failure in the query step.

## Testing Strategy

- **Round-trip, real data**: register a real transformation against a
  real shape produced by task 1's own tests (not a synthetic graph),
  confirm the rendered Bikeshed text / Excel workbook contains the real
  expected values.
- **`min_rows` enforcement**: a query returning fewer rows than
  `min_rows` raises; a transformation explicitly declaring `min_rows=0`
  accepts a genuinely empty result without raising.
- **Provenance is queryable**: a query that selects a value's
  `prov:wasDerivedFrom`/source URI alongside the value itself gets both
  in the same row — proving this layer doesn't strip provenance before a
  renderer can use it.
- **Renderer isolation**: a renderer that raises produces an error
  naming its transformation, distinguishable from a query-stage failure.

## Non-Goals

- Ingesting a new source format (e.g. a bank's CSV) into RDF — task 1's
  concern, a future selector type, not this task.
- Cross-standard alignment / SSSOM mappings (roadmap task 4).
- Stateful, multi-step process modeling (roadmap task 5) — this layer is
  and remains purely stateless, one query-and-render pass per call.
- JSON Schema output and any caching layer — not part of the actually
  agreed scope (see Context).

## Open Questions

- The exact SPARQL query files' storage location/naming convention
  (alongside each transformation's renderer, presumably) is an
  implementation-planning detail, not resolved here.
- Whether transformations themselves should live in a git-backed store
  the way task 1's shapes do (so a bank could register its own private
  transformation the same way it annotates its own private shapes) is a
  real question this spec doesn't resolve — deferred until the
  Wikipedia-like collaborative platform (roadmap task 6) needs an answer.
