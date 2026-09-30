# Task ID: 4

**Title:** Design and implement alignment layer (SSSOM-based real-world concept mapping)

**Status:** done

**Dependencies:** 1 ✓, 2 ✓

**Priority:** medium

**Description:** Connect one real, already-citable generator property shape to a real concept in the separately-governed institutional-ontology repo via a real, hand-rolled SSSOM (Simple Standard for Sharing Ontology Mappings) mapping -- no sssom-py, no parallel concept vocabulary -- and prove that two different, unmodified task-2 transformation renderers can resolve the same underlying fact through the mapping instead of a hardcoded standard-specific predicate.

**Details:**

## Reconciliation note (2026-09-30)

This task's `description`/`details`/`testStrategy` originally came from
task-master's own AI auto-elaboration at task-creation time, before the
real design spec existed -- the same situation task 3 was in before its
own reconciliation (see that task's own Reconciliation note). The
auto-elaboration proposed a much larger and differently-shaped project
than what the approved spec scoped and what was actually built: a brand
new `generator/ontologies/core/*.ttl` vocabulary (Person, Organization,
FinancialAccount, ~20 properties) duplicating a real, already-governed
sibling repo instead of using it; the `sssom-py` library (pandas/linkml
dependency chain); ROBOT-based ontology validation; a
`AlignmentAwareSparqlEngine` subclass; webapp endpoints and a CLI tool
for mapping management; a round-trip "generate a schema-valid MiKaDiv-FM
XML filing from core data, validate against the official XSD" pipeline;
and a `>=50`-mapping MVP set covering "one complete filing type".

None of that was built, and per this project's own review process
(the branch's final review, findings recorded in the plan's own
execution ledger before it was deleted) leaving it here as the recorded
Definition of Done would give a future reader a materially false
picture of what exists. The section below replaces it with what the
approved spec
(`docs/specs/2026-09-30-alignment-layer-design.md`) actually scoped and
what was actually shipped.

## What this task actually built

One repository (`generator`), one new top-level package (`alignment/`),
one real committed mapping.

### The key architectural decision: depend on institutional-ontology, don't duplicate it

`/work/institutional-ontology` (OpenFASTER-Standard org, a separate,
already-real, already-governed repo) is a real BFO/IAO/SSSOM ontology
built explicitly "to give independent schemas a shared, stable set of
things to point at instead of re-deriving equivalence between them
pairwise" (that repo's own README) -- exactly what this task needed.
Rather than invent a parallel `generator/ontologies/core/` vocabulary
(the original auto-elaboration's proposal), this task's alignment layer
maps generator's own property-shape IRIs directly to that repo's real,
already-published concepts (e.g. `IO:0000001`, "All given names").
Curating a *new* concept that doesn't exist yet in institutional-ontology
is explicitly out of this task's scope -- that repo's own careful
curation process (real BFO/IAO subclassing, citation-backed editor
notes, `robot verify`) owns that.

### `alignment/sssom.py`

`Mapping` (a `kw_only` frozen dataclass: `subject_id`, `predicate_id`,
`object_id`, `mapping_justification` required; `subject_label`,
`object_label`, `confidence`, `author_id` optional, matching the real
SSSOM schema's own required-slot set, verified live against the actual
`sssom-schema` 1.1.0a5 package rather than assumed).
`load_sssom_mappings(path) -> list[Mapping]` parses a real SSSOM TSV
file: a `#`-prefixed YAML-comment header (`curie_map`, `mapping_set_id`,
`license`), then a tab-delimited body, with real per-line error
locations and SSSOM's real built-in CURIE prefixes (`sssom`/`owl`/`rdf`/
`rdfs`/`skos`/`semapv`) recognized without needing to be redeclared.
`load_sssom_header(path) -> dict[str, str]` exposes the header metadata
separately. `mappings_to_graph(mappings) -> Graph` mints one real triple
per mapping (`subject skos:predicate object`) -- SSSOM's own documented
"simple" RDF serialization, not reified; deliberately drops
confidence/justification/author from the RDF graph itself (they remain
fully available from `load_sssom_mappings`'s own return value) per the
spec's own Open Questions, deferred until a subject has more than one
candidate mapping to arbitrate between.

No `sssom-py` (real PyPI package verified live, `pandas`/`linkml`/
`linkml-runtime` dependency chain judged disproportionate to reading a
handful of TSV rows -- the same reasoning task 2 already used rejecting
RML in favor of plain SPARQL+Jinja2).

### `alignment/institutional_ontology.py`

Mirrors `tests/corpus_fixtures.py`'s already-established "real data
lives in a sibling repo that might not be checked out" pattern exactly:
`institutional_ontology_path()` reads `INSTITUTIONAL_ONTOLOGY_PATH` at
call time (default: `/work/institutional-ontology/institutional-ontology.owl`,
that repo's own committed release artifact), `load_institutional_ontology()`
parses the real RDF/XML file, and `tests/alignment/fixtures.py`'s
`requires_real_institutional_ontology` skips cleanly (including for a
0-byte/interrupted checkout, not just a missing file) rather than
failing opaquely when that sibling repo isn't present.

### `alignment/validate.py`

`validate_mappings(mappings, *, generator_graph, institutional_graph)`
raises `UnresolvedSubjectError` if a mapping's subject doesn't name a
real `sh:PropertyShape` in the generator graph, `UnresolvedObjectError`
if its object doesn't name a real `owl:Class`/`owl:NamedIndividual` in
the institutional-ontology graph (collecting every bad mapping of each
kind, not just the first), and `EmptyInstitutionalGraphError` if the
institutional graph has no relevant triples at all (distinguishing "you
forgot to load it" from "this concept genuinely doesn't exist").
`load_and_validate_mappings(path, *, generator_graph,
institutional_graph)` composes load -> validate in one call -- the real
pipeline the spec describes, and the one a future task should copy.

### `alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv`

One real, committed mapping: generator's real
`MiKaDiv_FM_Personentypen_1.02.xsd` `Vorname` attribute (cited via task
1's existing `annotate_xpath()`, `standard="MiKaDiv-FM Personentypen"`,
`shape_name="PersonentypenFields"`, `property_name="Vorname"`)
`skos:exactMatch` institutional-ontology's real `IO:0000001` ("All given
names") -- the same real concept that repo's own editor notes already
document as `exactMatch` to MiKaDiv-VIB's `FirstName` and KaFE's
`Vorname`, for two sibling standards. `semapv:ManualMappingCuration`,
confidence `0.95`.

### The end-to-end proof

`tests/alignment/test_end_to_end.py`: cites the real Vorname field,
loads+validates+graphs the real mapping via `load_and_validate_mappings`
+ `mappings_to_graph`, then registers two `Transformation` instances of
two of task 2's existing renderer *kinds* (a `jinja_text_renderer` text
renderer and an `openpyxl` workbook renderer -- both real, already
demonstrated in `tests/annotation_model/transform/test_renderers.py`,
neither modified by this task) whose SPARQL query traverses through
`IO:0000001` rather than the generator-specific `Vorname` predicate
directly. Both renderers independently produce the real cited value --
proving "one stored fact populates multiple outputs without
duplication" with real data, using the real constraint that only one
standard (MiKaDiv-FM) has real annotated content in generator today (so
"multiple outputs" means two different task-2 output *kinds* from one
standard's data, not two different standards -- true cross-standard
proof is a Non-Goal below, waiting on a second standard actually being
annotated).

## Non-Goals (unchanged from the approved spec, still true of what shipped)

- New institutional-ontology concepts -- that repo's own curation
  process owns this, not this task.
- A second real generator-annotated standard, and therefore true
  cross-*standard* alignment proof (`mikadiv-vib`/`kafe` under
  `/work/ontologies` are empty stubs with no real annotated content) --
  a task-1-shaped prerequisite, not this task's job.
- A webapp mapping-management UI or a CLI tool -- nobody has asked for
  either yet.
- Any XML write-back/round-trip generation (a schema-valid regulatory
  filing generated from "core data" and validated against the official
  XSD) -- nothing in this codebase does this anywhere; task 2's
  transformation layer only ever renders read-only text documents.
  Inventing this capability is a separate, much larger task.
- `sssom-py`, ROBOT, or any ontology-reasoning dependency.
- Automatic/ML-based mapping inference -- every mapping is
  human-curated (`semapv:ManualMappingCuration`), matching
  institutional-ontology's own real practice.

**Test Strategy:**

## Verification strategy (what was actually run, matching the approved spec's Testing Strategy)

- **Real shapes, real ontology, not synthetic fixtures**
  (`tests/alignment/test_validate.py`, `tests/alignment/test_real_mapping_file.py`,
  `tests/alignment/test_end_to_end.py`): every test that needs a
  property shape cites one for real via `annotate_xpath()` against the
  real `MiKaDiv_FM_Personentypen_1.02.xsd`; every test that needs
  institutional-ontology content loads the real, separately checked-out
  `institutional-ontology.owl`, skipping cleanly via
  `requires_real_institutional_ontology` when that sibling repo (or a
  real, non-empty copy of it) isn't present.
- **SSSOM parsing robustness** (`tests/alignment/test_sssom.py`, 15
  tests): real curie_map expansion (including SSSOM's real built-in
  prefixes, verified against the actual `sssom-schema` package); a
  malformed confidence value, a short/long row, a malformed curie_map
  entry, an empty file, a header-only file, and a missing column-header
  row all raise a named `SssomParseError` with the real file and line
  number, never a bare `csv`/`KeyError`/`ValueError`/`TypeError`
  traceback; optional SSSOM columns may be omitted; a real file with
  MORE columns than the 8 this module reads still parses correctly.
- **Referential-integrity validation** (`tests/alignment/test_validate.py`,
  6 tests): a real valid mapping passes; a bad subject and a bad object
  are independently, provably tested (not just "whichever check happens
  to run first"); multiple bad subjects/objects are all reported
  together, not just the first; an empty institutional_graph raises a
  distinct error from a genuinely-unresolved concept.
- **The real committed mapping** (`tests/alignment/test_real_mapping_file.py`,
  2 tests): loads to exactly the one expected `Mapping`; validates
  cleanly against the real generator graph (after citing Vorname) and
  the real institutional-ontology graph.
- **The actual deliverable, proven end-to-end**
  (`tests/alignment/test_end_to_end.py`, 1 test): one real citation, one
  real validated mapping, two different *unmodified* task-2
  `Transformation` renderer kinds each resolving the same underlying
  fact through `IO:0000001` -- verified live (per the plan's own
  execution ledger) that repointing the query at a nonexistent concept
  makes both renderers fail with `TransformationError` ("0 rows"),
  proving the test genuinely depends on the alignment triple rather than
  passing for free.
- **Cross-cwd correctness**: the real mapping file's path is derived
  from each test file's own location (`Path(__file__).resolve().parents[2]`),
  not the working directory -- verified live from both the repo root and
  `tests/` as cwd.
- **Fresh-review verification**: a final whole-branch review (fresh
  Opus reviewer) found 0 Critical, 7 Important, 10 Minor findings, all
  fixed in the same pass per this project's standing rule (never defer
  Minors) -- full suite 349/349 passing after the fix pass, up from
  16 new regression tests added during that pass alone.

## Explicitly not run (out of scope, not a gap)

- No Storybook/webapp/CLI verification -- none of these exist for this
  task (Non-Goal).
- No schema-valid-XML-generation/round-trip test -- that capability
  doesn't exist anywhere in this codebase (Non-Goal).
- No cross-*standard* (as opposed to cross-*output*) proof -- no second
  real generator-annotated standard exists yet (Non-Goal, real
  prerequisite gap, not an oversight).
- No `sssom-py`/ROBOT-based validation -- deliberately not a dependency
  of this task.

## Definition of Done (replaces the original, met in full)

- `load_sssom_mappings()`/`load_sssom_header()` correctly parse a real
  SSSOM TSV, including every malformed-input case named in the spec's
  Error Handling section, with real file+line context on every failure.
- `validate_mappings()`/`load_and_validate_mappings()` correctly
  distinguish an unresolved subject, an unresolved object, and an
  unloaded institutional graph, collecting every failure of each kind.
- One real, committed SSSOM mapping connects a real generator property
  shape to a real institutional-ontology concept and validates cleanly.
- Two different, unmodified task-2 transformation renderer kinds
  resolve the same real cited fact through the alignment, proven live
  (not merely asserted) to depend on the alignment triple.
- Full test suite green (`pytest`, 349/349) confirmed after every
  final-review fix, not just once at task completion.
- README.md's own package-layout section and the task-master record
  itself (this document) accurately describe what was built, not
  task-master's own pre-spec auto-elaboration.
