# PROV-O Extension, Versioning, and Web-Annotation Citation Model — Design

**Supersedes/extends:** Nothing in `2026-09-15-provenance-and-review-platform-design.md`
("Plan A–D") or `2026-09-17-interconnected-provenance-ui-design.md` is reversed here.
Both shipped a working store, review workflow, citation capture, and reverse-lookup
that this document found — reading the real code, not assuming — already implement
most of what a recent research pass (several hours, primary sources verified) set
out to justify from scratch. This document is a **hardening and formalization**
pass: it names the pattern already running in production code in real, standard
terms (PROV-O, the W3C Web Annotation Data Model), fixes the one place the existing
vocabulary usage is not actually standard-conformant, and adds the small amount of
genuinely new plumbing (a `prov:Plan` catalog, per-fact extraction/composition-rule
annotations) that no prior spec scoped. Every file this touches keeps its existing
signatures; new behavior is additive (new optional parameters, new triples, one
backward-compatible predicate migration with dual-read support) — nothing here is a
rewrite.

## Context

The predecessor spec built the store (`store/`), the RDF-star provenance mechanism
(`provenance/record.py`), the maker-checker review workflow (`review/`), and real
inline citations (`citations/`). The interconnected-provenance-ui spec then built a
reverse-lookup direction (`provenance/reverse_lookup.py`) and a `SourceLocator`
abstraction (`citations/locator.py`) on top, explicitly noting that scheme "is
already, in effect, a serialized locator — it needs formalizing into this plugin
shape, not reinventing."

A separate research thread (this document's origin) spent significant effort
evaluating whether that shipped design holds up against real prior art:
OpenLineage was evaluated and rejected as "a pipeline-execution-tracking standard
for batch ETL jobs, wrong genre for 'one fact got corrected'"; PAV was evaluated
and rejected because OpenCitations' real production system (OCDM) achieves full
snapshot-versioning with plain PROV-O; HERITRACE was evaluated as a candidate
off-the-shelf tool and rejected because its `PRIMARY_SOURCE` is "a single global
dataset-level config... wrong granularity for per-fact citation," while several of
its *patterns* (SHACL-driven forms, ORCID-style reviewer identity, `prov:hadPrimarySource`
as the citation predicate) were judged worth reusing conceptually.

Reading the actual code this document is meant to affect turned up something the
research thread could not have known without it: **almost everything that research
concluded should exist already exists**, built independently by Plans A–D and the
interconnected-provenance-ui plan, for the plan's own reasons (a real, live-verified
pyoxigraph limitation, not a hypothetical one). This document is therefore mostly
a *confirmation-and-naming* exercise, with a small number of concrete, scoped
deltas called out explicitly below wherever reality and the research thread
diverged.

## Non-Goals

- **Not a rewrite of `store/runs.py`, `review/corrections.py`, `review/current_view.py`,
  `review/staleness.py`, `citations/pdf_citation.py`, `citations/xsd_citation.py`,
  `citations/locator.py`, or `citations/source_files.py`.** These already implement
  the IC+TSB versioning hybrid and the locator abstraction correctly; this document
  finds zero required changes to any of them (see "Versioning mechanism" and
  "Citation model" below for exactly what was checked).
- **No retroactive rewrite of already-written run/correction graphs.** Per this
  project's own append-only philosophy (already the law of the land in
  `store/runs.py`'s and `review/corrections.py`'s docstrings), a naming or
  predicate change made here applies to *future* writes only; historical data is
  read compatibly, never mutated in place, and never silently reinterpreted.
- **Not adopting PAV, OpenLineage, or any parallel provenance vocabulary.** Confirmed
  in this pass: every real requirement (revision chains, per-fact citation,
  structural runs) is expressible in real PROV-O terms already partially in use.
- **Not building a third citation-source plugin, or wiring any of this into the
  frontend.** The interconnected-provenance-ui spec's `SourcePlugin` registry and
  `Inspector` panel are the right place for a future "why" / extraction-rule display,
  but that is frontend work against a data model this document only lays the
  groundwork for — out of scope here, same layering as Plans A–C (data) vs. Plan D
  (frontend).
- **No `prov:invalidatedAtTime`-driven rewrite of `review/current_view.py`'s
  resolution algorithm.** See "Versioning mechanism" below — this is offered as an
  optional, non-blocking enhancement, not a requirement, because the information it
  would expose is already fully derivable from the existing correction/decision
  chain.

## Vocabulary/data model

**What's already real and stays as-is.** `provenance/vocab.py` and `review/vocab.py`
already keep the boundary this document would otherwise have to invent: real PROV-O
terms (`prov:wasDerivedFrom`, `prov:generatedAtTime`, `prov:wasAttributedTo`,
`prov:wasRevisionOf`) live under the genuine `http://www.w3.org/ns/prov#` namespace,
and this project's own workflow vocabulary (`review:Correction`, `review:Decision`,
`review:status`, `review:decides`, `review:targetSubject`, etc.) correctly lives
under a project-local `https://purl.openfaster.org/review/` namespace instead of
being crammed into `prov:`. `review/corrections.py` already types `review:Correction`
and `review:Decision` resources and attributes them via `prov:wasAttributedTo`/
`prov:generatedAtTime` — i.e., they are already, informally, PROV-O Activities; they
just aren't asserted as `prov:Activity` yet.

**Finding that changes the plan:** `provenance/record.py` mints
`prov:hasProvenanceRecord` as the RDF-star link predicate
(`<< s p o >> prov:hasProvenanceRecord <record>`). **This is not a real PROV-O term.**
PROV-O has no `hasProvenanceRecord` property at all — this project invented it but,
unlike `review:*`, minted it directly under the real `prov:` namespace URI. Any
consumer that treats `prov:` as "real, standard PROV-O" (a strict validator, an
external tool) would see an unknown property in a known namespace, which is worse
than a project-local term would have been. This is exactly the kind of drift the
research thread was worried about in the abstract (parallel-vocabulary risk) and it
already happened, in miniature, in shipped code.

Given the Non-Goal above (no retroactive rewrite of already-written graphs) and
given this predicate is internal wiring rather than anything ever surfaced to an
external consumer (`GET /api/provenance` never exposes the raw predicate, only
`sourceUri`/`generatedAt` JSON keys), the recommendation is **not** to rename it.
Instead:

- `provenance/vocab.py`'s docstring gains one explicit sentence documenting that
  `prov:hasProvenanceRecord` is a project-local invention living (for historical,
  now-frozen reasons) under the real PROV-O namespace URI, not an actual PROV-O
  term — so nobody mistakes it for standard vocabulary later.
- The two **new** predicates this document introduces (extraction/composition
  rules, see below) do **not** repeat this mistake: they get a genuine new
  project-local namespace, `https://purl.openfaster.org/record/` (`REC` in code),
  matching the existing `REVIEW` convention exactly.

**Recommended change (small, mechanical, backward-compatible — a semantic-accuracy
fix, not a naming-hygiene one):** swap the *citation* predicate on a provenance
record from `prov:wasDerivedFrom` to `prov:hadPrimarySource`. Both are real PROV-O
terms; `hadPrimarySource` is the more precise one for "this fact's real, external,
citable source" (a sub-property of `wasDerivedFrom` in the PROV-O spec itself), and
it is the literal, named recommendation from the HERITRACE-pattern research
("`prov:hadPrimarySource` as the citation predicate"). Concretely:

- `provenance/record.py::attach_provenance` writes `prov:hadPrimarySource` instead
  of `prov:wasDerivedFrom` in its `DELETE`/`WHERE` and `INSERT DATA` blocks, for
  *new* writes only.
- `provenance/record.py::get_provenance` and `provenance/reverse_lookup.py::find_facts_by_locator`
  both read via a SPARQL property-path alternation,
  `?record (prov:hadPrimarySource|prov:wasDerivedFrom) ?src`, so historical run
  graphs (written under Plans A–C, already on disk, never mutated) keep resolving
  correctly forever. This is the same "accept either shape, prefer the current one"
  idiom `webapp/routes_provenance.py::get_provenance_route` already uses for the
  untagged-vs-`lang="de"` literal fallback — not a new pattern for this codebase.

**New PROV-O typing (additive triples only, no shape change):**

- `store/runs.py::write_run` adds one triple: `<run-graph-uri> a prov:Activity .`
  on the run's own index subject, alongside its existing `RUNS.runId`/`RUNS.createdAt`
  etc. triples. A run already *is* a PROV-O Activity in every way that matters
  (it has a `generatedAtTime`-equivalent in `RUNS.createdAt` and produces entities);
  it just wasn't asserted as one.
- `review/corrections.py`'s two check-graph builders (`propose_correction`'s own
  `check` graph, and `_write_decision`'s `check` graph) each add one triple —
  `<correction-uri> a prov:Activity .` and `<decision-uri> a prov:Activity .`
  respectively — alongside their existing `RDF.type` triples. Verified against
  `review/validate.py`'s own stated scope and `_write_decision`'s explicit comment
  about *not* typing `correction_uri` as `review:Correction` inside that function's
  minimal check graph (to avoid accidentally re-triggering `CorrectionShape`'s
  target-class validation against a partial subgraph): adding an *extra* type
  triple never removes an existing `sh:targetClass` match and no shape in
  `review/shapes.ttl` targets `prov:Activity`, so this is safe by construction, not
  by luck — confirmed by reading `review/shapes.ttl` in full; no new shape is
  needed.
- `provenance/record.py::attach_provenance` adds `<record> a prov:Entity .` once
  (inserted the same "insert only if not already present" way the RDF-star link
  triple already is — see "Versioning mechanism" below for why that idiom exists).
  The `_record_uri` record resource is, precisely, the PROV-O Entity for "this
  fact's tracked value" — it was already structurally an Entity, again just not
  asserted as one.

**New PROV-O modeling: `prov:Plan` via qualified `prov:Association`.** This is
genuinely new — no existing file models "the stable recurring process that
produced this value" at all today. `provenance/plans.ttl` (new, hand-authored,
same format/loading convention as `review/shapes.ttl`) defines a small, fixed
catalog of `prov:Plan` resources, e.g.:

```turtle
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix plan: <https://purl.openfaster.org/plan/> .

plan:native-xsd-german-documentation a prov:Plan ;
    rdfs:label "Copy xs:documentation (no xml:lang, or xml:lang='de') verbatim from the native XSD element." .

plan:pdf-name-match-english-documentation a prov:Plan ;
    rdfs:label "Match the construct's name against the annex PDF's name column; copy the matched row's English text verbatim." .
```

Unlike `review/shapes.ttl` (read straight off disk by `pyshacl`, never loaded into
the dataset), these *are* real facts about the world that other triples need to
point at and a UI needs to resolve by URI — so a new, small `provenance/plans.py::ensure_plans_loaded(dataset)`
loads `plans.ttl` into a fixed `graph:plans` named graph once at startup
(`webapp/main.py`'s existing store-open step). Because `plans.ttl` contains only
ordinary triples (no RDF-star), this load is trivially idempotent under plain RDF
set semantics — no `FILTER NOT EXISTS` dance needed here, unlike the RDF-star link
in `attach_provenance` (see next section for exactly why that one *does* need it).

`attach_provenance` gains one new optional parameter, `plan: URIRef | None = None`
(default `None` — every existing call site in `webapp/pipeline.py` keeps working
completely unchanged). When provided, it mints a deterministic per-run-per-plan
Activity URI (same SHA-256-of-canonical-N3 pattern as `_record_uri`, keyed on
`(graph_uri, plan)` this time) and writes, once:

```turtle
:activity-<hash> a prov:Activity ;
    prov:qualifiedAssociation [
        a prov:Association ;
        prov:hadPlan plan:native-xsd-german-documentation ;
        prov:agent :extraction-pipeline ;
    ] .

<record> prov:wasGeneratedBy :activity-<hash> .
```

using a qualified `prov:Association` deliberately, not a direct `Activity →
prov:hadPlan → Plan` shortcut — `prov:hadPlan`'s real domain in PROV-O is
`prov:Association`, not `prov:Activity`, and there is no PROV-O-sanctioned
"simplified" direct property for Plan the way there is for `wasDerivedFrom`/
`wasAttributedTo`. Using the qualified form here is the standards-conformant
choice, matching exactly what the research thread specified.

**Honest scope note, found by reading the actual call sites, not assumed:**
`webapp/pipeline.py`'s two current provenance-attaching functions —
`_attach_english_provenance` (PDF name-match, then verbatim copy of the matched
text) and `_attach_german_provenance` (verbatim copy of the native XSD documentation
text) — are **both pure verbatim copies of a source string**, not extraction
transformations or compositions in any sense that would benefit from a `plan=`
annotation beyond "this text came from this source, unmodified." Neither call
site is changed to pass `plan=` as part of this document's required work; the
`plan=` parameter and `plans.ttl` catalog are shipped as available, tested
infrastructure for the first *real* rule-driven fact this project produces (a
composed/multi-source field, which does not exist yet — see "Extraction/composition
rule representation" below for the same finding applied there), not retrofitted
onto today's two copy-only paths for the sake of having a populated example.

## Versioning mechanism

**Nothing here needs to change.** This section exists to confirm, against the real
code, that the IC+TSB hybrid the research thread wanted to justify is already
exactly what's running:

- **Independent Copies (whole-run granularity):** `store/runs.py::write_run` — one
  immutable named graph per run, confirmed untouched, confirmed still the right
  layer for whole-corpus snapshots. `diff_runs` is the verified `FILTER NOT EXISTS`
  SPARQL pattern, unchanged.
- **Timestamp-Based (per-fact granularity):** `provenance/record.py::attach_provenance`'s
  own docstring and inline comments **already state, from direct, live verification
  against this exact pyoxigraph version**, precisely the constraint the research
  thread cites StarVers/Datomic for: RDF-star triples are never deleted or rewritten
  once inserted (a `DELETE`/`WHERE` template containing an RDF-star pattern is
  rejected outright — "expected GRAPH" — regardless of `GRAPH`-wrapping; re-inserting
  an identical RDF-star triple creates a true duplicate, not a dedup). That is why
  the RDF-star link (`<<s p o>> prov:hasProvenanceRecord <record>`) is written
  exactly once, guarded by `FILTER NOT EXISTS`, while the record resource's *own*
  ordinary metadata triples (`prov:wasDerivedFrom`/`prov:hadPrimarySource`,
  `prov:generatedAtTime`) go through a real `DELETE`/`WHERE` + re-`INSERT`, because
  ordinary (non-quoted) triples don't hit this limitation. **This is precisely the
  IC+TSB pattern OSTRICH validates as legitimate prior art** — mutable metadata
  lives on an ordinary-triple-addressed, stably-identified resource (the
  timestamp-indexed part), while the fact-to-record link itself is quoted-triple,
  append-only (the immutable-once-asserted part). No code change; this section is
  a citation of already-shipped design, not a new requirement.
- **Per-fact revision chains:** `review/corrections.py::propose_correction` already
  writes `prov:wasRevisionOf << s p priorValue >>` as a real RDF-star quoted-triple
  reference to the exact prior value being corrected, append-only, never edited —
  this is the OCDM-style "plain PROV-O achieves full snapshot-versioning, no PAV
  needed" claim, already true in this codebase and already checked by
  `review/staleness.py::is_correction_stale` (which reads that same
  `prov:wasRevisionOf` triple to detect when a later run's raw value has drifted
  out from under an approved correction) and resolved by
  `review/current_view.py::get_current_value`/`materialize_current_graph`.
  `review/corrections.py::_find_pending_corrections`/`propose_correction`'s
  auto-supersession logic (a new pending proposal for the same target rejects
  every existing pending one, `reason="superseded by a newer proposal"`) is
  already exactly the "new proposal supersedes the old one" behavior the
  predecessor spec called for — confirmed present, confirmed tested
  (`tests/review/test_corrections.py`), no gap found.

**Optional, non-blocking enhancement (explicitly not required):** OCDM's real
production pattern also uses `prov:invalidatedAtTime` on a superseded value so
"when did this stop being current" is a directly queryable fact, not something
requiring a join across `graph:corrections`. A small helper,
`provenance/record.py::invalidate_provenance(dataset, graph_uri, subject, predicate,
obj, invalidated_at)`, could write `prov:invalidatedAtTime` on the *prior* value's
record resource (resolved via the same deterministic `_record_uri`) when
`review/corrections.py::_write_decision` records an `outcome="approved"` decision.
This is flagged as optional because the information it exposes is already fully,
correctly derivable today via `review/current_view.py`'s existing
Decision-outcome/timestamp resolution — adding it would only make one specific
query cheaper/more standards-idiomatic, not enable anything new. Consistent with
this project's own stated principle for structural facts ("per-triple provenance
there would be overhead with no real payoff"), the same reasoning applies here:
build it only if/when a concrete consumer (e.g., a future "when did this value
change" timeline view) actually needs the direct query, not speculatively.

## Citation model

**Finding that changes the plan (selector type):** the research thread's
assumption was `TextPositionSelector`/`DataPositionSelector` for PDF citations
(character/byte offsets into extracted text). Reading `citations/pdf_citation.py`
and `citations/locator.py::PdfLocator` directly shows this is wrong for what this
project actually captures: `crop_pdf_page`/`PdfLocator.bbox` is a **spatial
bounding box on a rendered page** (`x0, top, x1, bottom` in PDF page coordinate
space, padded and cropped to a PNG), not a character offset into an extracted text
stream. The correct Web Annotation Data Model mapping for this is a
**`oa:FragmentSelector`** using the W3C Media Fragments URI convention
(`#page=<n>&xywh=<x>,<y>,<w>,<h>`-shaped), not `TextPositionSelector`/
`DataPositionSelector` — those exist specifically for offset-into-text-content
addressing, which this project doesn't do and has no current need to do (no PDF
text-extraction-offset citation exists anywhere in the codebase; `pdfplumber`'s
word-level bounding boxes are exactly what's already used, correctly, as a spatial
citation).

`citations/xsd_citation.py::resolve_xsd_component`'s dotted-qname-plus-`@attr`
addressing scheme (e.g. `{ns}SomeType.LocalElement.@LocalAttribute`) already *is*,
structurally, a restricted XPath-like stepwise descent — the research thread's
`oa:XPathSelector` mapping for this one is correct as originally proposed, and
needs no correction.

**What stays exactly as-is:** `citations/locator.py`'s `PdfLocator`/`XsdLocator`
dataclasses, `locator_to_source_uri`/`source_uri_to_locator`/`locator_lookup_key`,
and the `citation:pdf?...`/`citation:xsd?...` source-URI scheme they serialize —
all confirmed, by the interconnected-provenance-ui spec's own words ("already, in
effect, a serialized locator") and by this pass, to already be the right shape.
This document treats the Web Annotation Data Model purely as the **standards
lineage that validates this already-shipped design**, not as a rewrite target:

| This project's real type | Web Annotation Data Model equivalent |
|---|---|
| `PdfLocator{path, page, bbox}` | `oa:SpecificResource` with `oa:hasSource` = the PDF file, `oa:hasSelector` an `oa:FragmentSelector` (page + `xywh`) |
| `XsdLocator{file, component}` | `oa:SpecificResource` with `oa:hasSource` = the XSD file, `oa:hasSelector` an `oa:XPathSelector` whose value is the existing dotted-qname path |
| `provenance.record.attach_provenance`'s `source_uri` | the annotation's `oa:hasTarget` |
| the provenance record resource itself | the annotation's own asserting resource, attributed via `prov:hadPrimarySource` (see Vocabulary section) |

No new serialization is required to ship this correctly — the equivalence is
documented (in `citations/locator.py`'s module docstring, extended with this
table) so a future consumer that wants a real `oa:Annotation`-shaped JSON body
alongside the existing flat `sourceUri`/`generatedAt` fields has a precise,
correct mapping to implement against, rather than needing to re-derive it. Adding
that serialization endpoint itself is explicitly **not** part of this document's
Definition of Done (see Non-Goals) — it has no concrete consumer yet, and building
it speculatively would repeat the exact mistake this project's own Non-Goals
already warn against ("Not a general-purpose RDF/provenance browser").

## Extraction/composition rule representation

Genuinely new — confirmed by grep across `extraction/`, `webapp/`, `review/`,
`citations/`, `provenance/` that no rule/template/reference-expression
representation exists anywhere today. Two new, project-local (not `prov:`)
predicates under a new `https://purl.openfaster.org/record/` namespace (`REC` in
`provenance/vocab.py`, added alongside the existing `PROV`):

- `rec:hasExtractionRule` — a literal, RML `rml:reference`-style reference
  expression (e.g. `"xs:documentation[not(@xml:lang) or @xml:lang='de']/text()"`),
  for a fact pulled directly from one source location by a fixed, describable
  path/query.
- `rec:hasCompositionRule` — a literal, Altova MapForce/Informatica-style template
  expression (e.g. `"{documentedCount}/{totalCount}"`), for a fact built by
  combining two or more source values.
- **Neither predicate is written for a pure verbatim copy.** An undecorated
  record — no rule triple at all — is the honest signal for "this value is an
  exact copy of its cited source, nothing was extracted or composed," matching
  the Altova MapForce/Informatica convention named in the research and, more
  importantly, matching this project's own already-established Non-Goal ethos
  ("No fabricated confidence scores... there is no real continuous signal to
  attach a number to") — inventing an "identity" rule label where none is honestly
  needed would be the same category of mistake in reverse.

`provenance/record.py::attach_provenance` gains two more optional parameters,
`extraction_rule: str | None = None` and `composition_rule: str | None = None`
(both default `None`; existing call sites unaffected). When either is present, it
is written as an ordinary triple on the record resource, through the exact same
`DELETE`/`WHERE`-then-`INSERT` idiom already used for `generatedAtTime` — the
function's own docstring already states the governing rule this satisfies
("Any mutable metadata must live on ordinary triples about a separate,
stably-identified resource"), so this is a direct application of an existing rule,
not a new one.

**Honest scope note (same finding as above, applied here):** as confirmed while
reading `webapp/pipeline.py`, neither of today's two real provenance-attaching
functions has a genuine extraction/composition case to describe — both are
verbatim copies. The predecessor spec's own Context section mentions "an
unexplained-looking audit number split" as a Phase-1 motivation; reading
`reporting/data.py::build_audit` directly confirms this was a **display-formatting
concern in the Phase 1 static report**, not a multi-source composed RDF fact —
there is no composed field in the graph today that `rec:hasCompositionRule` would
attach to. This document ships the capability (predicate, parameter,
`REC` namespace) because a concrete future consumer already exists in spec form
(the interconnected-provenance-ui design's Living Text/Inspector "why" surface,
which today shows source + PDF-matcher decision category but nothing about
derivation mechanism) — but zero call sites populate either predicate as part of
this document's own Definition of Done. This is stated explicitly rather than
silently building unused plumbing without saying so, matching this project's
established convention (e.g., the interconnected-provenance-ui spec's own "Known
gaps carried into this design" section) of naming a real, deliberate scope
boundary instead of quietly leaving a gap or overclaiming completeness.

## Service / API layer

No route signatures change. `webapp/routes_provenance.py::get_provenance_route`'s
JSON contract (`{"sourceUri": ..., "generatedAt": ...}`) is unchanged — the
`prov:hadPrimarySource` migration is entirely internal to how `get_provenance`
resolves that dict, invisible to callers. `webapp/routes_provenance.py::get_xsd_citation`/
`get_pdf_citation` are unaffected (they never touch `attach_provenance`'s new
optional parameters). `webapp/pipeline.py::run_pipeline_and_store` is unaffected by
default (new parameters are opt-in); it is the future call site for `plan=`/
`extraction_rule=`/`composition_rule=` once a real rule-driven fact exists, per the
scope notes above.

`webapp/main.py`'s startup gains one line: `provenance.plans.ensure_plans_loaded(dataset)`,
alongside its existing store-open step — the only genuinely new startup behavior
in this document.

## Migration path

Explicit file-by-file summary:

**Touched, additive only (no existing behavior changes, only new optional
capability):**
- `provenance/vocab.py` — add `REC = Namespace("https://purl.openfaster.org/record/")`;
  extend the module docstring to document that `prov:hasProvenanceRecord` is a
  known, frozen, non-standard term (not renamed — see Vocabulary section).
- `provenance/record.py` — `attach_provenance` gains `plan`, `extraction_rule`,
  `composition_rule` (all `Optional`, default `None`); the citation predicate
  changes from `prov:wasDerivedFrom` to `prov:hadPrimarySource` for new writes;
  `<record> a prov:Entity` is added once; `get_provenance` reads via a
  `hadPrimarySource|wasDerivedFrom` property-path fallback.
- `provenance/reverse_lookup.py::find_facts_by_locator` — same property-path
  fallback for the source-predicate read.
- `store/runs.py::write_run` — adds one `RDF.type PROV.Activity` triple to the
  run's index subject.
- `review/corrections.py` — `propose_correction`'s and `_write_decision`'s check
  graphs each add one `RDF.type PROV.Activity` triple.
- `citations/locator.py` — module docstring extended with the Web Annotation
  equivalence table; no code/behavior change.
- `webapp/main.py` — one new startup call to load `provenance/plans.ttl`.

**New files:**
- `provenance/plans.ttl` — the hand-authored `prov:Plan` catalog.
- `provenance/plans.py` — `ensure_plans_loaded(dataset)`, mirroring
  `review/validate.py::load_shapes`'s file-loading convention but inserting into a
  real `graph:plans` named graph rather than staying disk-resident.

**Completely untouched (verified, not assumed):** `store/database.py`,
`store/stats.py`, `review/current_view.py`, `review/staleness.py`,
`review/shapes.ttl`, `review/validate.py`, `citations/pdf_citation.py`,
`citations/xsd_citation.py`, `citations/source_files.py`,
`webapp/routes_corrections.py`, `webapp/routes_runs.py`,
`webapp/routes_structure.py`, `webapp/routes_sources.py`, `webapp/errors.py`,
all of `extraction/`, all of `reporting/`, and the entire `frontend/` tree.

## Testing strategy

- `tests/provenance/` — extend existing `attach_provenance`/`get_provenance`
  round-trip tests with cases for the new optional `plan`/`extraction_rule`/
  `composition_rule` parameters (present and absent), and a regression test
  confirming a fact whose record resource was written with the *old*
  `prov:wasDerivedFrom` predicate (simulating a pre-migration run graph) still
  resolves correctly through the new property-path read.
- `tests/provenance/` (new) — `ensure_plans_loaded` is idempotent (calling it
  twice produces no duplicate triples — trivially true for ordinary triples, but
  asserted directly rather than assumed) and every `plan:` URI in `plans.ttl`
  resolves to a real `prov:Plan`-typed resource with a non-empty `rdfs:label`
  once loaded.
- `tests/store/test_runs.py` — extend to assert the new `PROV.Activity` type
  triple on a freshly written run's index subject.
- `tests/review/test_corrections.py` — extend to assert the new `PROV.Activity`
  type triple on both `review:Correction` and `review:Decision` resources, and
  confirm SHACL validation still passes unchanged (i.e., the extra type triple
  doesn't trip `CorrectionShape`/`DecisionShape`) — a direct regression test for
  the exact risk flagged in the Vocabulary section.
- `tests/webapp/test_routes_provenance.py` — confirm the JSON response shape is
  byte-for-byte unchanged for a fact recorded under the new predicate.
- One real, whole-corpus run (this project's existing convention, per the
  predecessor spec's own Testing strategy) confirming the new triples appear
  correctly against the real MiKaDiv-FM corpus, not just synthetic fixtures.

## Definition of Done

- `prov:hasProvenanceRecord`'s non-standard status is documented, not silently
  left ambiguous; no code claims it is real PROV-O.
- New provenance records use `prov:hadPrimarySource`; old records (real, already
  on disk, unmutated) still resolve through every existing read path.
- Runs, Corrections, and Decisions are all now explicitly typed `prov:Activity`
  in addition to their existing project-local types, verified not to disturb any
  existing SHACL validation.
- Provenance records are explicitly typed `prov:Entity`.
- A real, loaded `prov:Plan` catalog exists (`graph:plans`), reachable via
  `prov:qualifiedAssociation`/`prov:hadPlan` from an opt-in per-run Activity, with
  zero required call-site changes to today's two (verbatim-copy) provenance paths.
- `rec:hasExtractionRule`/`rec:hasCompositionRule` exist as real, tested, optional
  capabilities on `attach_provenance`, explicitly unpopulated by any current call
  site — a stated, deliberate scope boundary, not a silent gap.
- The Web Annotation Data Model equivalence for `PdfLocator`/`XsdLocator` is
  documented with the corrected selector type (`FragmentSelector`, not
  `TextPositionSelector`/`DataPositionSelector`), with zero changes to
  `citations/locator.py`'s actual code.
- Every file listed as "completely untouched" above has zero diff.
- `extraction/`'s and the frontend's existing tests are unaffected and still pass
  unchanged.
