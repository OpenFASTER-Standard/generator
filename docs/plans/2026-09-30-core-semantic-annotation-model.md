# Core Semantic Annotation Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `annotation_model` package that turns a
citation of a real source span (an XSD element, a PDF region) into a
git-committed Turtle file containing a W3C Web Annotation, a PROV-O
provenance link, and a SHACL property shape — the foundational
representation every later OpenFASTER sub-project (transformation, UI
generation, alignment, process modeling) will be a projection of or
addition on top of.

**Architecture:** Five tasks, bottom-up, each producing a real,
independently-testable module. Task 1 is a hardened XML parser
(carried forward from existing, proven code, duplicated into the new
package rather than imported from the package it supersedes, so
`annotation_model` has zero dependency on `reference_model`). Task 2
resolves the two selector types against real sources, reusing the
existing, already-proven resolution logic and its real-corpus test
cases, re-expressed over a standalone `Status`/`ResolutionOutcome` pair
instead of importing the superseded ones. Task 3 turns a resolved
selector into RDF triples with `rdflib`. Task 4 wraps a git repository
as an explicit, required annotation target (no default, ever) and
writes/reads Turtle files to/from it. Task 5 re-resolves an existing
annotation's selector against the current source and reports drift.
Each task consumes only the previous task's real interface.

**Tech Stack:** Python 3.11, `rdflib>=7.6`, `pyshacl>=0.40` (new
dependencies — verified installable and their exact validation API
confirmed live before writing this plan, see Task 3), plus the
existing `lxml`/`pdfplumber`/`shapely` (unchanged) and the real
MiKaDiv-FM corpus via `tests/corpus_fixtures.py` (unchanged, reused
as-is).

**Spec:** `docs/specs/2026-09-30-core-semantic-annotation-model-design.md`

## Global Constraints

- **No default target data store, anywhere, ever.** `TargetStore.__init__`
  (Task 4) takes `path` as a required positional argument with no
  default value and no environment-variable fallback. This is a security/
  correctness property (a public regulation and a bank's private process
  must be indistinguishable to the tool), not a style choice — Task 4's
  own test proves omitting it raises `TypeError`, not just that the
  happy path works.
- **The XML parser is exactly** `etree.XMLParser(no_network=True,
  load_dtd=False, huge_tree=False)` — never add `resolve_entities=False`.
  This exact regression (blocking external entities but silently
  breaking internal-entity drift detection and crashing canonicalization)
  already happened once in this repo's history; Task 1's tests must
  prove both properties hold simultaneously, not just the external-entity
  block.
- **The four-way resolution outcome is exactly** `Status.RESOLVED` /
  `Status.NOT_FOUND` / `Status.AMBIGUOUS` / `Status.UNCITABLE`, defined
  fresh in `annotation_model.outcomes` (Task 2) — not imported from
  `reference_model.model`, which this package supersedes and must not
  depend on.
- **RDF namespaces are fixed across every task**: `OA =
  Namespace("http://www.w3.org/ns/oa#")` (W3C Web Annotation, not
  bundled with `rdflib`, so define it once in `annotation_model/namespaces.py`
  and import everywhere), `PROV`/`SH`/`XSD` from `rdflib.namespace`
  (bundled), and one small local extension `GEN =
  Namespace("https://openfaster.org/ns/generator#")` for the one concept
  no existing vocabulary covers — `GEN.contentHash`, a literal string
  `"sha256:<hex digest>"`. `GEN`'s IRI-minting scheme for shapes/properties
  (below) is provisional to this implementation, not a claim about the
  ecosystem's eventual naming policy.
- **IRI-minting scheme** (all under `GEN`, parameterized by `standard`,
  `shape_name`, `property_name` — every one of these three strings
  participates in every IRI, so two different standards using the same
  `property_name` never collide):
  - Node shape: `GEN[f"{standard}/{shape_name}"]`
  - Property shape: `GEN[f"{standard}/{shape_name}/{property_name}"]`
  - Property path (placeholder, not real-world semantics): `GEN[f"{standard}/{shape_name}/{property_name}/path"]`
  - Annotation: `GEN[f"{standard}/{shape_name}/{property_name}/annotation"]`
- **PDF source addressing** uses the real Adobe PDF Open Parameters
  fragment convention, `<source-uri>#page=<N>` (1-indexed, matching how
  `SvgSelector.page` already works) — not a bespoke page-numbering
  scheme.
- **File layout in a target store**: one Turtle file per node shape, at
  `shapes/<standard-slug>/<shape-slug>.ttl`, containing that shape, all
  its property shapes, and their annotations. `<standard-slug>`/
  `<shape-slug>` are the lowercased, hyphen-joined form of `standard`/
  `shape_name` (e.g. `"MiKaDiv-FM Meldeart23"` → `mikadiv-fm-meldeart23`).
  This was an explicit open question in the spec; recorded here as the
  concrete decision, simple and YAGNI per the spec's own instruction —
  one file per shape is the smallest unit the round-trip and
  multi-tenancy tests below can exercise independently.
- Every real-corpus test uses `tests/corpus_fixtures.py`'s
  `requires_real_corpus`/`REAL_CORPUS_ROOT` unchanged — this module has
  no dependency on the superseded representation and needs no changes.
- This plan does not touch `webapp/`, `citation_workflow/`, `discovery/`,
  `review_surfacing/`, `review_recording/`, `review_consultation/`,
  `references_catalog/`, or `reference_model/` — they stay exactly as
  they are until a later, separate migration plan exists.
- **Self-review note, not a gap**: the spec's layer-1 discussion (reusing
  `ontologies/xsd`'s/`xml`'s existing OWL vocabulary where it already
  formalizes a real external standard) is a principle for a later task
  to apply when it actually types a shape's underlying schema construct
  — the spec's own Concrete Workflow never requires layer-1 typing
  triples as part of annotation, so no task here produces them. Nothing
  in this plan references or depends on `ontologies/xsd`/`xml`.
- **Also not built by this plan**: any admin-facing CLI/UI for driving
  the workflow interactively. This plan delivers the underlying,
  independently-tested library functions the workflow's steps map to;
  an admin-facing interface belongs to the collaborative platform
  (roadmap task 6) or a thin wrapper task of its own, not this one.

## Review Focus

- **A target-store path that doesn't exist yet vs. one that exists but
  isn't a git repo yet** — `TargetStore.open()` must `git init` a fresh
  directory and open (not re-init) an existing repo, without crashing on
  either. (Task 4)
- **Re-annotating the same `(standard, shape_name, property_name)`
  twice must not duplicate triples** — calling `write_shape` again for a
  shape that already has some properties must add the new property
  without creating a second `sh:NodeShape` for the same shape IRI.
  (Task 4)
- **A PDF selector citing a page number beyond the real document's page
  count** must resolve `NOT_FOUND`, carried forward from the existing,
  already-correct `SvgSelector` behavior — a regression here would be
  silent. (Task 2)
- **Two different standards using an identical `property_name` must
  never collide** in the RDF graph or on disk — proven by annotating
  the same `property_name` under two different `standard` values into
  the same store and asserting both node shapes and both property
  shapes exist independently. (Task 3)
- **Drift checking must handle all four `Status` outcomes on
  re-resolution, not only "hash changed" and "not found"** — a
  previously-`RESOLVED` selector that now resolves `AMBIGUOUS` or
  `UNCITABLE` (the source gained a second match, or the cited node's
  shape changed) must be reported distinctly, not coerced into a
  boolean. (Task 5)

---

### Task 1: Hardened XML parser

**Files:**
- Create: `annotation_model/__init__.py` (empty)
- Create: `annotation_model/xml_safety.py`
- Test: `tests/annotation_model/__init__.py` (empty)
- Test: `tests/annotation_model/test_xml_safety.py`

**Interfaces:**
- Produces: `SAFE_XML_PARSER: lxml.etree.XMLParser`

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/test_xml_safety.py
from pathlib import Path

from lxml import etree

from annotation_model.xml_safety import SAFE_XML_PARSER


def test_external_entity_is_blocked(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("super-secret-file-content", encoding="utf-8")
    malicious = tmp_path / "malicious.xml"
    malicious.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file://{secret}">
]>
<root>&xxe;</root>
""",
        encoding="utf-8",
    )
    import pytest

    with pytest.raises(etree.XMLSyntaxError):
        etree.parse(str(malicious), parser=SAFE_XML_PARSER)


def test_internal_entity_still_expands_and_changes_the_hash(tmp_path: Path):
    def _doc(value: str) -> Path:
        path = tmp_path / f"doc-{value}.xml"
        path.write_text(
            f"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY val "{value}">
]>
<root>&val;</root>
""",
            encoding="utf-8",
        )
        return path

    tree_a = etree.parse(str(_doc("alpha")), parser=SAFE_XML_PARSER)
    tree_b = etree.parse(str(_doc("beta")), parser=SAFE_XML_PARSER)
    bytes_a = etree.tostring(tree_a.getroot(), method="c14n")
    bytes_b = etree.tostring(tree_b.getroot(), method="c14n")

    assert b"alpha" in bytes_a
    assert b"beta" in bytes_b
    assert bytes_a != bytes_b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_xml_safety.py -v`
Expected: both FAIL with `ModuleNotFoundError: No module named 'annotation_model'`

- [ ] **Step 3: Implement `SAFE_XML_PARSER` in `annotation_model/xml_safety.py`**

```python
from lxml import etree

SAFE_XML_PARSER = etree.XMLParser(
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_xml_safety.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add annotation_model/__init__.py annotation_model/xml_safety.py \
        tests/annotation_model/__init__.py tests/annotation_model/test_xml_safety.py
git commit -m "feat(annotation_model): add hardened XML parser"
```

---

### Task 2: Selector resolution over real sources

**Files:**
- Create: `annotation_model/outcomes.py`
- Create: `annotation_model/selectors/__init__.py` (empty)
- Create: `annotation_model/selectors/xpath.py`
- Create: `annotation_model/selectors/svg.py`
- Test: `tests/annotation_model/test_xpath.py`
- Test: `tests/annotation_model/test_svg.py`

**Interfaces:**
- Consumes: Task 1's `SAFE_XML_PARSER`.
- Produces:
  - `Status(Enum)`: `RESOLVED`, `NOT_FOUND`, `AMBIGUOUS`, `UNCITABLE`
  - `ResolutionOutcome(status: Status, raw_content: Any = None)` (dataclass, frozen)
  - `resolve_xpath(retrieval_uri: str, xpath: str) -> ResolutionOutcome`
  - `canonicalize_and_hash_xml(element) -> str`
  - `resolve_svg_region(retrieval_uri: str, page: int, points: str) -> ResolutionOutcome`
  - `canonicalize_and_hash_text(text: str) -> str`

Steps below port the existing, already-proven logic and real-corpus
test cases from `reference_model/selectors/xpath_selector.py` and
`svg_selector.py` (read both in full before starting — the resolution
logic is correct and does not change; only the outcome type and module
location do). Real coordinates/XPaths below are copied from the
existing, already-verified-against-the-real-corpus test files.

- [ ] **Step 1: Write the failing test for `outcomes.py`**

```python
# tests/annotation_model/test_outcomes.py
from annotation_model.outcomes import ResolutionOutcome, Status


def test_status_has_four_members():
    assert {s.value for s in Status} == {"RESOLVED", "NOT_FOUND", "AMBIGUOUS", "UNCITABLE"}


def test_resolution_outcome_defaults_raw_content_to_none():
    outcome = ResolutionOutcome(status=Status.NOT_FOUND)
    assert outcome.raw_content is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/annotation_model/test_outcomes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.outcomes'`

- [ ] **Step 3: Implement `annotation_model/outcomes.py`**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Status(Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    UNCITABLE = "UNCITABLE"


@dataclass(frozen=True)
class ResolutionOutcome:
    status: Status
    raw_content: Any = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/annotation_model/test_outcomes.py -v`
Expected: `2 passed`

- [ ] **Step 5: Write the failing XPath tests (real corpus)**

```python
# tests/annotation_model/test_xpath.py
from pathlib import Path

from annotation_model.outcomes import Status
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import requires_real_corpus

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


@requires_real_corpus
def test_resolves_real_element_and_hash_is_reproducible():
    outcome_1 = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    assert outcome_1.status == Status.RESOLVED
    digest_1 = canonicalize_and_hash_xml(outcome_1.raw_content)

    outcome_2 = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    digest_2 = canonicalize_and_hash_xml(outcome_2.raw_content)

    assert digest_1 == digest_2
    assert len(digest_1) == 64


@requires_real_corpus
def test_rename_makes_selector_not_found(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    outcome = resolve_xpath(str(mutated_path), AORDNR_XPATH)
    assert outcome.status == Status.NOT_FOUND


def test_missing_source_file_is_not_found():
    outcome = resolve_xpath("/nonexistent/path/does-not-exist.xsd", AORDNR_XPATH)
    assert outcome.status == Status.NOT_FOUND


@requires_real_corpus
def test_xpath_matching_multiple_real_elements_is_ambiguous():
    outcome = resolve_xpath(REAL_XSD, "//xs:element")
    assert outcome.status == Status.AMBIGUOUS


@requires_real_corpus
def test_xpath_resolving_to_an_attribute_is_uncitable():
    outcome = resolve_xpath(REAL_XSD, AORDNR_XPATH + "/@name")
    assert outcome.status == Status.UNCITABLE


def test_an_external_entity_never_reaches_a_resolved_outcome(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("super-secret-file-content", encoding="utf-8")
    malicious = tmp_path / "malicious.xsd"
    malicious.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE xs:schema [
  <!ENTITY xxe SYSTEM "file://{secret}">
]>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="AOrdNr">
    <xs:annotation><xs:documentation>&xxe;</xs:documentation></xs:annotation>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )
    outcome = resolve_xpath(
        str(malicious), "/xs:schema/xs:element[@name='AOrdNr']/xs:annotation/xs:documentation"
    )
    assert outcome.status == Status.NOT_FOUND
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_xpath.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.selectors.xpath'`

- [ ] **Step 7: Implement `annotation_model/selectors/xpath.py`**

Port `resolve()`/`canonicalize_and_hash()` from
`reference_model/selectors/xpath_selector.py` verbatim in logic,
renamed to the signatures above, importing `SAFE_XML_PARSER` from
`annotation_model.xml_safety` and `Status`/`ResolutionOutcome` from
`annotation_model.outcomes`. Malformed XML (`etree.XMLSyntaxError`,
including the entity-parse failure above) and a missing file (`OSError`)
both map to `Status.NOT_FOUND`; a non-node-set XPath result or a
non-`_Element` single match maps to `Status.UNCITABLE`, exactly as the
existing module already does.

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_xpath.py -v`
Expected: `6 passed`

- [ ] **Step 9: Write the failing SVG tests (real corpus)**

```python
# tests/annotation_model/test_svg.py
from annotation_model.outcomes import Status
from annotation_model.selectors.svg import canonicalize_and_hash_text, resolve_svg_region
from tests.corpus_fixtures import requires_real_corpus

REAL_PDF = "/work/ontologies/mikadiv-fm/sources/1.02/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12
HEADING_POINTS = "60,88 255,88 255,115 60,115"
CAPTION_POINTS = "170,565 270,565 270,590 170,590"


@requires_real_corpus
def test_resolves_real_heading_and_hash_is_reproducible():
    outcome_1 = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    assert outcome_1.status == Status.RESOLVED
    assert "Nachrichteninhalte" in outcome_1.raw_content

    digest_1 = canonicalize_and_hash_text(outcome_1.raw_content)
    outcome_2 = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    digest_2 = canonicalize_and_hash_text(outcome_2.raw_content)
    assert digest_1 == digest_2


@requires_real_corpus
def test_different_real_region_produces_different_hash():
    heading = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    caption = resolve_svg_region(REAL_PDF, PAGE_12, CAPTION_POINTS)
    assert canonicalize_and_hash_text(heading.raw_content) != canonicalize_and_hash_text(caption.raw_content)


@requires_real_corpus
def test_page_beyond_real_document_length_is_not_found():
    outcome = resolve_svg_region(REAL_PDF, 9999, HEADING_POINTS)
    assert outcome.status == Status.NOT_FOUND


def test_missing_pdf_file_is_not_found():
    outcome = resolve_svg_region("/nonexistent/does-not-exist.pdf", 1, HEADING_POINTS)
    assert outcome.status == Status.NOT_FOUND
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_svg.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.selectors.svg'`

- [ ] **Step 11: Implement `annotation_model/selectors/svg.py`**

Port the polygon-parsing and `resolve()`/`canonicalize_and_hash()` logic
from `reference_model/selectors/svg_selector.py` verbatim in logic,
renamed to the signatures above (`resolve_svg_region(retrieval_uri,
page, points)` replaces `resolve(selector, retrieval_uri)` — inline the
points-string-to-`Polygon` parsing that `SvgSelector.polygon()` did,
since there is no longer a selector dataclass to hang the method off
of), using `Status`/`ResolutionOutcome` from `annotation_model.outcomes`.

- [ ] **Step 12: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_svg.py -v`
Expected: `4 passed`

- [ ] **Step 13: Add new dependencies to `pyproject.toml`**

Add `"rdflib>=7.6"` and `"pyshacl>=0.40"` to `[project] dependencies`
(needed starting next task, added now so `pip install -e .` picks them
up in one place). Run `pip install -e .` in the repo's virtualenv.

- [ ] **Step 14: Commit**

```bash
git add annotation_model/outcomes.py annotation_model/selectors/ \
        tests/annotation_model/test_outcomes.py tests/annotation_model/test_xpath.py \
        tests/annotation_model/test_svg.py pyproject.toml
git commit -m "feat(annotation_model): resolve XPath/SVG selectors against real sources"
```

---

### Task 3: RDF emission (Web Annotation + PROV-O + SHACL)

**Files:**
- Create: `annotation_model/namespaces.py`
- Create: `annotation_model/rdf.py`
- Test: `tests/annotation_model/test_rdf.py`

**Interfaces:**
- Consumes: Task 2's `Status`, `ResolutionOutcome`, `resolve_xpath`,
  `canonicalize_and_hash_xml`.
- Produces:
  - `annotate_xpath(graph: rdflib.Graph, *, standard: str, shape_name: str, property_name: str, xpath: str, source_uri: str, content_hash: str) -> rdflib.URIRef` (returns the property shape's IRI)
  - `annotate_svg(graph: rdflib.Graph, *, standard: str, shape_name: str, property_name: str, page: int, points: str, source_uri: str, content_hash: str) -> rdflib.URIRef`
  - `OA`, `GEN` namespace constants in `annotation_model/namespaces.py`

**Verified against the real, installed library before writing this
task** (`rdflib==7.6.0`, `pyshacl==0.40.1`): `pyshacl.validate(data_graph,
shacl_graph=shapes_graph, meta_shacl=True)` returns `(conforms: bool,
results_graph, results_text)` and raises
`pyshacl.errors.ReportableRuntimeError` if `shacl_graph` is not valid
SHACL — this is the shape-correctness check Step 1's test below uses.
`rdflib.namespace` ships `PROV`, `SH`, `XSD` built in; `OA` (Web
Annotation) does not and is defined in `annotation_model/namespaces.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/test_rdf.py
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.namespaces import GEN, OA
from annotation_model.rdf import annotate_xpath

SOURCE_URI = "file:///work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotate(graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape", property_name="value"):
    return annotate_xpath(
        graph,
        standard=standard,
        shape_name=shape_name,
        property_name=property_name,
        xpath=XPATH,
        source_uri=SOURCE_URI,
        content_hash="sha256:" + "a" * 64,
    )


def test_produces_a_valid_shacl_shape():
    import pyshacl

    graph = Graph()
    _annotate(graph)

    conforms, _, results_text = pyshacl.validate(Graph(), shacl_graph=graph, meta_shacl=True)
    assert conforms, results_text


def test_node_shape_and_property_shape_are_linked():
    graph = Graph()
    property_shape_iri = _annotate(graph)

    node_shape_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape"]
    assert (node_shape_iri, RDF.type, SH.NodeShape) in graph
    assert (node_shape_iri, SH.property, property_shape_iri) in graph
    assert (property_shape_iri, RDF.type, SH.PropertyShape) in graph


def test_property_shape_carries_provenance_and_hash():
    graph = Graph()
    property_shape_iri = _annotate(graph)

    annotation_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape/value/annotation"]
    assert (property_shape_iri, PROV.wasDerivedFrom, annotation_iri) in graph
    assert (property_shape_iri, GEN.contentHash, Literal("sha256:" + "a" * 64)) in graph
    assert (annotation_iri, RDF.type, OA.Annotation) in graph


def test_annotation_target_has_the_source_and_an_xpath_selector():
    graph = Graph()
    _annotate(graph)

    annotation_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape/value/annotation"]
    targets = list(graph.objects(annotation_iri, OA.hasTarget))
    assert len(targets) == 1
    target = targets[0]
    assert (target, OA.hasSource, URIRef(SOURCE_URI)) in graph

    selectors = list(graph.objects(target, OA.hasSelector))
    assert len(selectors) == 1
    selector = selectors[0]
    assert (selector, RDF.type, OA.XPathSelector) in graph
    assert (selector, RDF.value, Literal(XPATH)) in graph


def test_two_standards_with_the_same_property_name_do_not_collide():
    graph = Graph()
    shape_a = _annotate(graph, standard="MiKaDiv-FM Meldeart23", property_name="value")
    shape_b = _annotate(graph, standard="KaFE", property_name="value")

    assert shape_a != shape_b
    assert (shape_a, RDF.type, SH.PropertyShape) in graph
    assert (shape_b, RDF.type, SH.PropertyShape) in graph


def test_reannotating_the_same_shape_does_not_duplicate_the_node_shape():
    graph = Graph()
    _annotate(graph, property_name="value")
    _annotate(graph, property_name="other")

    node_shape_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape"]
    assert list(graph.triples((node_shape_iri, RDF.type, SH.NodeShape))) == [
        (node_shape_iri, RDF.type, SH.NodeShape)
    ]
    assert len(list(graph.objects(node_shape_iri, SH.property))) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_rdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.namespaces'`

- [ ] **Step 3: Implement `annotation_model/namespaces.py`**

```python
from rdflib import Namespace

OA = Namespace("http://www.w3.org/ns/oa#")
GEN = Namespace("https://openfaster.org/ns/generator#")
```

- [ ] **Step 4: Implement `annotation_model/rdf.py`**

`annotate_xpath` and `annotate_svg` both: (a) compute the node-shape,
property-shape, and annotation IRIs per the Global Constraints'
IRI-minting scheme; (b) add `(node_shape_iri, RDF.type, SH.NodeShape)`
only if not already present (checking `(node_shape_iri, RDF.type,
SH.NodeShape) in graph` first — this is what makes Step 1's
re-annotation test pass without duplication); (c) always add
`(node_shape_iri, SH.property, property_shape_iri)`,
`(property_shape_iri, RDF.type, SH.PropertyShape)`,
`(property_shape_iri, SH.path, path_iri)`,
`(property_shape_iri, PROV.wasDerivedFrom, annotation_iri)`,
`(property_shape_iri, GEN.contentHash, Literal(content_hash))`; (d)
build the annotation: `(annotation_iri, RDF.type, OA.Annotation)`, a
blank-node target with `OA.hasSource` = `URIRef(source_uri)` (`svg`
variant: `URIRef(f"{source_uri}#page={page}")`) and `OA.hasSelector` =
a blank-node selector of type `OA.XPathSelector`/`OA.SvgSelector` with
`RDF.value` = `Literal(xpath)`/`Literal(svg_value)` (the SVG selector's
literal value is the same `<svg:polygon points='...' .../>` string
`SvgSelector.create()` already builds in the superseded code — inline
that string construction here, no dependency on the old class); return
`property_shape_iri`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_rdf.py -v`
Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add annotation_model/namespaces.py annotation_model/rdf.py tests/annotation_model/test_rdf.py
git commit -m "feat(annotation_model): emit Web Annotation/PROV-O/SHACL triples"
```

---

### Task 4: Explicit git-backed target store, no default

**Files:**
- Create: `annotation_model/store.py`
- Test: `tests/annotation_model/test_store.py`

**Interfaces:**
- Consumes: any `rdflib.Graph` (e.g. one built by Task 3's `annotate_xpath`/`annotate_svg`).
- Produces:
  - `class TargetStore:`
    - `def __init__(self, path: str) -> None` — `path` required, no default, no env var read.
    - `def open(self) -> None` — `git init` if `path` doesn't exist yet or isn't a git repo; no-op (just confirms it's a git repo) if it already is one.
    - `def write_shape(self, graph: Graph, *, standard: str, shape_name: str) -> Path` — serializes `graph` as Turtle to `shapes/<standard-slug>/<shape-slug>.ttl` (slugify: lowercase, replace runs of non-alphanumeric characters with a single `-`, strip leading/trailing `-`), `git add` + `git commit` that file, returns its path.
    - `def read_shape(self, *, standard: str, shape_name: str) -> Graph` — parses that file back into a fresh `Graph`; raises `FileNotFoundError` if it doesn't exist.

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/test_store.py
import subprocess

import pytest
from rdflib import Graph
from rdflib.namespace import RDF, SH

from annotation_model.store import TargetStore


def test_path_is_required():
    with pytest.raises(TypeError):
        TargetStore()


def test_open_initializes_a_fresh_directory_as_a_git_repo(tmp_path):
    store = TargetStore(str(tmp_path / "fresh"))
    store.open()
    assert (tmp_path / "fresh" / ".git").is_dir()


def test_open_does_not_reinitialize_an_existing_repo(tmp_path):
    repo_path = tmp_path / "existing"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    marker = repo_path / ".git" / "existing-marker"
    marker.write_text("was here")

    store = TargetStore(str(repo_path))
    store.open()
    assert marker.exists()


def _shape_graph(shape_iri_local="TestShape"):
    from annotation_model.rdf import annotate_xpath

    graph = Graph()
    annotate_xpath(
        graph,
        standard="TestStandard",
        shape_name=shape_iri_local,
        property_name="value",
        xpath="/xs:schema/xs:element",
        source_uri="file:///tmp/test.xsd",
        content_hash="sha256:" + "b" * 64,
    )
    return graph


def test_write_then_read_round_trips(tmp_path):
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    written_path = store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")

    assert written_path.exists()
    assert written_path == tmp_path / "store" / "shapes" / "teststandard" / "testshape.ttl"

    read_back = store.read_shape(standard="TestStandard", shape_name="TestShape")
    from annotation_model.namespaces import GEN

    assert (GEN["TestStandard/TestShape"], RDF.type, SH.NodeShape) in read_back


def test_read_missing_shape_raises_file_not_found(tmp_path):
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    with pytest.raises(FileNotFoundError):
        store.read_shape(standard="TestStandard", shape_name="NoSuchShape")


def test_true_multi_tenancy_two_stores_never_cross_contaminate(tmp_path):
    public_store = TargetStore(str(tmp_path / "public"))
    public_store.open()
    public_store.write_shape(_shape_graph(), standard="PublicStandard", shape_name="PublicShape")

    bank_store = TargetStore(str(tmp_path / "bank-private"))
    bank_store.open()
    bank_store.write_shape(_shape_graph(), standard="BankInternal", shape_name="BankShape")

    public_files = sorted(p.name for p in (tmp_path / "public" / "shapes").rglob("*.ttl"))
    bank_files = sorted(p.name for p in (tmp_path / "bank-private" / "shapes").rglob("*.ttl"))
    assert public_files == ["publicshape.ttl"]
    assert bank_files == ["bankshape.ttl"]
    assert not (tmp_path / "public" / "shapes" / "bankinternal").exists()
    assert not (tmp_path / "bank-private" / "shapes" / "publicstandard").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.store'`

- [ ] **Step 3: Implement `annotation_model/store.py`**

Use `subprocess.run(["git", ...], cwd=self._path, check=True,
capture_output=True)` for `init`/`add`/`commit` (assumes `git config
user.name`/`user.email` are already set globally, as this box's own
`docker/init.sh` already does — do not add per-repo config in this
step, it isn't this task's problem). `open()` checks `(Path(path) /
".git").is_dir()` before deciding whether to `git init`. `write_shape`
creates parent directories with `Path.mkdir(parents=True,
exist_ok=True)`, serializes via `graph.serialize(format="turtle")`
before writing (avoids partial-write-then-format-error ordering
issues), then commits with a message naming `standard`/`shape_name`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_store.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add annotation_model/store.py tests/annotation_model/test_store.py
git commit -m "feat(annotation_model): git-backed target store, no default ever"
```

---

### Task 5: Drift checking

**Files:**
- Create: `annotation_model/drift.py`
- Test: `tests/annotation_model/test_drift.py`

**Interfaces:**
- Consumes: Task 2's `resolve_xpath`, `canonicalize_and_hash_xml`,
  `Status`; Task 3/4's stored graph structure (queries `GEN.contentHash`,
  `OA.hasSource`, `OA.hasSelector`/`RDF.value` via direct triple
  patterns — no SPARQL needed at this scale).
- Produces:
  - `@dataclass(frozen=True) class DriftResult: changed: bool; current_status: Status`
  - `check_xpath_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult`

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/test_drift.py
from pathlib import Path

from rdflib import Graph

from annotation_model.drift import check_xpath_drift
from annotation_model.namespaces import GEN
from annotation_model.outcomes import Status
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import requires_real_corpus

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotated_graph(source_uri: str, xpath: str = AORDNR_XPATH):
    outcome = resolve_xpath(source_uri.removeprefix("file://"), xpath)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath=xpath,
        source_uri=source_uri,
        content_hash=content_hash,
    )
    return graph, property_shape_iri


@requires_real_corpus
def test_unchanged_source_reports_no_drift():
    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.changed is False
    assert result.current_status == Status.RESOLVED


@requires_real_corpus
def test_content_change_is_detected_as_drift(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('maxOccurs="3000"') == 1
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(original.replace('maxOccurs="3000"', 'maxOccurs="5000"'), encoding="utf-8")

    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=str(mutated_path))
    assert result.changed is True
    assert result.current_status == Status.RESOLVED


@requires_real_corpus
def test_rename_is_reported_as_not_found_not_a_silent_pass(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1
    mutated_path = tmp_path / "renamed.xsd"
    mutated_path.write_text(original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"'), encoding="utf-8")

    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=str(mutated_path))
    assert result.changed is True
    assert result.current_status == Status.NOT_FOUND


@requires_real_corpus
def test_newly_ambiguous_source_is_reported_not_coerced_to_a_bool():
    # annotate_xpath() is a pure RDF builder -- it trusts its caller
    # already resolved successfully and does not re-resolve internally
    # (see Task 3), so a placeholder hash is fine here: this test is
    # only exercising check_xpath_drift's handling of a re-resolution
    # that comes back AMBIGUOUS, not the original annotation's validity.
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath="//xs:element",
        source_uri=f"file://{REAL_XSD}",
        content_hash="sha256:" + "0" * 64,
    )
    # //xs:element matches multiple real nodes in the unmodified file --
    # confirms check_xpath_drift reports AMBIGUOUS distinctly rather than
    # only ever returning RESOLVED/NOT_FOUND.
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.current_status == Status.AMBIGUOUS


@requires_real_corpus
def test_newly_uncitable_resolution_is_reported_not_coerced_to_a_bool():
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath=AORDNR_XPATH + "/@name",
        source_uri=f"file://{REAL_XSD}",
        content_hash="sha256:" + "0" * 64,
    )
    # .../@name resolves to an attribute, not an element -- UNCITABLE per
    # the existing, already-proven behavior. Confirms this fourth Status
    # value is also reported distinctly, not folded into NOT_FOUND.
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.current_status == Status.UNCITABLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_drift.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.drift'`

- [ ] **Step 3: Implement `annotation_model/drift.py`**

```python
from dataclasses import dataclass

from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from annotation_model.namespaces import GEN, OA
from annotation_model.outcomes import Status
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath


@dataclass(frozen=True)
class DriftResult:
    changed: bool
    current_status: Status


def check_xpath_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult:
    stored_hash = str(next(graph.objects(property_shape_iri, GEN.contentHash)))
    annotation_iri = next(graph.objects(property_shape_iri, PROV.wasDerivedFrom))
    target = next(graph.objects(annotation_iri, OA.hasTarget))
    selector = next(graph.objects(target, OA.hasSelector))
    xpath = str(next(graph.objects(selector, RDF.value)))

    outcome = resolve_xpath(retrieval_uri, xpath)
    if outcome.status != Status.RESOLVED:
        return DriftResult(changed=True, current_status=outcome.status)

    current_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    return DriftResult(changed=current_hash != stored_hash, current_status=Status.RESOLVED)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_drift.py -v`
Expected: `5 passed`

- [ ] **Step 5: Run the full test suite**

Run: `pytest`
Expected: all tests pass (existing `reference_model`/`webapp`/etc. tests
unaffected — this plan added a new, independent package and touched no
existing file).

- [ ] **Step 6: Commit**

```bash
git add annotation_model/drift.py tests/annotation_model/test_drift.py
git commit -m "feat(annotation_model): detect drift by re-resolving a stored annotation"
```

---

## Task-Master Bookkeeping

After Task 5's commit, mark roadmap task 1 done with real evidence:

```bash
npx -y --package=task-master-ai task-master set-status --id=1 --status=done
```

Then hand-edit `.taskmaster/tasks/tasks.json`'s task 1 to add an
`evidence.commits` array containing the five real commit SHAs from
Tasks 1–5 above (see `scripts/validate-tasks`'s requirements), and run
`scripts/validate-tasks` to confirm it passes before considering this
plan complete.
