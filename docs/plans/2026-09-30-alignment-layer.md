# Alignment Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect one real, cited `sh:PropertyShape` in generator's own
graph to a real concept in the separately-governed `institutional-ontology`
repo via a real SSSOM mapping, and prove that two existing, unmodified
task-2 `Transformation` kinds can each resolve a value through that
mapping instead of a hardcoded predicate.

**Architecture:** Five bottom-up tasks, one repository. Task 1 builds the
SSSOM TSV reader/writer (no `sssom-py` — see spec). Task 2 builds
read-only access to the real, separately-checked-out
`institutional-ontology.owl`, mirroring `tests/corpus_fixtures.py`'s
established real-sibling-repo pattern. Task 3 builds referential-integrity
validation across both graphs. Task 4 commits the one real mapping this
whole design exists to prove. Task 5 is the end-to-end proof: cite, align,
and resolve through two different existing renderer kinds.

**Tech Stack:** Python 3.11, `rdflib>=7.6` (already a dependency, used for
both TSV→graph conversion and reading `institutional-ontology.owl`'s real
RDF/XML). Standard library `csv` for the TSV body — no `sssom-py`, no
`pyyaml` (the header block this needs is small enough to hand-parse; see
Task 1).

**Spec:** `docs/specs/2026-09-30-alignment-layer-design.md`

## Global Constraints

- **No `sssom-py` dependency.** The spec rejects it for its
  `pandas`/`linkml`/`linkml-runtude` weight relative to what this task
  needs (reading a handful of TSV rows). Do not add it during
  implementation even if a step feels easier with it.
- **`INSTITUTIONAL_ONTOLOGY_PATH` and `MIKADIV_CORPUS_ROOT`-style env
  vars are read at call time, not import time.** Matches
  `webapp/app.py`'s `_catalog_path()`/`_corpus_root()` convention
  exactly (see that file's own comments) — never a module-level
  `os.environ.get(...)` assignment for these, which would silently pin
  whatever the env var was at first import.
- **Real data only.** Every test that needs a property shape cites one
  for real via `annotate_xpath()` against the real
  `MiKaDiv_FM_Personentypen_1.02.xsd`; every test that needs
  `institutional-ontology` content reads the real, separately
  checked-out `institutional-ontology.owl`, skipping cleanly (never
  failing opaquely) when it isn't present, via a `requires_real_*`
  marker matching `tests/corpus_fixtures.py`'s `requires_real_corpus`
  exactly.
- **Citation convention for the one real mapping in this plan**:
  `standard="MiKaDiv-FM Personentypen"`, `shape_name="PersonentypenFields"`,
  `property_name="Vorname"` — matching
  `tests/annotation_model/transform/conftest.py`'s `two_field_graph`
  fixture's own established convention (family-qualified `standard`,
  `shape_name="{Family}Fields"`, `property_name`=the field name), not
  the older per-field-shape convention in `tests/annotation_model/test_hints.py`.
  Verified live: this produces the real property-shape IRI
  `https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname`.
- **Real XPath for `Vorname`**, verified live to resolve:
  `/xs:schema/xs:complexType[@name='PersonNatDatenType']/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']`
  against `{MIKADIV_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd`.
- **Real target concept**: `IO:0000001`, full IRI
  `https://purl.openfaster.org/io/IO_0000001`, real label
  `"All given names"@en` (verified live against
  `/work/institutional-ontology/institutional-ontology.owl`, real
  RDF/XML, `rdflib.Graph.parse(path, format="xml")`).
- **`OWL.Class` / `OWL.NamedIndividual`**: `institutional-ontology.owl`
  has real instances of both kinds of object (`IO:0000001` is a class,
  `IO:0000004` "Ms." is a named individual — verified live) — validation
  must accept either.

## Review Focus

- **`validate_mappings()` catching a bad subject vs. a bad object are
  two independently-tested paths, not one test that only exercises
  whichever happens to run first.** Task 3's two failure tests must each
  use a mapping that is valid on the *other* side, so a validator that
  only ever checks one side (and always raises/always passes regardless
  of the other) cannot pass both tests by accident.
- **`load_sssom_mappings()` genuinely expands CURIEs via the file's own
  `curie_map` header, not a hardcoded prefix table.** Task 1's fixture
  uses a `curie_map` entry with a prefix this plan's other real data
  (Task 4) does not use, so a hardcoded-prefix implementation fails
  Task 1's own test even before Task 4 exists.
- **The end-to-end test (Task 5) proves two *different* renderer kinds
  resolve through the alignment, not the same renderer invoked twice.**
  One assertion must be on Jinja2-rendered text, the other on real
  `openpyxl` workbook cell values — two structurally different output
  types, matching `test_renderers.py`'s own existing pattern of proving
  "no framework code" by using a genuinely different renderer for each.
- **`institutional_ontology_path()`/`INSTITUTIONAL_ONTOLOGY_PATH` is
  read at call time.** Task 2's test sets the env var, calls the
  function, then changes the env var and calls it again in the same
  test process (no reimport) — a module-level read would return the
  first value both times.
- **A malformed SSSOM row fails loudly and specifically.** Task 1's
  malformed-TSV test asserts the raised error names the file and the
  bad row's line content, not a bare `KeyError`/`IndexError` — matching
  this project's established "never a bare underlying exception with no
  indication of what failed" principle (`annotation_model/transform/apply.py`'s
  `TransformationError` is the precedent to match in spirit, not in
  type).

---

### Task 1: SSSOM TSV reading and RDF conversion

**Files:**
- Create: `alignment/__init__.py` (empty)
- Create: `alignment/sssom.py`
- Test: `tests/alignment/__init__.py` (empty)
- Test: `tests/alignment/test_sssom.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `Mapping` (frozen dataclass: `subject_id: str`,
  `subject_label: str`, `predicate_id: str`, `object_id: str`,
  `object_label: str`, `mapping_justification: str`, `confidence: float`,
  `author_id: str` — all fields hold the *expanded* IRI/string form, not
  the raw CURIE). `load_sssom_mappings(path: Path) -> list[Mapping]`.
  `mappings_to_graph(mappings: list[Mapping]) -> Graph`.
  `SssomParseError(ValueError)` — raised only by `load_sssom_mappings`
  on a malformed file; no other task constructs or needs to catch one
  (Tasks 3-5 call `load_sssom_mappings` only on well-formed files and
  let a real parse error propagate uncaught if it ever occurs).

- [ ] **Step 1: Write the failing test for parsing a real SSSOM TSV fixture**

```python
# tests/alignment/test_sssom.py
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SKOS

from alignment.sssom import Mapping, SssomParseError, load_sssom_mappings, mappings_to_graph

# Deliberately made-up prefixes ("madeup"/"concept"), not the real
# gen:/io: this plan's real data (Task 4) uses -- proves
# load_sssom_mappings() expands CURIEs via THIS file's own curie_map,
# not a hardcoded table of known prefixes.
VALID_TSV = """\
#curie_map:
#  madeup: https://example.org/madeup#
#  concept: https://example.org/concepts/
#  skos: http://www.w3.org/2004/02/skos/core#
#  semapv: https://w3id.org/semapv/vocab/
#mapping_set_id: https://openfaster.org/alignments/test-set
#license: https://creativecommons.org/publicdomain/zero/1.0/
subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id
madeup:Test/Shape/Field\tField\tskos:exactMatch\tconcept:0000099\tTest concept\tsemapv:ManualMappingCuration\t0.95\ttest-author
"""


def test_loads_one_real_mapping_with_curie_expansion(tmp_path: Path):
    tsv_path = tmp_path / "test.sssom.tsv"
    tsv_path.write_text(VALID_TSV, encoding="utf-8")

    mappings = load_sssom_mappings(tsv_path)

    assert mappings == [
        Mapping(
            subject_id="https://example.org/madeup#Test/Shape/Field",
            subject_label="Field",
            predicate_id="http://www.w3.org/2004/02/skos/core#exactMatch",
            object_id="https://example.org/concepts/0000099",
            object_label="Test concept",
            mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
            confidence=0.95,
            author_id="test-author",
        )
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py::test_loads_one_real_mapping_with_curie_expansion -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'alignment'` or
`ImportError` for `load_sssom_mappings`).

- [ ] **Step 3: Implement `Mapping` and `load_sssom_mappings(path: Path) -> list[Mapping]` in `alignment/sssom.py`**

Split the file's lines into header (`#`-prefixed) and body. Parse the
header for a `curie_map:` block: a top-level `#curie_map:` line starts
it; subsequent `#  prefix: iri` lines (two-space indent, still
`#`-prefixed) are entries; a `#`-line without that indent ends the
block. Other top-level `#key: value` header lines (`mapping_set_id`,
`license`) are read but not otherwise used by this MVP. Parse the
non-header lines with `csv.DictReader(..., delimiter="\t")`. For each
row, expand `subject_id`/`predicate_id`/`object_id` via the curie map
(split on the first `:`, look up the prefix, concatenate) and build a
`Mapping`, converting `confidence` to `float`. A CURIE whose prefix
isn't in the map, or a row missing a required column, raises
`SssomParseError` naming the file and the offending row's raw line.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py::test_loads_one_real_mapping_with_curie_expansion -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for a malformed row raising a named, specific error**

```python
def test_missing_column_raises_named_error_identifying_the_file_and_row(tmp_path: Path):
    tsv_path = tmp_path / "bad.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\n"  # missing every other required column
        "gen:X\tskos:exactMatch\tgen:Y\n",
        encoding="utf-8",
    )

    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)

    assert str(tsv_path) in str(exc_info.value)
    assert "gen:X" in str(exc_info.value)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py::test_missing_column_raises_named_error_identifying_the_file_and_row -v`
Expected: FAIL (either no error raised, or a bare `KeyError`, not `SssomParseError`
with the file path and row content in the message).

- [ ] **Step 7: Make `load_sssom_mappings` raise `SssomParseError` with file + row context on a missing column**

Catch the `KeyError` a short/missing column raises when building each
`Mapping` and re-raise as `SssomParseError(f"{path}: row {raw_row!r} is
missing a required SSSOM column: {original_exc}")`.

- [ ] **Step 8: Run both tests to verify they pass**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Write the failing test for `mappings_to_graph`**

```python
def test_mappings_to_graph_mints_one_real_triple():
    mapping = Mapping(
        subject_id="https://openfaster.org/ns/generator#Test/Shape/Field",
        subject_label="Field",
        predicate_id="http://www.w3.org/2004/02/skos/core#exactMatch",
        object_id="https://purl.openfaster.org/io/IO_0000099",
        object_label="Test concept",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95,
        author_id="test-author",
    )

    graph = mappings_to_graph([mapping])

    assert len(graph) == 1
    assert (
        URIRef("https://openfaster.org/ns/generator#Test/Shape/Field"),
        SKOS.exactMatch,
        URIRef("https://purl.openfaster.org/io/IO_0000099"),
    ) in graph
```

- [ ] **Step 10: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py::test_mappings_to_graph_mints_one_real_triple -v`
Expected: FAIL (`ImportError` for `mappings_to_graph`, or `AttributeError`).

- [ ] **Step 11: Implement `mappings_to_graph(mappings: list[Mapping]) -> Graph` in `alignment/sssom.py`**

For each mapping, `graph.add((URIRef(m.subject_id), URIRef(m.predicate_id),
URIRef(m.object_id)))`. `predicate_id` is already a fully-expanded IRI
string from `load_sssom_mappings` (or supplied pre-expanded by a caller
building `Mapping`s directly) — no further CURIE handling here.

- [ ] **Step 12: Run all of Task 1's tests to verify they pass**

Run: `.venv/bin/pytest tests/alignment/test_sssom.py -v`
Expected: PASS (3 passed)

- [ ] **Step 13: Commit**

```bash
git add alignment/__init__.py alignment/sssom.py tests/alignment/__init__.py tests/alignment/test_sssom.py
git commit -m "feat(alignment): parse real SSSOM TSV files into RDF triples"
```

---

### Task 2: Read-only access to the real institutional-ontology graph

**Files:**
- Create: `alignment/institutional_ontology.py`
- Create: `tests/alignment/fixtures.py`
- Test: `tests/alignment/test_institutional_ontology.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH: str`.
  `institutional_ontology_path() -> Path`.
  `load_institutional_ontology(path: Path | None = None) -> Graph`.
  `requires_real_institutional_ontology` (a `pytest.mark.skipif`
  instance, from `tests/alignment/fixtures.py`) — Task 3 and Task 5
  import this.

- [ ] **Step 1: Write the failing test for the default path and env-var override, read at call time**

```python
# tests/alignment/test_institutional_ontology.py
import os

from alignment.institutional_ontology import (
    DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH,
    institutional_ontology_path,
)


def test_default_path_with_no_env_var(monkeypatch):
    monkeypatch.delenv("INSTITUTIONAL_ONTOLOGY_PATH", raising=False)
    assert institutional_ontology_path() == Path(DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH)


def test_env_var_override_is_read_at_call_time_not_import_time(monkeypatch):
    monkeypatch.setenv("INSTITUTIONAL_ONTOLOGY_PATH", "/tmp/first.owl")
    assert institutional_ontology_path() == Path("/tmp/first.owl")

    monkeypatch.setenv("INSTITUTIONAL_ONTOLOGY_PATH", "/tmp/second.owl")
    assert institutional_ontology_path() == Path("/tmp/second.owl")
```

Add `from pathlib import Path` to the test file's imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_institutional_ontology.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'alignment.institutional_ontology'`).

- [ ] **Step 3: Implement `DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH` and `institutional_ontology_path()` in `alignment/institutional_ontology.py`**

```python
DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH = "/work/institutional-ontology/institutional-ontology.owl"
```

`institutional_ontology_path()` returns `Path(os.environ.get(
"INSTITUTIONAL_ONTOLOGY_PATH", DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH))` —
read inside the function body, matching `webapp/app.py`'s
`_corpus_root()` exactly (a comment there is the precedent to cite).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/alignment/test_institutional_ontology.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Create `tests/alignment/fixtures.py` with `requires_real_institutional_ontology`**

```python
"""Shared access to the real, separately checked-out institutional-ontology
repo, mirroring tests/corpus_fixtures.py's requires_real_corpus exactly.
"""
from __future__ import annotations

import pytest

from alignment.institutional_ontology import institutional_ontology_path

requires_real_institutional_ontology = pytest.mark.skipif(
    not institutional_ontology_path().is_file(),
    reason=(
        f"real institutional-ontology.owl not available at "
        f"{institutional_ontology_path()!r} -- set INSTITUTIONAL_ONTOLOGY_PATH to override"
    ),
)
```

- [ ] **Step 6: Write the failing test for loading the real ontology**

```python
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from alignment.institutional_ontology import load_institutional_ontology
from tests.alignment.fixtures import requires_real_institutional_ontology

IO_0000001 = URIRef("https://purl.openfaster.org/io/IO_0000001")


@requires_real_institutional_ontology
def test_loads_real_ontology_with_the_real_given_name_concept():
    graph = load_institutional_ontology()

    assert len(graph) > 0
    assert (IO_0000001, RDF.type, OWL.Class) in graph
    labels = list(graph.objects(IO_0000001, RDFS.label))
    assert labels == [Literal("All given names", lang="en")]
```

Add `from rdflib import Literal` to the test file's imports.

- [ ] **Step 7: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_institutional_ontology.py -v`
Expected: FAIL (`ImportError` for `load_institutional_ontology`), or if
run in an environment without `/work/institutional-ontology`, SKIPPED —
either is an acceptable "not yet passing" result; if SKIPPED, confirm
the skip reason names the missing path correctly before moving on.

- [ ] **Step 8: Implement `load_institutional_ontology(path: Path | None = None) -> Graph` in `alignment/institutional_ontology.py`**

```python
def load_institutional_ontology(path: Path | None = None) -> Graph:
    graph = Graph()
    graph.parse(path or institutional_ontology_path(), format="xml")
    return graph
```

- [ ] **Step 9: Run all of Task 2's tests to verify they pass**

Run: `.venv/bin/pytest tests/alignment/test_institutional_ontology.py -v`
Expected: PASS (3 passed) if `/work/institutional-ontology` is present on
this machine; SKIPPED for the one real-ontology test otherwise, with the
other two still passing.

- [ ] **Step 10: Commit**

```bash
git add alignment/institutional_ontology.py tests/alignment/fixtures.py tests/alignment/test_institutional_ontology.py
git commit -m "feat(alignment): read the real, separately checked-out institutional-ontology graph"
```

---

### Task 3: Referential-integrity validation

**Files:**
- Create: `alignment/validate.py`
- Test: `tests/alignment/test_validate.py`

**Interfaces:**
- Consumes: `Mapping` (Task 1, `alignment/sssom.py`).
  `load_institutional_ontology`, `requires_real_institutional_ontology`
  (Task 2). `requires_real_corpus`, `REAL_CORPUS_ROOT` (already exists,
  `tests/corpus_fixtures.py`). `annotate_xpath` (already exists,
  `annotation_model/rdf.py`).
- Produces: `UnresolvedSubjectError(LookupError)`,
  `UnresolvedObjectError(LookupError)`. `validate_mappings(mappings:
  list[Mapping], *, generator_graph: Graph, institutional_graph: Graph)
  -> None`. No other task consumes this task's output — it is the last
  piece Task 5 assembles before the end-to-end proof.

- [ ] **Step 1: Write the failing test for a mapping that validates cleanly against real graphs on both sides**

```python
# tests/alignment/test_validate.py
from rdflib import Graph, URIRef
from rdflib.namespace import SKOS

from alignment.institutional_ontology import load_institutional_ontology
from alignment.sssom import Mapping
from alignment.validate import UnresolvedObjectError, UnresolvedSubjectError, validate_mappings
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.alignment.fixtures import requires_real_institutional_ontology
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)
VORNAME_IRI = "https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname"
IO_0000001 = "https://purl.openfaster.org/io/IO_0000001"


def _cited_vorname_graph() -> Graph:
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    annotate_xpath(
        graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )
    return graph


def _valid_mapping() -> Mapping:
    return Mapping(
        subject_id=VORNAME_IRI, subject_label="Vorname",
        predicate_id=str(SKOS.exactMatch),
        object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )


@requires_real_corpus
@requires_real_institutional_ontology
def test_a_real_valid_mapping_does_not_raise():
    validate_mappings(
        [_valid_mapping()],
        generator_graph=_cited_vorname_graph(),
        institutional_graph=load_institutional_ontology(),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_validate.py::test_a_real_valid_mapping_does_not_raise -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'alignment.validate'`).

- [ ] **Step 3: Implement `UnresolvedSubjectError`, `UnresolvedObjectError`, and `validate_mappings` in `alignment/validate.py`**

Mirror `annotation_model/hints.py`'s `PropertyShapeNotFoundError` style
(a docstring explaining exactly what triggers it and why it must not be
silently ignored). For each mapping: raise `UnresolvedSubjectError` if
`(URIRef(mapping.subject_id), RDF.type, SH.PropertyShape) not in
generator_graph`; raise `UnresolvedObjectError` if neither
`(URIRef(mapping.object_id), RDF.type, OWL.Class)` nor
`(URIRef(mapping.object_id), RDF.type, OWL.NamedIndividual)` is in
`institutional_graph`. Both error messages name the mapping's
`subject_id`/`object_id` and `subject_label`/`object_label`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/alignment/test_validate.py::test_a_real_valid_mapping_does_not_raise -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for an unresolved subject**

```python
@requires_real_institutional_ontology
def test_nonexistent_subject_raises_unresolved_subject_error():
    bad_mapping = Mapping(
        subject_id="https://openfaster.org/ns/generator#NoSuchStandard/NoSuchShape/NoSuchField",
        subject_label="Nope", predicate_id=str(SKOS.exactMatch),
        object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(UnresolvedSubjectError):
        validate_mappings(
            [bad_mapping], generator_graph=Graph(), institutional_graph=load_institutional_ontology(),
        )
```

Add `import pytest` to the test file's imports.

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_validate.py::test_nonexistent_subject_raises_unresolved_subject_error -v`
Expected: FAIL if `validate_mappings` doesn't yet check the subject side at
all (should already pass after Step 3-4 if implemented correctly — if it
passes immediately, re-read Step 3's implementation, since this is the
Review Focus item about both sides being independently tested; a
validator that always raises `UnresolvedSubjectError` regardless of
object correctness would also make this pass, which is why Step 9 below
exists).

- [ ] **Step 7: Run all validate tests together to verify nothing regressed**

Run: `.venv/bin/pytest tests/alignment/test_validate.py -v`
Expected: PASS (2 passed) — `test_a_real_valid_mapping_does_not_raise`
must still pass alongside this new failing-subject test, confirming the
validator distinguishes the two mappings rather than always raising.

- [ ] **Step 8: Write the failing test for an unresolved object**

```python
@requires_real_corpus
def test_nonexistent_object_raises_unresolved_object_error():
    bad_mapping = Mapping(
        subject_id=VORNAME_IRI, subject_label="Vorname",
        predicate_id=str(SKOS.exactMatch),
        object_id="https://purl.openfaster.org/io/IO_9999999", object_label="Nope",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(UnresolvedObjectError):
        validate_mappings(
            [bad_mapping], generator_graph=_cited_vorname_graph(), institutional_graph=Graph(),
        )
```

- [ ] **Step 9: Run test to verify it fails, then run the whole file to verify all four pass**

Run: `.venv/bin/pytest tests/alignment/test_validate.py -v`
Expected: PASS (4 passed) — this is the test that would catch a
validator implemented as "if either side is wrong, raise
UnresolvedSubjectError" (Step 7 would already have passed by accident in
that buggy case, but this test raising the wrong error type would fail
here, proving the two checks are genuinely independent).

- [ ] **Step 10: Commit**

```bash
git add alignment/validate.py tests/alignment/test_validate.py
git commit -m "feat(alignment): validate a mapping's subject and object resolve to real things"
```

---

### Task 4: The one real committed mapping

**Files:**
- Create: `alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv`
- Test: `tests/alignment/test_real_mapping_file.py`

**Interfaces:**
- Consumes: `load_sssom_mappings`, `Mapping` (Task 1).
  `validate_mappings` (Task 3). `load_institutional_ontology`,
  `requires_real_institutional_ontology` (Task 2). `annotate_xpath`
  (existing). `requires_real_corpus`, `REAL_CORPUS_ROOT` (existing).
- Produces: the real, committed TSV file at
  `alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv` — Task 5
  loads this exact file, does not construct its own.

- [ ] **Step 1: Write the real TSV file**

```tsv
#curie_map:
#  gen: https://openfaster.org/ns/generator#
#  io: https://purl.openfaster.org/io/IO_
#  skos: http://www.w3.org/2004/02/skos/core#
#  semapv: https://w3id.org/semapv/vocab/
#mapping_set_id: https://openfaster.org/alignments/mikadiv-fm-to-institutional-ontology
#license: https://creativecommons.org/publicdomain/zero/1.0/
subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	confidence	author_id
gen:MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname	Vorname	skos:exactMatch	io:0000001	All given names	semapv:ManualMappingCuration	0.95	openfaster-generator-system
```

The `subject_id` CURIE's local part after `gen:` is the real property-shape
IRI's own path segment, percent-encoding included — copy it exactly from
the Global Constraints section above, do not re-derive it.

- [ ] **Step 2: Write the failing test that this real file loads to exactly one real Mapping**

```python
# tests/alignment/test_real_mapping_file.py
from pathlib import Path

from alignment.sssom import load_sssom_mappings

REAL_MAPPING_FILE = Path("alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv")


def test_the_real_committed_file_loads_to_exactly_one_mapping():
    mappings = load_sssom_mappings(REAL_MAPPING_FILE)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.subject_id == (
        "https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname"
    )
    assert mapping.object_id == "https://purl.openfaster.org/io/IO_0000001"
    assert mapping.predicate_id == "http://www.w3.org/2004/02/skos/core#exactMatch"
    assert mapping.confidence == 0.95
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_real_mapping_file.py -v`
Expected: FAIL only if Step 1's file has a typo relative to this
assertion (e.g. a CURIE that doesn't expand to exactly this IRI) — if it
already passes, the file was written correctly; still run this step to
confirm rather than assuming.

- [ ] **Step 4: Fix the TSV file if Step 3 failed, then re-run until it passes**

Run: `.venv/bin/pytest tests/alignment/test_real_mapping_file.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test that the real file validates cleanly against real graphs**

```python
from rdflib import Graph

from alignment.institutional_ontology import load_institutional_ontology
from alignment.validate import validate_mappings
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.alignment.fixtures import requires_real_institutional_ontology
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)


@requires_real_corpus
@requires_real_institutional_ontology
def test_the_real_committed_mapping_validates_against_real_graphs():
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    generator_graph = Graph()
    annotate_xpath(
        generator_graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )

    mappings = load_sssom_mappings(REAL_MAPPING_FILE)

    validate_mappings(
        mappings, generator_graph=generator_graph, institutional_graph=load_institutional_ontology(),
    )
```

Add `from alignment.sssom import load_sssom_mappings` to this file's
imports (alongside the existing import already present from Step 2).

- [ ] **Step 6: Run both of this task's tests to verify they pass**

Run: `.venv/bin/pytest tests/alignment/test_real_mapping_file.py -v`
Expected: PASS (2 passed) if both real sibling repos are present;
Step 5's test SKIPPED otherwise, Step 2's test still PASSED (it needs
neither real corpus nor real institutional-ontology, only the committed
TSV file and Task 1's parser).

- [ ] **Step 7: Commit**

```bash
git add alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv tests/alignment/test_real_mapping_file.py
git commit -m "feat(alignment): commit the real MiKaDiv-FM Vorname -> IO:0000001 mapping"
```

---

### Task 5: End-to-end proof — two renderer kinds resolve through the alignment

**Files:**
- Test: `tests/alignment/test_end_to_end.py`

**Interfaces:**
- Consumes: `load_sssom_mappings`, `mappings_to_graph` (Task 1).
  `Transformation`, `register`, `unregister` (existing,
  `annotation_model/transform/registry.py`). `apply_transformation`
  (existing, `annotation_model/transform/apply.py`).
  `jinja_text_renderer` (existing, `annotation_model/transform/jinja.py`).
  `openpyxl.Workbook` (existing dependency, real usage pattern already in
  `tests/annotation_model/transform/test_renderers.py`). The real
  committed mapping file from Task 4.
- Produces: nothing further — this is the plan's final task.

- [ ] **Step 1: Write the failing end-to-end test**

```python
# tests/alignment/test_end_to_end.py
from pathlib import Path

from openpyxl import Workbook

from alignment.sssom import load_sssom_mappings, mappings_to_graph
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation, register, unregister
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)
REAL_MAPPING_FILE = Path("alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv")

ALIGNED_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
  ?property skos:exactMatch <https://purl.openfaster.org/io/IO_0000001> .
}
"""


def _workbook_renderer(rows: list[dict]) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["hash"])
    for row in rows:
        sheet.append([str(row["hash"])])
    return workbook


@requires_real_corpus
def test_two_different_renderers_resolve_the_same_fact_through_the_alignment():
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    data_graph = Graph()
    annotate_xpath(
        data_graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )

    alignment_graph = mappings_to_graph(load_sssom_mappings(REAL_MAPPING_FILE))
    combined_graph = data_graph + alignment_graph

    try:
        register(Transformation(
            name="aligned-bikeshed-1", query=ALIGNED_QUERY,
            renderer=jinja_text_renderer("{% for row in rows %}{{ row['hash'] }}{% endfor %}"),
        ))
        register(Transformation(name="aligned-excel-1", query=ALIGNED_QUERY, renderer=_workbook_renderer))

        text_result = apply_transformation(combined_graph, "aligned-bikeshed-1")
        workbook_result = apply_transformation(combined_graph, "aligned-excel-1")

        assert text_result == content_hash
        sheet = workbook_result.active
        rows = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
        assert rows == [("hash",), (content_hash,)]
    finally:
        unregister("aligned-bikeshed-1")
        unregister("aligned-excel-1")
```

Add `from rdflib import Graph` to this file's imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/alignment/test_end_to_end.py -v`
Expected: FAIL or ERROR before Task 4 exists (this task assumes Tasks
1-4 are already complete when it starts; if run standalone before them,
expect an `ImportError`/`FileNotFoundError`). If Tasks 1-4 are already
done (the normal case, since this is the plan's last task), this should
already run — run it now specifically to confirm the query against
`combined_graph` genuinely needs the alignment triple: temporarily point
`ALIGNED_QUERY`'s `skos:exactMatch` line at a concept IRI that isn't in
the mapping file (e.g. `IO_9999999`) and confirm both `apply_transformation`
calls then raise `TransformationError` (0 rows, below `min_rows=1`)
before reverting to the real query and continuing.

- [ ] **Step 3: Run test to verify it passes with the real query**

Run: `.venv/bin/pytest tests/alignment/test_end_to_end.py -v`
Expected: PASS

- [ ] **Step 4: Run the whole project's test suite to confirm nothing regressed**

Run: `.venv/bin/pytest`
Expected: PASS (all tests that were passing before this plan still pass;
any newly-skipped tests are only the ones gated on
`requires_real_institutional_ontology`/`requires_real_corpus` when that
sibling repo genuinely isn't present on the machine running this).

- [ ] **Step 5: Commit**

```bash
git add tests/alignment/test_end_to_end.py
git commit -m "test(alignment): prove two different renderer kinds resolve through the alignment"
```
