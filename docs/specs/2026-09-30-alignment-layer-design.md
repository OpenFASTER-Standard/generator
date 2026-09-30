# Alignment Layer — Design

## Summary

Connects one real, already-cited `sh:PropertyShape` from `annotation_model`
(roadmap task 1) to a real, already-published concept in the
[`institutional-ontology`](https://github.com/OpenFASTER-Standard/institutional-ontology)
repo (`IO:0000001`, "All given names"), via a real SSSOM mapping record,
and proves that an *existing*, unmodified transformation from
`annotation_model.transform` (roadmap task 2) can resolve a value through
that mapping instead of a hardcoded standard-specific predicate — the
concrete mechanism behind "one stored fact populates multiple outputs
without duplication."

This is the direct, minimal-surface-area fix for the real gap task 1
deliberately left open: two same-named fields in two different standards
are two unconnected `sh:PropertyShape` nodes until an explicit alignment
says otherwise (`docs/specs/2026-09-30-core-semantic-annotation-model-design.md`,
lines 68–74). This spec is that "otherwise," proven once, for real.

## Context

Depends on roadmap tasks 1 and 2 (`annotation_model`, already merged).
Per this project's standing rule, nothing here treats existing code as
untouchable — but nothing here needs to touch task 1 or 2's code at all;
this task is additive on top of both.

**What already exists that this design builds on, verified live, not
assumed:**

- **A real shared-concept vocabulary already exists and is not this
  repo's to duplicate.** `/work/institutional-ontology` is a real,
  separately-governed OWL ontology (BFO+IAO+SSSOM, real OBO Foundry
  practice, own PURL namespace `https://purl.openfaster.org/io/`)
  built explicitly "to give independent schemas a shared, stable set of
  things to point at instead of re-deriving equivalence between them
  pairwise" (that repo's own README). It already has ten real curated
  concepts/individuals, including `IO:0000001` ("All given names",
  full IRI `https://purl.openfaster.org/io/IO_0000001`), whose editor
  note already documents it as `skos:exactMatch` to MiKaDiv-VIB's
  `FirstName` and KaFE's `Vorname` (a sibling `openfaster-spec` repo's
  own field-mapping work, not this one). Building a parallel
  `generator/ontologies/core/*.ttl` — the original task-master
  auto-elaboration's proposal — would recreate the exact problem this
  ontology exists to prevent. This design depends on
  `institutional-ontology` directly instead.
- **No machine-readable SSSOM mapping file exists anywhere yet.**
  `institutional-ontology`'s own editor notes reference
  `mappings/mikadiv-kafe.sssom.tsv`, but that directory was renamed to
  `realizations/` in a later commit (`742d5bd`) and no `realizations/`
  directory exists in the current tree — the real mappings currently
  live only as prose inside `IAO:0000116` annotations. This task
  introduces the first real, structured SSSOM mapping file in the
  OpenFASTER ecosystem, not an import of an existing one.
- **A real, provable alignment target already exists.** Generator's own
  real corpus has `MiKaDiv_FM_Personentypen_1.02.xsd`'s `Vorname`
  attribute (`"Der Vorname der natürlichen Person."`) — not yet cited
  in generator, but real, present, and textually/semantically the same
  concept `IO:0000001` already covers for two sibling standards.
- **Task 2's transformation layer needs no changes.**
  `annotation_model/transform/apply.py`'s `apply_transformation(graph,
  name)` runs a `Transformation`'s SPARQL query against "whatever
  `rdflib.Graph` it's handed" (that module's own docstring already
  cross-references this task as the reason). A mapping expressed as a
  real triple, unioned into the data graph before the call, is
  indistinguishable to that function from any other triple — no
  `AlignmentAwareSparqlEngine` subclass, no engine change.
- **No second real, generator-annotated standard exists yet.**
  `mikadiv-vib`/`kafe` under `/work/ontologies` are empty directory
  stubs (a `README.md` only) — this design proves "one fact, many
  outputs" using two different task-2 *output artifacts* from the same
  standard's data, not two standards. Cross-*standard* proof is
  explicitly deferred (see Non-Goals) until a second standard is
  actually annotated — a task-1-shaped prerequisite, not this task's
  job.
- **`sssom-py` (real, PyPI, v0.4.21) is not used.** Its dependency
  chain (`pandas`, `linkml`, `linkml-runtime`, `sparqlwrapper`) is
  disproportionate to reading a handful of TSV rows, and its schema
  validation checks SSSOM's *shape*, not whether `subject_id`/
  `object_id` resolve to anything real — the actual correctness concern
  here. This project already made the identical call in task 2 (SPARQL
  + Jinja2 over RML). SSSOM's *file format* — a small YAML-comment
  header plus a TSV body, real predicates from SKOS
  (`skos:exactMatch`/`skos:closeMatch`/etc.) — needs nothing heavier
  than `csv` and `rdflib`, both already dependencies.

## Core Concepts

### `alignment/sssom.py` (new module)

```python
@dataclass(frozen=True)
class Mapping:
    subject_id: str            # generator property-shape IRI
    subject_label: str
    predicate_id: str          # a real SKOS CURIE, e.g. "skos:exactMatch"
    object_id: str             # institutional-ontology concept IRI
    object_label: str
    mapping_justification: str # a real semapv CURIE, e.g. "semapv:ManualMappingCuration"
    confidence: float
    author_id: str
```

- `load_sssom_mappings(path: Path) -> list[Mapping]` — parses a real
  SSSOM TSV: `#`-prefixed YAML-comment header lines (`curie_map`,
  `mapping_set_id`, `license`, etc. — read for provenance, not
  interpreted further by this MVP), then a normal TSV body via `csv`.
  CURIEs in `subject_id`/`object_id`/`predicate_id` are expanded via
  the header's own `curie_map` before being handed anywhere as an IRI.
- `mappings_to_graph(mappings: list[Mapping]) -> Graph` — mints one
  real triple per mapping: `(expand(subject_id), expand(predicate_id),
  expand(object_id))`. This is SSSOM's own documented "simple" RDF
  serialization (the mapping predicate used directly, not reified) —
  not invented here.

### `alignment/validate.py` (new module)

`validate_mappings(mappings, *, generator_graph, institutional_graph) ->
None` — raises a clear, named error (mirroring `hints.py`'s
`PropertyShapeNotFoundError` precedent from this same branch's own
final review) rather than silently accepting a mapping to nothing:

- `UnresolvedSubjectError` if `subject_id` doesn't name a real
  `(subject, RDF.type, SH.PropertyShape)` in `generator_graph`.
- `UnresolvedObjectError` if `object_id` doesn't name a real
  `(object, RDF.type, OWL.Class)` or `(object, RDF.type,
  OWL.NamedIndividual)` in `institutional_graph` (the real ontology has
  both kinds — `IO:0000001` is a class, `IO:0000004` "Ms." is an
  individual).

### `alignment/institutional_ontology.py` (new module)

Mirrors `tests/corpus_fixtures.py`'s already-established pattern for
"real data lives in a sibling repo that might not be checked out,"
applied to a second sibling repo:

- `DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH = "/work/institutional-ontology/institutional-ontology.owl"`
  — the real, committed release artifact (that repo's own README:
  "Commit the release OWL artifact at repo root, not just gitignored
  `build/`").
- `institutional_ontology_path() -> Path` — reads
  `INSTITUTIONAL_ONTOLOGY_PATH`, defaulting to the above, at call time
  (not import time — matching `webapp/app.py`'s existing
  `_module_root()`/`_catalog_path()` convention).
- `load_institutional_ontology(path: Path | None = None) -> Graph` —
  parses the real OWL/XML file via `rdflib`.
- `tests/alignment/fixtures.py`: `requires_real_institutional_ontology
  = pytest.mark.skipif(not institutional_ontology_path().is_file(),
  reason=...)`, matching `corpus_fixtures.py`'s
  `requires_real_corpus` exactly.

### `alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv` (new, real, committed data)

One real mapping, hand-curated the same way `institutional-ontology`'s
own editor notes are: the real MiKaDiv-FM Personentypen `Vorname`
attribute, cited exactly the way
`tests/annotation_model/transform/conftest.py`'s existing
`two_field_graph` fixture already cites its own fields (`standard`=the
family name, `shape_name`="{Family}Fields", `property_name`=the field
name) — `standard="MiKaDiv-FM Personentypen"`,
`shape_name="PersonentypenFields"`, `property_name="Vorname"`. This
task's `subject_id`, resolved via `annotation_model`'s existing
deterministic IRI scheme and verified live —
`https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname`
— `skos:exactMatch` `IO:0000001` (`https://purl.openfaster.org/io/IO_0000001`),
justified `semapv:ManualMappingCuration`, confidence `0.95` (matching
the confidence `institutional-ontology`'s own editor note already
assigns the equivalent MiKaDiv-VIB/KaFE mappings, for the same
real-world-scope reasoning).

## Data Flow

1. A real property shape is cited in `generator`'s own graph via task
   1's existing `annotate_xpath()` against the real
   `MiKaDiv_FM_Personentypen_1.02.xsd` (`standard="MiKaDiv-FM
   Personentypen"`, `shape_name="PersonentypenFields"`,
   `property_name="Vorname"`, matching
   `tests/annotation_model/transform/conftest.py`'s own established
   citation pattern exactly — no new citation capability needed).
2. `load_sssom_mappings()` reads the real, committed TSV.
3. `validate_mappings()` confirms both sides of the one real mapping
   resolve against the real generator graph and the real, separately
   checked-out `institutional-ontology.owl`.
4. `mappings_to_graph()` produces the one real alignment triple.
5. Two `Transformation` instances, of two of task 2's existing renderer
   *kinds* (a `jinja_text_renderer` Bikeshed-style prose renderer and a
   workbook/tabular renderer — both real, already demonstrated in
   `tests/annotation_model/transform/test_renderers.py`), registered
   and torn down within this task's own test exactly the way every
   `Transformation` in this codebase already is (registration is always
   call-scoped — nothing is ever a standing pre-registered instance).
   Each runs its own SPARQL query, unmodified from task 2's engine,
   against `data_graph + alignment_graph`, traversing through
   `IO:0000001` rather than the generator-specific `Vorname` property
   shape directly, and each correctly produces the real cited given-name
   value in its own output shape — proving "many outputs" with the real
   constraint that only one standard is annotated so far.

## Error Handling

- A mapping whose `subject_id` doesn't resolve to a real property shape
  in the generator graph raises `UnresolvedSubjectError` — never
  silently produces a triple pointing at nothing.
- A mapping whose `object_id` doesn't resolve to a real class or
  individual in `institutional-ontology` raises `UnresolvedObjectError`
  — same reasoning.
- `institutional-ontology.owl` not being present on disk (no sibling
  checkout) skips every test that needs it, cleanly, via
  `requires_real_institutional_ontology` — never fails opaquely on
  missing/empty data, matching `requires_real_corpus`'s existing
  precedent and its own documented reasoning
  (`tests/corpus_fixtures.py`'s module docstring, "the 2026-09-29 audit
  finding on this exact gap").
- Malformed SSSOM TSV (missing a required column, an unparseable
  `confidence` float) raises a clear, named parse error identifying the
  file and the bad row — never a bare `csv`/`KeyError` traceback.

## Testing Strategy

- **Real shapes, not synthetic ones**: the validation and integration
  tests cite the real Personentypen `Vorname` attribute via the real
  `annotate_xpath()` against the real XSD, matching this project's
  established discipline (task 1/3's own test suites).
- **Real target ontology, not a mocked graph**: tests load the real,
  separately checked-out `institutional-ontology.owl` and skip cleanly
  via `requires_real_institutional_ontology` when it isn't present
  (e.g. on a CI runner with no sibling checkout, matching
  `requires_real_corpus`'s existing precedent).
- **Referential-integrity failures, both directions**: a mapping with a
  typo'd/nonexistent `subject_id` raises `UnresolvedSubjectError`
  without producing a triple; same for a nonexistent `object_id` and
  `UnresolvedObjectError`.
- **The actual deliverable, proven end-to-end**: one real citation, one
  real mapping, two different *unmodified* task-2 `Transformation`s
  each resolving the same underlying fact through
  `IO:0000001` — this is the test that proves the headline claim
  ("one stored fact populates multiple outputs without duplication"),
  not a unit test of any one function in isolation.
- **Round-trip TSV parsing**: `load_sssom_mappings()` on the real
  committed file returns exactly the one real `Mapping` with every
  field matching the file's real content.

## Non-Goals

- **New `institutional-ontology` concepts.** Curating a concept that
  doesn't exist yet is that repo's own careful process (real BFO/IAO
  subclassing, real citation-backed editor notes, `robot verify`) — out
  of scope for this task, which only consumes what's already real and
  published there.
- **A second real generator-annotated standard.** `mikadiv-vib`/`kafe`
  have no real annotated content in `generator`'s own corpus yet;
  proving true cross-*standard* alignment (not just cross-*output*)
  waits until one exists — a task-1-shaped prerequisite.
- **A webapp mapping-management UI, or a CLI tool.** Nobody has asked
  for either yet; this spec proves the mechanism with real committed
  data and real tests, not an authoring workflow.
- **Any XML write-back / round-trip generation** (core data → a
  schema-valid regulatory filing, validated against the official XSD).
  Nothing in this codebase does this anywhere today — task 2's
  transformation layer only ever renders read-only text documents.
  Inventing this capability is a separate, much larger task, not a side
  effect of adding an alignment layer.
- **`sssom-py`, ROBOT, or any ontology-reasoning dependency.** See
  Context above.
- **Automatic/ML-based mapping inference.** Every mapping is
  human-curated (`semapv:ManualMappingCuration`), matching
  `institutional-ontology`'s own real practice.

## Open Questions

- Whether a mapping's `confidence`/`mapping_justification` fields ever
  need to influence which mapping wins when a future property shape has
  *multiple* candidate mappings to different concepts — not a concern
  for this spec's single real mapping, deferred until a real case with
  more than one mapping per subject exists.
- Whether `alignments/*.sssom.tsv` needs its own change-review process
  once curators other than this session start adding mappings (e.g.
  requiring the same PR-review pattern `institutional-ontology` itself
  uses) — an operational/process question, not a design one, deferred
  to whoever actually curates the second mapping.
