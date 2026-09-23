# Source Reference Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the format-agnostic `Reference`/`Selector` model from
`docs/specs/2026-09-23-source-reference-model-design.md`: a way to record
exactly what real source span (an XSD element, a region of a PDF page) backs
a fact, precise enough to re-locate later and cheap to extend to a source
format nobody has thought of yet.

**Architecture:** A new, standalone `reference_model/` package with zero
dependency on any other module in this repo. A polymorphic `Selector`
(tagged by a `type` string) resolves against a real document via a small
per-type `resolve`/`canonicalize_and_hash` pair registered in a lookup
table; `Reference` is a recursive `Leaf | Union` shape built on top,
completely ignorant of what selector types exist.

**Tech Stack:** Python 3.11, `lxml` (XSD/XPath + C14N canonicalization),
`pdfplumber` (PDF text/word extraction, already a dependency), `shapely`
(new dependency — point-in-polygon test for PDF regions), `reportlab` (new
dev-only dependency — used only to construct one synthetic no-text-layer
PDF fixture for an edge-case test), `pytest`.

**Spec:** `docs/specs/2026-09-23-source-reference-model-design.md`

## Global Constraints

- Python `>=3.11` (matches this repo's existing `pyproject.toml`).
- `content_hash.algorithm` is fixed to `"sha256"` for now; the field exists
  so the algorithm could change later without a schema change.
- A `Reference` never stores a human-readable snippet — only a
  machine-addressable `selector` and a `content_hash`.
- `Union` parts are ordered (page-order, then reading-order) and that order
  is load-bearing: `Union.reference_id`/`Union.content_hash` are computed
  from the parts' own ids/hashes in that fixed order, so recomputing later
  is deterministic only if the same order is used.
- `resolve()` returns one of `RESOLVED` / `NOT_FOUND` / `AMBIGUOUS` /
  `UNCITABLE` as **data**, never an exception — those are all expected,
  meaningful outcomes at check time, not bugs.
- Only `cite()` (citation time) raises, and only when the result isn't a
  clean single `RESOLVED`.
- `Leaf.reference_id` is `sha256(subject_document.family +
  selector.canonical_form)` — it deliberately excludes `version`, so citing
  the same logical span across a version bump keeps the same
  `reference_id` even though `content_hash` may differ. This is a
  deliberate design choice from the spec, not an oversight — do not "fix"
  it by adding `version` into the hash input.
- `SvgSelector.page` is a plain integer field, not a full per-page
  sub-resource — a deliberate simplification versus strict Web Annotation
  practice, noted in the spec.

## Review Focus

- **Citing a `Union` around a not-yet-resolved part.** The spec requires
  citation-time discipline ("a `Reference` should never be creatable
  against something that doesn't unambiguously resolve") for a `Leaf`; a
  reasonable person would expect the same guarantee for a `Union`. Task 5
  shows this holds *by construction* (a `Union`'s parts can only ever be
  already-successfully-`cite()`d `Reference`s) and tests it directly.
- **An `XPathSelector` resolving to a non-element node** (an attribute or
  text node via a trailing `@name` or `text()` step). Canonical XML
  (C14N) is only meaningful for an element subtree; silently attempting it
  on an attribute node would either crash unhelpfully or, worse, hash
  something not actually addressable the way the selector implies. Task 3
  treats this as `UNCITABLE` and tests it against a real attribute-selecting
  XPath.
- **A malformed or missing `points=` attribute in an `SvgSelector.value`
  string.** A hand-authored or generated selector could easily contain a
  typo'd or empty polygon. Task 4 raises a specific, actionable
  `ValueError` rather than an opaque `shapely`/regex failure.
- **German-language text with umlauts/ß in extracted PDF regions.** Every
  real PDF in this corpus is German-language; a reasonable person would
  expect `ü`/`ö`/`ä`/`ß` to round-trip through `canonicalize_and_hash`
  without corruption or an encoding error. Task 4 tests this against real
  extracted German text, not ASCII-only fixtures.
- **A page number that no longer exists after a document shrinks.** A
  reasonable person filing a citation against page 12 of a 45-page PDF
  would expect a later version with only 10 pages to be reported as
  "reference gone," not to silently resolve against the wrong page or
  crash with an `IndexError`. Task 4 tests this against the real PDF's
  real page count.

---

## Task 1: Package skeleton, dependencies, and the core data model

**Files:**
- Modify: `pyproject.toml`
- Create: `reference_model/__init__.py`
- Create: `reference_model/model.py`
- Create: `tests/reference_model/__init__.py`
- Test: `tests/reference_model/test_model.py`

**Interfaces:**
- Produces: `Status` (enum: `RESOLVED`, `NOT_FOUND`, `AMBIGUOUS`,
  `UNCITABLE`), `ResolutionOutcome(status, raw_content=None)`,
  `SubjectDocument(family, version, retrieval_uri)`,
  `ContentHash(algorithm, digest)`, `Leaf(reference_id, subject_document,
  selector, content_hash, captured_at)`, `Union(parts)` (with
  `.reference_id`/`.content_hash` properties), `Reference` (type alias for
  `Leaf | Union`), `selector_canonical_form(selector) -> str`,
  `compute_leaf_reference_id(family, selector) -> str`,
  `compute_union_reference_id(part_ids: list[str]) -> str`,
  `compute_union_content_hash(part_digests: list[str]) -> ContentHash`,
  `now_iso() -> str`.

- [ ] **Step 1: Add new dependencies to `pyproject.toml`**

Edit the `dependencies` list to add `shapely`, and the `dev` optional
dependencies to add `reportlab`:

```toml
dependencies = [
    "rdflib>=7.0",
    "lxml>=5.0",
    "xmlschema>=3.0",
    "openpyxl>=3.1",
    "exrex>=0.11",
    "allpairspy>=2.5",
    "pdfplumber>=0.11",
    "pyoxigraph>=0.5",
    "oxrdflib>=0.5",
    "pyshacl>=0.27",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "shapely>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27", "reportlab>=4.0"]
```

Also add `reference_model` to the packages-discovery include list:

```toml
[tool.setuptools.packages.find]
include = ["extraction*", "generation*", "equivalence*", "ingestion*", "reporting*", "store*", "provenance*", "review*", "citations*", "webapp*", "reference_model*"]
```

- [ ] **Step 2: Install the new dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs successfully, including `shapely` and `reportlab`.

- [ ] **Step 3: Create the package skeleton**

`reference_model/__init__.py`:

```python
"""Format-agnostic source reference model: records exactly what real
source span (an XSD element, a PDF page region, ...) backs a fact, in a
way that's precise enough to re-locate later and cheap to extend to a new
source format. See docs/specs/2026-09-23-source-reference-model-design.md.
"""
```

`tests/reference_model/__init__.py`: empty file.

- [ ] **Step 4: Write the failing tests for the core data model**

`tests/reference_model/test_model.py`:

```python
from dataclasses import dataclass

from reference_model.model import (
    ContentHash,
    Leaf,
    SubjectDocument,
    Union,
    compute_leaf_reference_id,
    compute_union_content_hash,
    compute_union_reference_id,
    now_iso,
    selector_canonical_form,
)


@dataclass(frozen=True)
class _DummySelector:
    type: str
    value: str


def _make_leaf(family: str, version: str, digest: str) -> Leaf:
    selector = _DummySelector(type="Dummy", value="same-for-both")
    return Leaf(
        reference_id=compute_leaf_reference_id(family, selector),
        subject_document=SubjectDocument(family=family, version=version, retrieval_uri=f"/tmp/{family}"),
        selector=selector,
        content_hash=ContentHash(algorithm="sha256", digest=digest),
        captured_at=now_iso(),
    )


def test_selector_canonical_form_is_stable_and_reflects_content():
    a = _DummySelector(type="Dummy", value="x")
    b = _DummySelector(type="Dummy", value="x")
    c = _DummySelector(type="Dummy", value="y")
    assert selector_canonical_form(a) == selector_canonical_form(b)
    assert selector_canonical_form(a) != selector_canonical_form(c)


def test_leaf_reference_id_is_deterministic_and_excludes_version():
    # Same family+selector, deliberately different version and content_hash --
    # per the spec, reference_id must still match. See Global Constraints.
    leaf_v1 = _make_leaf("MiKaDiv_FM_Meldeart23", "1.02", "aaa")
    leaf_v2 = _make_leaf("MiKaDiv_FM_Meldeart23", "1.03", "bbb")
    assert leaf_v1.reference_id == leaf_v2.reference_id
    assert leaf_v1.content_hash.digest != leaf_v2.content_hash.digest


def test_leaf_reference_id_differs_across_families():
    leaf_a = _make_leaf("family-a", "1.0", "aaa")
    leaf_b = _make_leaf("family-b", "1.0", "aaa")
    assert leaf_a.reference_id != leaf_b.reference_id


def test_union_reference_id_and_hash_are_deterministic_given_order():
    leaf_1 = _make_leaf("family-a", "1.0", "aaa")
    leaf_2 = _make_leaf("family-b", "1.0", "bbb")

    union_1 = Union(parts=(leaf_1, leaf_2))
    union_2 = Union(parts=(leaf_1, leaf_2))
    assert union_1.reference_id == union_2.reference_id
    assert union_1.content_hash.digest == union_2.content_hash.digest

    # Order is load-bearing -- reversing it changes both ids, on purpose.
    union_reversed = Union(parts=(leaf_2, leaf_1))
    assert union_reversed.reference_id != union_1.reference_id
    assert union_reversed.content_hash.digest != union_1.content_hash.digest


def test_compute_union_reference_id_and_hash_are_pure_functions():
    assert compute_union_reference_id(["a", "b"]) == compute_union_reference_id(["a", "b"])
    assert compute_union_reference_id(["a", "b"]) != compute_union_reference_id(["b", "a"])
    hash_1 = compute_union_content_hash(["digest-a", "digest-b"])
    hash_2 = compute_union_content_hash(["digest-a", "digest-b"])
    assert hash_1.digest == hash_2.digest
    assert hash_1.algorithm == "sha256"
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.model'`

- [ ] **Step 6: Implement `reference_model/model.py`**

```python
"""Format-agnostic Reference/Selector data model. Nothing in this module
knows about XSDs, PDFs, or any specific selector type -- see
reference_model/selectors/ for those. See
docs/specs/2026-09-23-source-reference-model-design.md.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union as TypingUnion


class Status(Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    UNCITABLE = "UNCITABLE"


@dataclass(frozen=True)
class ResolutionOutcome:
    status: Status
    raw_content: Any = None  # only meaningful when status is RESOLVED


@dataclass(frozen=True)
class SubjectDocument:
    family: str
    version: str
    retrieval_uri: str


@dataclass(frozen=True)
class ContentHash:
    algorithm: str
    digest: str


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def selector_canonical_form(selector: Any) -> str:
    """Any dataclass-based Selector gets a stable canonical form for free --
    a new selector type needs no custom method for this to work, which is
    part of what makes adding a new source format trivial."""
    if not is_dataclass(selector):
        raise TypeError(f"selector {selector!r} must be a dataclass")
    return _canonical_json(asdict(selector))


def compute_leaf_reference_id(family: str, selector: Any) -> str:
    # Deliberately excludes subject_document.version -- see Global
    # Constraints in the implementation plan.
    key = f"{family}|{selector_canonical_form(selector)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compute_union_reference_id(part_ids: list[str]) -> str:
    key = "|".join(part_ids)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compute_union_content_hash(part_digests: list[str]) -> ContentHash:
    key = "|".join(part_digests)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return ContentHash(algorithm="sha256", digest=digest)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Leaf:
    reference_id: str
    subject_document: SubjectDocument
    selector: Any
    content_hash: ContentHash
    captured_at: str


@dataclass(frozen=True)
class Union:
    parts: tuple["Reference", ...]

    @property
    def reference_id(self) -> str:
        return compute_union_reference_id([p.reference_id for p in self.parts])

    @property
    def content_hash(self) -> ContentHash:
        return compute_union_content_hash([p.content_hash.digest for p in self.parts])


Reference = TypingUnion[Leaf, Union]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_model.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml reference_model/__init__.py reference_model/model.py tests/reference_model/__init__.py tests/reference_model/test_model.py
git commit -m "Add reference_model package: core Leaf/Union data model"
```

---

## Task 2: Selector-type registry

**Files:**
- Create: `reference_model/registry.py`
- Test: `tests/reference_model/test_registry.py`

**Interfaces:**
- Consumes: `ResolutionOutcome` (Task 1, `reference_model.model`).
- Produces: `Resolver(resolve, canonicalize_and_hash)`, `register(selector_type: str, resolver: Resolver) -> None`, `get_resolver(selector_type: str) -> Resolver`.

- [ ] **Step 1: Write the failing tests**

`tests/reference_model/test_registry.py`:

```python
from dataclasses import dataclass

import pytest

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, get_resolver, register


@dataclass(frozen=True)
class _DummySelector:
    type: str
    value: str


def test_register_and_get_resolver_round_trip():
    def resolve(selector, retrieval_uri):
        return ResolutionOutcome(status=Status.RESOLVED, raw_content=selector.value)

    def canonicalize_and_hash(raw_content):
        return f"hash-of-{raw_content}"

    resolver = Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash)
    register("DummyForRegistryTest", resolver)

    fetched = get_resolver("DummyForRegistryTest")
    selector = _DummySelector(type="DummyForRegistryTest", value="hello")
    outcome = fetched.resolve(selector, "/does/not/matter")
    assert outcome.status == Status.RESOLVED
    assert fetched.canonicalize_and_hash(outcome.raw_content) == "hash-of-hello"


def test_get_resolver_raises_for_unknown_type():
    with pytest.raises(KeyError, match="NoSuchSelectorType"):
        get_resolver("NoSuchSelectorType")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.registry'`

- [ ] **Step 3: Implement `reference_model/registry.py`**

```python
"""Selector-type registry. Adding a new source format means writing a
resolve()/canonicalize_and_hash() pair and registering it here -- nothing
else in this package, or any future consumer, needs to change or even be
aware a new format was added.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from reference_model.model import ResolutionOutcome

ResolveFn = Callable[[Any, str], ResolutionOutcome]
CanonicalizeAndHashFn = Callable[[Any], str]


@dataclass(frozen=True)
class Resolver:
    resolve: ResolveFn
    canonicalize_and_hash: CanonicalizeAndHashFn


_REGISTRY: dict[str, Resolver] = {}


def register(selector_type: str, resolver: Resolver) -> None:
    _REGISTRY[selector_type] = resolver


def get_resolver(selector_type: str) -> Resolver:
    try:
        return _REGISTRY[selector_type]
    except KeyError:
        raise KeyError(
            f"no resolver registered for selector type {selector_type!r}; "
            f"known types: {sorted(_REGISTRY)}"
        ) from None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_registry.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add reference_model/registry.py tests/reference_model/test_registry.py
git commit -m "Add reference_model selector-type registry"
```

---

## Task 3: `XPathSelector` for XSD elements

**Files:**
- Create: `reference_model/selectors/__init__.py`
- Create: `reference_model/selectors/xpath_selector.py`
- Modify: `reference_model/__init__.py`
- Test: `tests/reference_model/test_xpath_selector.py`

**Interfaces:**
- Consumes: `ResolutionOutcome`, `Status` (Task 1); `Resolver`, `register` (Task 2).
- Produces: `XPathSelector(type, value)` with `XPathSelector.create(value) -> XPathSelector`; registers `"XPathSelector"` in the registry as an import side effect.

- [ ] **Step 1: Write the failing tests, against the real XSD file**

`tests/reference_model/test_xpath_selector.py`:

```python
from pathlib import Path

import pytest

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.xpath_selector import XPathSelector

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _resolver():
    return get_resolver("XPathSelector")


def test_resolves_real_element_and_hash_is_reproducible():
    selector = XPathSelector.create(AORDNR_XPATH)
    resolver = _resolver()

    outcome_1 = resolver.resolve(selector, REAL_XSD)
    assert outcome_1.status == Status.RESOLVED
    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)

    outcome_2 = resolver.resolve(selector, REAL_XSD)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)

    assert digest_1 == digest_2
    assert len(digest_1) == 64  # sha256 hex digest


def test_rename_makes_selector_not_found(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1  # confirmed unique in the real file
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')

    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    selector = XPathSelector.create(AORDNR_XPATH)
    outcome = _resolver().resolve(selector, str(mutated_path))
    assert outcome.status == Status.NOT_FOUND


def test_content_change_without_rename_changes_hash_but_still_resolves(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('maxOccurs="3000"') == 1  # confirmed unique in the real file
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')

    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    selector = XPathSelector.create(AORDNR_XPATH)
    resolver = _resolver()

    original_outcome = resolver.resolve(selector, REAL_XSD)
    original_digest = resolver.canonicalize_and_hash(original_outcome.raw_content)

    mutated_outcome = resolver.resolve(selector, str(mutated_path))
    assert mutated_outcome.status == Status.RESOLVED
    mutated_digest = resolver.canonicalize_and_hash(mutated_outcome.raw_content)

    assert mutated_digest != original_digest


def test_xpath_matching_nothing_is_not_found():
    selector = XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.NOT_FOUND


def test_xpath_matching_multiple_real_elements_is_ambiguous():
    # The real file has 3 xs:element nodes (AbgefKapitalertragsteuer,
    # AmtlicheOrdnungsnummerListe, AOrdNr).
    selector = XPathSelector.create("//xs:element")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.AMBIGUOUS


def test_xpath_resolving_to_an_attribute_is_uncitable():
    selector = XPathSelector.create(AORDNR_XPATH + "/@name")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.UNCITABLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_xpath_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.selectors'`

- [ ] **Step 3: Implement `reference_model/selectors/xpath_selector.py`**

```python
"""XPathSelector: addresses one XML element inside an XSD by an XPath
expression evaluated against the schema's own document tree.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from lxml import etree

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register

_NSMAP = {"xs": "http://www.w3.org/2001/XMLSchema"}


@dataclass(frozen=True)
class XPathSelector:
    type: str
    value: str

    @staticmethod
    def create(value: str) -> "XPathSelector":
        return XPathSelector(type="XPathSelector", value=value)


def resolve(selector: XPathSelector, retrieval_uri: str) -> ResolutionOutcome:
    tree = etree.parse(retrieval_uri)
    matches = tree.xpath(selector.value, namespaces=_NSMAP)

    if len(matches) == 0:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    if len(matches) > 1:
        return ResolutionOutcome(status=Status.AMBIGUOUS)

    match = matches[0]
    if not isinstance(match, etree._Element):
        # e.g. an XPath ending in @attr or text() -- not element-rooted,
        # so it can't be canonicalized the way this selector type promises.
        return ResolutionOutcome(status=Status.UNCITABLE)
    return ResolutionOutcome(status=Status.RESOLVED, raw_content=match)


def canonicalize_and_hash(raw_content: "etree._Element") -> str:
    canonical_bytes = etree.tostring(raw_content, method="c14n")
    return hashlib.sha256(canonical_bytes).hexdigest()


register("XPathSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
```

`reference_model/selectors/__init__.py`:

```python
"""Importing this package registers every built-in selector type.
Adding a new format means adding a module here and importing it below --
nothing else changes."""
from reference_model.selectors import xpath_selector  # noqa: F401
```

- [ ] **Step 4: Wire selector registration into package import**

Modify `reference_model/__init__.py` to add, at the end of the file:

```python
from reference_model import selectors  # noqa: E402,F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_xpath_selector.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add reference_model/__init__.py reference_model/selectors/__init__.py reference_model/selectors/xpath_selector.py tests/reference_model/test_xpath_selector.py
git commit -m "Add XPathSelector for XSD elements, real-file tests"
```

---

## Task 4: `SvgSelector` for PDF page regions

**Files:**
- Create: `reference_model/selectors/svg_selector.py`
- Modify: `reference_model/selectors/__init__.py`
- Test: `tests/reference_model/test_svg_selector.py`

**Interfaces:**
- Consumes: `ResolutionOutcome`, `Status` (Task 1); `Resolver`, `register` (Task 2).
- Produces: `SvgSelector(type, page, value)` with `SvgSelector.create(page, points) -> SvgSelector`; registers `"SvgSelector"` in the registry as an import side effect.

- [ ] **Step 1: Write the failing tests, against the real PDF file**

The spec's testing strategy describes proving a hash changes by "mutating a
temp copy" of the source, the same technique Task 3 uses for the XSD.
For the PDF, that would mean authoring a modified PDF binary, which needs
extra tooling for no real gain here: two different real, already-existing
regions on the same page serve exactly the same purpose (proving
`canonicalize_and_hash` is sensitive to real content differences) using
only real, unaltered material — arguably more in keeping with this
project's practice of testing against real files than fabricating a
synthetic "mutated" PDF would be. The one place an actual mutation would
matter — proving a *renamed/removed* target goes to `NOT_FOUND` — is
already covered for XSDs in Task 3; the "blank region" and "no text layer"
tests below cover the PDF-specific `NOT_FOUND`/`UNCITABLE` cases using a
verified-real-blank region and a synthetic no-text PDF respectively.

`tests/reference_model/test_svg_selector.py`:

```python
from pathlib import Path

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.svg_selector import SvgSelector

REAL_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12  # confirmed: real page with a text layer, out of 45 total pages

# Real word bounding boxes on page 12, verified live against the actual file:
#   "2.2 Nachrichteninhalte" heading: x [70.9, 246.8], top [92.1, 110.1]
#   "Inhalt einer Nachricht" caption: x [180.2, 260.7], top [572.4, 581.4]
#   a verified-blank region with zero overlapping words: x [400, 550], top [200, 220]
HEADING_POINTS = "60,88 255,88 255,115 60,115"
CAPTION_POINTS = "170,565 270,565 270,590 170,590"
BLANK_POINTS = "400,200 550,200 550,220 400,220"


def _resolver():
    return get_resolver("SvgSelector")


def test_resolves_real_heading_and_hash_is_reproducible():
    selector = SvgSelector.create(PAGE_12, HEADING_POINTS)
    resolver = _resolver()

    outcome_1 = resolver.resolve(selector, REAL_PDF)
    assert outcome_1.status == Status.RESOLVED
    assert "Nachrichteninhalte" in outcome_1.raw_content

    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)
    outcome_2 = resolver.resolve(selector, REAL_PDF)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)
    assert digest_1 == digest_2


def test_different_real_region_produces_different_hash():
    resolver = _resolver()
    heading_outcome = resolver.resolve(SvgSelector.create(PAGE_12, HEADING_POINTS), REAL_PDF)
    caption_outcome = resolver.resolve(SvgSelector.create(PAGE_12, CAPTION_POINTS), REAL_PDF)

    assert "Inhalt" in caption_outcome.raw_content
    heading_digest = resolver.canonicalize_and_hash(heading_outcome.raw_content)
    caption_digest = resolver.canonicalize_and_hash(caption_outcome.raw_content)
    assert heading_digest != caption_digest


def test_german_umlauts_and_eszett_round_trip_through_the_hash():
    # "Dateigröße" -- real body text a few lines below the heading on this
    # same page -- contains both an umlaut (ö) and an eszett (ß).
    selector = SvgSelector.create(PAGE_12, "118,155 174,155 174,172 118,172")
    resolver = _resolver()
    outcome = resolver.resolve(selector, REAL_PDF)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "Dateigröße"
    digest = resolver.canonicalize_and_hash(outcome.raw_content)
    assert len(digest) == 64  # did not raise a UnicodeEncodeError etc.


def test_blank_region_is_not_found():
    selector = SvgSelector.create(PAGE_12, BLANK_POINTS)
    outcome = _resolver().resolve(selector, REAL_PDF)
    assert outcome.status == Status.NOT_FOUND


def test_nonexistent_page_is_not_found():
    selector = SvgSelector.create(46, HEADING_POINTS)  # real PDF has only 45 pages
    outcome = _resolver().resolve(selector, REAL_PDF)
    assert outcome.status == Status.NOT_FOUND


def test_page_with_no_text_layer_is_uncitable(tmp_path: Path):
    from reportlab.pdfgen import canvas as reportlab_canvas

    no_text_pdf = tmp_path / "no-text.pdf"
    c = reportlab_canvas.Canvas(str(no_text_pdf), pagesize=(200, 200))
    c.rect(10, 10, 180, 180, fill=1)  # a filled rectangle -- no text-drawing calls at all
    c.showPage()
    c.save()

    selector = SvgSelector.create(1, "0,0 200,0 200,200 0,200")
    outcome = _resolver().resolve(selector, str(no_text_pdf))
    assert outcome.status == Status.UNCITABLE


def test_malformed_points_raises_a_clear_error():
    selector = SvgSelector(type="SvgSelector", page=PAGE_12, value="<svg:polygon xmlns:svg='http://www.w3.org/2000/svg'/>")
    try:
        _resolver().resolve(selector, REAL_PDF)
        assert False, "expected a ValueError for a selector with no points= attribute"
    except ValueError as exc:
        assert "points=" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_svg_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.selectors.svg_selector'`

- [ ] **Step 3: Implement `reference_model/selectors/svg_selector.py`**

```python
"""SvgSelector: addresses an arbitrary polygon region on one page of a PDF.

Deliberately not a rectangle-only bounding box -- real PDF paragraphs wrap
irregularly around figures/columns, so an arbitrary polygon (borrowing the
real W3C Web Annotation SvgSelector shape) is needed. `page` is a plain
field rather than a full per-page sub-resource -- a deliberate
simplification, see the design spec.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pdfplumber
from shapely.geometry import Point, Polygon

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register

_POINTS_RE = re.compile(r"points=['\"]([^'\"]+)['\"]")


@dataclass(frozen=True)
class SvgSelector:
    type: str
    page: int  # 1-indexed, matching how humans refer to PDF page numbers
    value: str  # e.g. "<svg:polygon points='60,88 255,88 255,115 60,115' xmlns:svg='...'/>"

    @staticmethod
    def create(page: int, points: str) -> "SvgSelector":
        value = f"<svg:polygon points='{points}' xmlns:svg='http://www.w3.org/2000/svg'/>"
        return SvgSelector(type="SvgSelector", page=page, value=value)

    def polygon(self) -> Polygon:
        match = _POINTS_RE.search(self.value)
        if not match:
            raise ValueError(f"SvgSelector.value has no parseable points= attribute: {self.value!r}")
        coords = []
        for pair in match.group(1).strip().split():
            x_str, y_str = pair.split(",")
            coords.append((float(x_str), float(y_str)))
        if len(coords) < 3:
            raise ValueError(f"SvgSelector polygon needs at least 3 points, got {coords!r}")
        return Polygon(coords)


def resolve(selector: SvgSelector, retrieval_uri: str) -> ResolutionOutcome:
    with pdfplumber.open(retrieval_uri) as pdf:
        if selector.page < 1 or selector.page > len(pdf.pages):
            return ResolutionOutcome(status=Status.NOT_FOUND)

        page = pdf.pages[selector.page - 1]
        words = page.extract_words()
        if not words:
            # The whole page has no text layer at all -- a scanned/image-only
            # page, not merely an empty region on an otherwise textful page.
            return ResolutionOutcome(status=Status.UNCITABLE)

        polygon = selector.polygon()
        matched = [
            w
            for w in words
            if polygon.contains(Point((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
        ]
        if not matched:
            return ResolutionOutcome(status=Status.NOT_FOUND)

        matched.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
        text = " ".join(w["text"] for w in matched)
        return ResolutionOutcome(status=Status.RESOLVED, raw_content=text)


def canonicalize_and_hash(raw_content: str) -> str:
    normalized = " ".join(raw_content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


register("SvgSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
```

- [ ] **Step 4: Register the new selector module**

Modify `reference_model/selectors/__init__.py`:

```python
"""Importing this package registers every built-in selector type.
Adding a new format means adding a module here and importing it below --
nothing else changes."""
from reference_model.selectors import svg_selector, xpath_selector  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_svg_selector.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add reference_model/selectors/svg_selector.py reference_model/selectors/__init__.py tests/reference_model/test_svg_selector.py
git commit -m "Add SvgSelector for arbitrary polygon PDF regions, real-file tests"
```

---

## Task 5: `cite()`, `Union` assembly, and check-time resolution

**Files:**
- Create: `reference_model/cite.py`
- Test: `tests/reference_model/test_cite.py`

**Interfaces:**
- Consumes: `Leaf`, `Union`, `Reference`, `SubjectDocument`, `ContentHash`, `Status`, `compute_leaf_reference_id`, `now_iso` (Task 1); `get_resolver` (Task 2); `XPathSelector` (Task 3); `SvgSelector` (Task 4).
- Produces: `CitationError`, `cite(subject_document, selector) -> Leaf`, `cite_union(parts: list[Reference]) -> Union`, `LeafCheckResult(leaf, outcome, hash_changed)`, `check_leaf(leaf, retrieval_overrides=None) -> LeafCheckResult`, `check_reference(reference, retrieval_overrides=None) -> list[LeafCheckResult]`.

- [ ] **Step 1: Write the failing tests**

`tests/reference_model/test_cite.py`:

```python
from pathlib import Path

import pytest

from reference_model.cite import CitationError, check_leaf, check_reference, cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.svg_selector import SvgSelector
from reference_model.selectors.xpath_selector import XPathSelector

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
REAL_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12
HEADING_POINTS = "60,88 255,88 255,115 60,115"


def _xsd_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def _pdf_subject_document() -> SubjectDocument:
    return SubjectDocument(family="khb_mikadiv_fm_de", version="v9", retrieval_uri=REAL_PDF)


def test_cite_builds_a_leaf_from_a_real_xsd_element():
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    assert leaf.subject_document.family == "MiKaDiv_FM_Meldeart23"
    assert leaf.content_hash.algorithm == "sha256"
    assert len(leaf.content_hash.digest) == 64


def test_citing_the_same_span_twice_is_idempotent():
    leaf_1 = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    assert leaf_1.reference_id == leaf_2.reference_id
    assert leaf_1.content_hash.digest == leaf_2.content_hash.digest


def test_cite_raises_when_selector_does_not_resolve():
    bad_selector = XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']")
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), bad_selector)


def test_cite_raises_when_selector_is_ambiguous():
    ambiguous_selector = XPathSelector.create("//xs:element")
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), ambiguous_selector)


def test_cite_raises_when_region_is_uncitable(tmp_path: Path):
    from reportlab.pdfgen import canvas as reportlab_canvas

    no_text_pdf = tmp_path / "no-text.pdf"
    c = reportlab_canvas.Canvas(str(no_text_pdf), pagesize=(200, 200))
    c.rect(10, 10, 180, 180, fill=1)
    c.showPage()
    c.save()

    subject_document = SubjectDocument(family="synthetic", version="1", retrieval_uri=str(no_text_pdf))
    selector = SvgSelector.create(1, "0,0 200,0 200,200 0,200")
    with pytest.raises(CitationError):
        cite(subject_document, selector)


def test_a_union_can_only_ever_contain_already_resolved_leaves():
    # There is no way to construct a Leaf that failed to resolve -- cite()
    # already raised before one could exist -- so a Union is guaranteed by
    # construction to never contain a broken part. This test documents and
    # pins that guarantee rather than re-checking it defensively at
    # cite_union() time.
    good_leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']"))
    # The only Leaf available to put in a Union is the one that already
    # succeeded above.
    union = cite_union([good_leaf])
    assert union.parts == (good_leaf,)


def test_check_reference_on_a_union_reports_each_part_independently(tmp_path: Path):
    xsd_leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    pdf_leaf = cite(_pdf_subject_document(), SvgSelector.create(PAGE_12, HEADING_POINTS))
    union = cite_union([xsd_leaf, pdf_leaf])

    # Break only the XSD part, by pointing that family's re-check at a
    # mutated temp copy while the PDF part is re-checked against its real,
    # unchanged file.
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    results = check_reference(union, retrieval_overrides={"MiKaDiv_FM_Meldeart23": str(mutated_path)})
    results_by_family = {r.leaf.subject_document.family: r for r in results}

    assert results_by_family["MiKaDiv_FM_Meldeart23"].outcome.status == Status.NOT_FOUND
    assert results_by_family["khb_mikadiv_fm_de"].outcome.status == Status.RESOLVED
    assert results_by_family["khb_mikadiv_fm_de"].hash_changed is False


def test_check_leaf_detects_a_changed_hash_without_a_status_change(tmp_path: Path):
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))

    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = check_leaf(leaf, retrieval_uri=str(mutated_path))
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_cite.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.cite'`

- [ ] **Step 3: Implement `reference_model/cite.py`**

```python
"""cite() builds a new, verified Reference at citation time -- it raises
unless the selector resolves cleanly. check_leaf()/check_reference()
re-check an existing Reference later, returning outcomes as data without
raising: "this doesn't resolve anymore" is an expected, meaningful result
at check time, not a bug. See the Global Constraints in this plan and the
Resolution & Error Semantics section of the design spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reference_model.model import (
    ContentHash,
    Leaf,
    Reference,
    ResolutionOutcome,
    Status,
    SubjectDocument,
    Union,
    compute_leaf_reference_id,
    now_iso,
)
from reference_model.registry import get_resolver


class CitationError(Exception):
    pass


def cite(subject_document: SubjectDocument, selector: Any) -> Leaf:
    resolver = get_resolver(selector.type)
    outcome = resolver.resolve(selector, subject_document.retrieval_uri)
    if outcome.status != Status.RESOLVED:
        raise CitationError(
            f"cannot cite {selector!r} against {subject_document.retrieval_uri!r}: "
            f"resolved to {outcome.status.value}, not RESOLVED"
        )
    digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return Leaf(
        reference_id=compute_leaf_reference_id(subject_document.family, selector),
        subject_document=subject_document,
        selector=selector,
        content_hash=ContentHash(algorithm="sha256", digest=digest),
        captured_at=now_iso(),
    )


def cite_union(parts: list[Reference]) -> Union:
    # No further resolution check is needed here: every element of `parts`
    # is already either a Leaf built by a successful cite() call, or a
    # Union built the same recursive way -- there is no way to construct an
    # unresolved Reference to put in this list in the first place.
    return Union(parts=tuple(parts))


@dataclass(frozen=True)
class LeafCheckResult:
    leaf: Leaf
    outcome: ResolutionOutcome
    hash_changed: bool | None  # None unless outcome.status is RESOLVED


def check_leaf(leaf: Leaf, retrieval_uri: str | None = None) -> LeafCheckResult:
    resolver = get_resolver(leaf.selector.type)
    uri = retrieval_uri if retrieval_uri is not None else leaf.subject_document.retrieval_uri
    outcome = resolver.resolve(leaf.selector, uri)
    if outcome.status != Status.RESOLVED:
        return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=None)
    new_digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=new_digest != leaf.content_hash.digest)


def check_reference(
    reference: Reference, retrieval_overrides: dict[str, str] | None = None
) -> list[LeafCheckResult]:
    if isinstance(reference, Leaf):
        override = None
        if retrieval_overrides is not None:
            override = retrieval_overrides.get(reference.subject_document.family)
        return [check_leaf(reference, retrieval_uri=override)]

    results: list[LeafCheckResult] = []
    for part in reference.parts:
        results.extend(check_reference(part, retrieval_overrides))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_cite.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Run the full `reference_model` test suite**

Run: `pytest tests/reference_model/ -v`
Expected: PASS (all tests across Tasks 1-5)

- [ ] **Step 6: Commit**

```bash
git add reference_model/cite.py tests/reference_model/test_cite.py
git commit -m "Add cite()/cite_union()/check_reference() for the source reference model"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `Reference` (`Leaf`/`Union`), `XPathSelector`, and `SvgSelector` exist with the fields and semantics in the spec.
- [ ] The selector-type registry has working `resolve`/`canonicalize_and_hash` entries for both selector types.
- [ ] `pytest tests/reference_model/ -v` passes in full, against the real source files in `/work/ontologies/mikadiv-fm/sources/`.
- [ ] Citing the real `AOrdNr` element and the real page-12 KHB paragraph both produce a working `Reference`; re-resolving each against an intentionally mutated copy of its source produces the expected, distinguishable outcome (`NOT_FOUND` or a changed hash, never a silent false match).
