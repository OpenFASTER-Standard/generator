# Core Semantic Annotation Model — Design

## Summary

`generator` becomes a tool for annotating any ground-truth source document
(an XSD, a PDF, a statute, an arbitrary process description) with a formal,
standards-based RDF representation of what that source actually says —
precise enough to re-locate the exact span later and flag when it may have
changed. This spec covers only that core model (OpenFASTER roadmap task 1).
It deliberately does not cover declarative transformation, UI generation,
the cross-standard alignment layer, stateful process modeling, the
collaborative public/private platform, or personal/institutional data
storage — those are separate, later specs (roadmap tasks 2–7, tracked in
`.taskmaster/tasks/tasks.json`), each depending on this one.

## Context

This supersedes the existing `reference_model`/`references_catalog`/
`staleness_sweep` machinery built earlier in this repo's history, and
treats every existing repo in the OpenFASTER org — `generator`, `ui`,
`ontologies`, `institutional-ontology`, `openfaster-spec` — as open to
reconsideration on its technical merits, not as prior architecture to
extend. Nothing here is grounded in what already exists in this org;
it's grounded in (a) the real source materials this system annotates and
(b) genuine external prior art for the problems involved, per this
project's standing rule that there is no "existing codebase" to anchor on.

The wider vision (recorded in this session's brainstorm, not yet its own
spec) is that annotating ground-truth sources should let downstream
artifacts — UI, transformations, documentation, eventually business
logic — be generated projections of the annotation, rather than
hand-built per consumer. This spec's job is only to get the annotation
itself right; every generation mechanism is out of scope here.

## Core Concepts

Three real, existing W3C-track standards compose to form the model,
chosen specifically so that no part of "point at a source span" or
"record where this came from" is invented from scratch:

### 1. W3C Web Annotation Data Model — citing a source span

An **`oa:Annotation`** (Web Annotation Data Model, W3C Recommendation)
is the unit of "this exact span of this exact source means this." Its
`oa:hasTarget` names the source document and a selector locating the
span within it:

- **`oa:XPathSelector`** for XML/XSD sources — an XPath expression,
  exactly as `XPathSelector` does in the current codebase, just
  expressed as a standard Web Annotation selector rather than a
  bespoke class.
- An **IIIF-style fragment/region selector** for PDF sources — a page
  number plus a bounding region, the standardized equivalent of the
  current bespoke `SvgSelector`.

Real, production-used infrastructure (Hypothesis's annotation tool,
Europeana, IIIF-based digital archives), not bespoke JSON.

### 2. PROV-O — provenance

Every SHACL shape element produced by an annotation carries
**`prov:wasDerivedFrom`**, pointing at the `oa:Annotation` that
justified it. `prov:Entity`/`prov:Activity` give "this shape property
exists because of this annotation, made at this time" a standard,
query-able shape rather than an ad hoc `Revision` dataclass.

### 3. SHACL — the per-standard shape

Each individual standard/regulation/process gets its own
**`sh:NodeShape`** graph (layer 2), built entirely from what that
standard's own source documents say — no cross-standard interpretation
at this layer. Two fields named identically in two different standards
are two different, unconnected `sh:PropertyShape` nodes until an
explicit alignment (a later, separate spec — roadmap task 4) says
otherwise.

### Layer 1 — format-language ontologies

What a source document's *format* structurally is (what XML is, what
XLSX is) is a separate, standard-based concern from what a *specific
standard* requires. Where an existing, externally-grounded formalization
already exists — `ontologies/xsd` models the real XSD 1.1 Schema
Component Model, `ontologies/xml` models real XML document structure —
reusing it is correct, because it formalizes an external ground truth,
not because it predates this spec. Layer 1 is reused where it already
correctly reflects an external standard; it is not exempt from scrutiny
where it doesn't.

## Data Storage Model

**No triple store, no bespoke database.** Every annotation, shape, and
provenance triple is written to git-tracked Turtle files. Git commit
history is the revision/audit history — there is no separate `Revision`/
catalog concept to keep in sync with it.

**No default target, ever.** The tool takes an explicit git-backed data
store (a path or remote) on every invocation. This is not a convenience
default deferred to later — it's load-bearing: the same tool must work
identically for a public regulation and for a bank's own private,
non-public process mapping, and *any* implicit default (including
treating the org's own `ontologies` repo as "the" default) would bias
the tool toward one tenant over another. A public data store (e.g. the
org's `ontologies` repo) and a private one (e.g. a bank's own repo) are
indistinguishable to the tool — same code path, different target.

This also means `generator` itself holds no ground-truth data of its
own. It is pure tool: given a source document and a target store, it
produces correctly-formed, provenance-carrying RDF and commits it to
that store.

**Note, explicitly out of scope for this spec:** whether `ontologies`
should remain one multi-module repo or split into one repo per standard
(matching real OBO Foundry practice, which `institutional-ontology`
already patterns itself on) is a real, open question this spec does not
resolve — it affects how many "target stores" the public side of this
ecosystem actually has, not the tool's design, which is store-count-agnostic
either way.

## Concrete Workflow

1. Admin names a target data store (git path/remote) — required, no default.
2. Admin names a ground-truth source: one the target store already
   tracks, or a fresh one being imported.
3. Admin picks a concrete span in that source via a selector (XPath for
   XML/XSD; page+region for PDF).
4. Admin asserts what that span means: a new or existing SHACL property
   shape.
5. The tool resolves the selector against the real source immediately:
   - **Not found** — selector matches nothing. Blocks annotation creation.
   - **Ambiguous** — selector matches more than one node. Blocks
     annotation creation until narrowed.
   - **Uncitable** — selector resolves to something that can't carry a
     citable value (e.g. an attribute where a full element is expected).
     Blocks annotation creation.
   - **Resolved** — the tool computes a content hash of the resolved
     span, for later drift detection.
6. On success, the `sh:PropertyShape` (or shape reference), its
   `oa:Annotation`, its `prov:wasDerivedFrom` link, and its content hash
   are written as Turtle and committed to the target store.
7. **Drift checking** (run independently, any time): re-resolve every
   existing annotation's selector against the current state of its
   source; a changed hash or a resolution that now fails is flagged for
   review. Functionally the same job the current `staleness_sweep`
   performs, against the new representation.

## Error Handling

- The three resolution failure modes above (not found / ambiguous /
  uncitable) are hard blocks on annotation creation, not warnings — this
  distinction is already proven correct in the current codebase's
  `Status` enum and carries forward unchanged in spirit.
- **XML parsing safety is non-negotiable and must be re-verified, not
  assumed**: every XML resolution path uses a hardened parser
  (`no_network=True`, `load_dtd=False`) — this session already found and
  fixed a real regression here (a naive `resolve_entities=False` blanket
  fix broke legitimate internal-entity documents while still needing
  external-entity blocking), so this is implemented as a shared,
  single, tested parser configuration, not re-derived ad hoc per selector
  type.
- A conflict between two annotations from *different* standards is only
  possible once the alignment layer (a separate, later spec) exists;
  this spec's shapes are per-standard and cannot conflict with each
  other by construction — noted here so the alignment spec inherits the
  requirement that such conflicts are always surfaced, never silently
  resolved.

## Testing Strategy

- **Round-trip, real corpus**: annotate a real span in a real
  MiKaDiv-FM XSD; confirm the resulting Turtle parses as valid RDF and
  the shape validates under `pySHACL`'s own shape-correctness check.
- **Drift detection, real corpus**: mutate a real cited span (rename,
  change content) and confirm re-resolution correctly reports not-found
  or a changed hash. Uses the real corpus per this project's existing
  `requires_real_corpus` discipline — not synthetic-only fixtures.
- **True multi-tenancy**: run two independent target stores side by
  side (standing in for "a public regulation" and "a bank's private
  process") and confirm zero cross-contamination — this is the test
  that actually proves "no default" holds in practice, not just in
  code review.
- **XXE / injection regression**: carry forward, unchanged in intent,
  the existing external-entity-blocked and internal-entity-still-expands
  tests from `test_xpath_selector.py` — the underlying resolution risk
  is identical regardless of which annotation format wraps the selector.

## What This Supersedes

- `reference_model.Reference` and its `Status` enum → an `oa:Annotation`
  with a standard selector; the four-way resolution outcome (resolved /
  not found / ambiguous / uncitable) survives as a concept, re-expressed
  over the new representation.
- `reference_model.selectors.XPathSelector` / `SvgSelector` → `oa:XPathSelector`
  / an IIIF-style region selector.
- `references_catalog`'s JSON catalog and hand-rolled `Revision`/
  `RevisionKind` model → git commit history over Turtle files.
- `staleness_sweep`'s bespoke sweep/report dataclasses → drift checking
  re-resolves `oa:Annotation` selectors and compares hashes directly;
  the same job, no bespoke report schema required.
- `review_surfacing`, `review_recording`, `review_consultation`,
  `citation_workflow`, `discovery`, and the existing `webapp` are all
  built on top of the superseded model above and will need their own
  follow-up redesign once this spec's replacement lands — not
  attempted in this spec, which scopes to the annotation model only.

## Non-Goals (deferred to later specs)

- Declarative transformation of an annotated shape into an output
  document (roadmap task 2).
- Shape-driven UI generation (roadmap task 3).
- Cross-standard alignment / SSSOM mappings (roadmap task 4).
- Stateful, multi-step process modeling (roadmap task 5).
- The Wikipedia-like public/private collaborative annotation platform
  (roadmap task 6).
- Personal/institutional data storage and consent-sharing (roadmap
  task 7 — explicitly deferred by the product owner).

## Open Questions

- Whether `ontologies` should split into one repo per standard (real
  OBO Foundry practice) is unresolved and doesn't block this spec.
- The exact Turtle file/directory layout within a target store (one
  file per shape? per standard? per annotation?) is an implementation
  planning detail, not resolved here.
- Whether `rdflib` + `pySHACL` (matching the existing Python stack) or
  a real triple store (Oxigraph, Apache Jena/Fuseki) is needed is
  deferred until real scale/query-pattern evidence exists — start with
  `rdflib`/`pySHACL`, in-process, no server to run.
