# XSD Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `discovery/xsd_discoverer.py` from
`docs/specs/2026-09-25-xsd-discovery-design.md`: mechanically enumerate
every named XML Schema construct in a real XSD file as a citable
candidate, with a verified-unique XPath for each, and no judgment about
which ones are "worth" citing.

**Architecture:** One new small package with one function
(`discover_candidates()`) that walks a parsed XSD tree, computes an XPath
for every node bearing a `name` attribute in the XML Schema namespace,
and verifies each one resolves uniquely before returning it — split
across two tasks: the core algorithm proven against the real corpus, then
the synthetic-fixture edge cases the real corpus doesn't happen to
exercise on its own.

**Tech Stack:** Python 3.11, `lxml` (already a dependency), plus the real
MiKaDiv-FM corpus at `/work/ontologies/mikadiv-fm/sources/1.02/xsd/`.

**Spec:** `docs/specs/2026-09-25-xsd-discovery-design.md`

## Global Constraints

- **The candidate rule is one uniform test, never a tag whitelist**: any
  node whose tag is in the `http://www.w3.org/2001/XMLSchema` namespace
  and carries a `name` attribute. Do not special-case `xs:element` vs.
  `xs:complexType` vs. anything else — the whole point of this design is
  that they're treated identically.
- **Every computed XPath is verified live** by evaluating it against the
  real parsed document before being returned as a `Candidate` — a path
  that doesn't resolve to exactly one node becomes an `ExcludedCandidate`
  with the real match count, never silently dropped and never silently
  wrong.
- **The output XPath always uses the `xs:` prefix** for the XML Schema
  namespace, regardless of whatever prefix the source document itself
  binds that namespace to — it must match `XPathSelector`'s own hardcoded
  namespace map (`{"xs": "http://www.w3.org/2001/XMLSchema"}`), not the
  document's own authoring choice.
- **None of the testing scenarios below is optional or a "nice to have."**
  This project has an active, standing preference against narrowing test
  coverage to a hand-picked subset — every scenario named in the spec's
  own Testing strategy section gets a real, passing test in this plan,
  full stop.
- **Not in scope, per the spec's own Non-Goals**: no PDF discoverer, no
  judgment about which candidates matter, no UI, no `save_reference()`
  integration, no cross-file deduplication.

## Review Focus

- **A source document that binds the XML Schema namespace to a different
  prefix than `xs:`** (e.g. `xmlns:xsd="http://www.w3.org/2001/XMLSchema"`).
  A reasonable person feeding this a real-world XSD authored with a
  different convention would expect the computed XPath to still use `xs:`
  (matching what `XPathSelector` actually expects), not silently produce
  an XPath that can never resolve against this project's own selector.
  Tested directly in Task 2.
- **An `xs:element` using `ref=` instead of `name=`** (a real, valid XSD
  construct — confirmed absent from this specific real corpus via a live
  grep, but not an unrealistic input for a future schema version). A
  reasonable person would expect it to be cleanly skipped — neither
  miscounted as a candidate nor as an exclusion — since it has no `name`
  attribute at all. Tested directly in Task 2.
- **Two candidates that legitimately share the same `name` value but have
  different tags** (e.g. an `xs:element name="Foo"` and an unrelated
  `xs:complexType name="Foo"`). A reasonable person would expect both to
  be discovered independently and correctly, not conflated or treated as
  colliding, since their computed XPaths differ by tag even when `name`
  matches. Tested directly in Task 2.
- **A real, deeply-nested candidate** (confirmed live: `Paymentlines`,
  4 ancestor levels deep, inside `MiKaDiv_FM_Meldeart13_1.02.xsd`'s
  `Meldeart13` complexType, itself containing an inline anonymous
  `xs:complexType` this project's other, shallower test fixtures never
  exercise). A reasonable person would expect the algorithm to handle
  real nesting depth correctly, not just the 2-3-level examples this
  project's existing hand-written citations happen to use. Tested
  directly in Task 1.
- **The completeness-invariant test must use a genuinely independent
  count**, written fresh in the test file rather than by importing any
  private helper from `discovery.xsd_discoverer` — otherwise a bug shared
  between the implementation's own filtering logic and the test's "check"
  would silently cancel out instead of being caught. Enforced directly in
  Task 1's own test code.

---

## Task 1: Core algorithm, proven against the real corpus

**Files:**
- Create: `discovery/__init__.py`
- Create: `discovery/xsd_discoverer.py`
- Create: `tests/discovery/__init__.py`
- Test: `tests/discovery/test_xsd_discoverer.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `lxml.etree` (already a dependency; no other project code).
- Produces: `Candidate(tag, name, xpath)`, `ExcludedCandidate(tag, name, xpath, match_count)`,
  `DiscoveryResult(candidates, excluded)` (all frozen dataclasses), and
  `discover_candidates(xsd_path: str) -> DiscoveryResult`.

- [ ] **Step 1: Create the package skeletons**

`discovery/__init__.py`:

```python
"""Mechanically discovers citable candidates in a real XSD file. See
docs/specs/2026-09-25-xsd-discovery-design.md.
"""
```

`tests/discovery/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/discovery/test_xsd_discoverer.py`:

```python
import glob

from lxml import etree

from discovery.xsd_discoverer import DiscoveryResult, discover_candidates

REAL_XSD_DIR = "/work/ontologies/mikadiv-fm/sources/1.02/xsd"
REAL_MELDEART23_XSD = f"{REAL_XSD_DIR}/MiKaDiv_FM_Meldeart23_1.02.xsd"
_XS_NS = "http://www.w3.org/2001/XMLSchema"

AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def test_discovers_ground_truth_element_candidates():
    result = discover_candidates(REAL_MELDEART23_XSD)
    xpaths_by_name = {c.name: c.xpath for c in result.candidates}
    assert xpaths_by_name["AOrdNr"] == AORDNR_XPATH
    assert xpaths_by_name["AbgefKapitalertragsteuer"] == ABGEF_XPATH


def test_discovers_complextype_candidates_too():
    result = discover_candidates(REAL_MELDEART23_XSD)
    complex_type_names = {c.name for c in result.candidates if c.tag == "complexType"}
    assert "Meldeart23" in complex_type_names
    assert "AmtlicheOrdnungsnummerMa23ListeType" in complex_type_names


def test_every_candidate_xpath_resolves_to_exactly_one_node():
    tree = etree.parse(REAL_MELDEART23_XSD)
    result = discover_candidates(REAL_MELDEART23_XSD)
    for candidate in result.candidates:
        matches = tree.xpath(candidate.xpath, namespaces={"xs": _XS_NS})
        assert len(matches) == 1, candidate


def test_no_duplicate_xpaths_among_candidates():
    result = discover_candidates(REAL_MELDEART23_XSD)
    xpaths = [c.xpath for c in result.candidates]
    assert len(xpaths) == len(set(xpaths))


def test_candidates_and_excluded_account_for_every_named_node():
    tree = etree.parse(REAL_MELDEART23_XSD)
    # Independent count, written directly here -- not by importing any
    # private helper from discovery.xsd_discoverer, so this test can't
    # pass merely because it shares a bug with the implementation.
    named_node_count = sum(
        1
        for node in tree.iter()
        if isinstance(node.tag, str)
        and node.tag.startswith(f"{{{_XS_NS}}}")
        and node.get("name") is not None
    )

    result = discover_candidates(REAL_MELDEART23_XSD)

    assert named_node_count > 0
    assert len(result.candidates) + len(result.excluded) == named_node_count


def test_discovers_candidates_across_the_full_real_corpus():
    xsd_files = sorted(glob.glob(f"{REAL_XSD_DIR}/*.xsd"))
    assert len(xsd_files) == 13
    for xsd_path in xsd_files:
        result = discover_candidates(xsd_path)
        assert isinstance(result, DiscoveryResult)
        assert len(result.candidates) >= 1, xsd_path


def test_deeply_nested_real_candidate_has_full_multilevel_xpath():
    result = discover_candidates(f"{REAL_XSD_DIR}/MiKaDiv_FM_Meldeart13_1.02.xsd")
    xpaths_by_name = {c.name: c.xpath for c in result.candidates}
    assert xpaths_by_name["Paymentlines"] == (
        "/xs:schema/xs:complexType[@name='Meldeart13']/xs:complexContent"
        "/xs:extension/xs:sequence/xs:element[@name='KontoListe']"
        "/xs:complexType/xs:sequence/xs:element[@name='Konto']"
        "/xs:complexType/xs:sequence/xs:element[@name='Paymentlines']"
    )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/discovery/test_xsd_discoverer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'discovery.xsd_discoverer'`

- [ ] **Step 4: Implement `discovery/xsd_discoverer.py`**

```python
"""Mechanically discovers citable candidates in one real XSD file: every
named XML Schema construct (elements, complexTypes, simpleTypes,
attributes, groups, attributeGroups -- anything with a `name` attribute
in the XML Schema namespace), with no judgment about which ones are
"worth" citing. See docs/specs/2026-09-25-xsd-discovery-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

_XS_NS = "http://www.w3.org/2001/XMLSchema"


@dataclass(frozen=True)
class Candidate:
    tag: str
    name: str
    xpath: str


@dataclass(frozen=True)
class ExcludedCandidate:
    tag: str
    name: str
    xpath: str
    match_count: int


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[Candidate, ...]
    excluded: tuple[ExcludedCandidate, ...]


def _is_named_xsd_construct(node) -> bool:
    return (
        isinstance(node.tag, str)
        and node.tag.startswith(f"{{{_XS_NS}}}")
        and node.get("name") is not None
    )


def _path_step(node) -> str:
    qname = etree.QName(node)
    tag = f"xs:{qname.localname}" if qname.namespace == _XS_NS else qname.localname
    name = node.get("name")
    return f"{tag}[@name='{name}']" if name else tag


def _compute_xpath(node) -> str:
    steps = []
    current = node
    while current is not None:
        steps.append(_path_step(current))
        current = current.getparent()
    return "/" + "/".join(reversed(steps))


def discover_candidates(xsd_path: str) -> DiscoveryResult:
    tree = etree.parse(xsd_path)
    candidates = []
    excluded = []
    for node in tree.iter():
        if not _is_named_xsd_construct(node):
            continue
        xpath = _compute_xpath(node)
        matches = tree.xpath(xpath, namespaces={"xs": _XS_NS})
        tag = etree.QName(node).localname
        name = node.get("name")
        if len(matches) == 1:
            candidates.append(Candidate(tag=tag, name=name, xpath=xpath))
        else:
            excluded.append(
                ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=len(matches))
            )
    return DiscoveryResult(candidates=tuple(candidates), excluded=tuple(excluded))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/discovery/test_xsd_discoverer.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Register the new package**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` section:

```toml
[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*", "webapp*", "references_catalog*", "discovery*"]
```

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
```

Expected: installs successfully (metadata-only update, no new
third-party dependency).

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (160 tests: 153 previously passing, plus 7 new)

- [ ] **Step 8: Commit**

```bash
git add discovery/ tests/discovery/ pyproject.toml
git commit -m "Add discovery.xsd_discoverer: enumerate every named XML Schema construct"
```

---

## Task 2: Synthetic-fixture edge cases

**Files:**
- Create: `tests/discovery/test_xsd_discoverer_edge_cases.py`

**Interfaces:**
- Consumes: `discover_candidates(xsd_path: str) -> DiscoveryResult` (Task 1).
- Produces: nothing new — this task only adds test coverage for behavior
  Task 1's implementation already has, using synthetic fixtures the real
  corpus doesn't happen to exercise.

This task is validation, not new-feature TDD: Task 1's `discover_candidates()`
should already handle every scenario below correctly by construction (the
exclusion path, prefix normalization, and tag-vs-name distinction are all
already implemented, not stubbed). There is no missing behavior to drive
with a RED step. Write each test, then run it for real — a pass confirms
the algorithm actually does what the spec claims; a failure is a genuine
bug in Task 1's implementation that the real corpus didn't happen to
surface, to be fixed via `superpowers:systematic-debugging`, not brushed
aside as "the test must be wrong."

- [ ] **Step 1: Write the tests**

`tests/discovery/test_xsd_discoverer_edge_cases.py`:

```python
from discovery.xsd_discoverer import discover_candidates


def test_ambiguous_synthetic_candidates_are_excluded_with_correct_match_count(tmp_path):
    xsd_path = tmp_path / "ambiguous.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="Ambiguous">
    <xs:choice>
      <xs:sequence>
        <xs:element name="Same" type="xs:string"/>
      </xs:sequence>
      <xs:sequence>
        <xs:element name="Same" type="xs:string"/>
      </xs:sequence>
    </xs:choice>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    same_excluded = [e for e in result.excluded if e.name == "Same"]
    assert len(same_excluded) == 2
    for excluded in same_excluded:
        assert excluded.match_count == 2
        assert excluded.tag == "element"
    assert not any(c.name == "Same" for c in result.candidates)
    assert any(c.name == "Ambiguous" for c in result.candidates)


def test_computed_xpath_always_uses_xs_prefix_regardless_of_source_document_prefix(tmp_path):
    xsd_path = tmp_path / "xsd_prefix.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <xsd:element name="Foo" type="xsd:string"/>
</xsd:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    (candidate,) = result.candidates
    assert candidate.xpath == "/xs:schema/xs:element[@name='Foo']"


def test_ref_based_element_usage_has_no_name_and_is_not_a_candidate(tmp_path):
    xsd_path = tmp_path / "ref_usage.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="RealElement" type="xs:string"/>
  <xs:complexType name="Wrapper">
    <xs:sequence>
      <xs:element ref="RealElement"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    names = {c.name for c in result.candidates}
    assert names == {"RealElement", "Wrapper"}
    assert result.excluded == ()


def test_same_name_different_tag_candidates_are_not_conflated(tmp_path):
    xsd_path = tmp_path / "shared_name.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="Shared">
    <xs:sequence>
      <xs:element name="Shared" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    assert result.excluded == ()
    by_tag = {(c.tag, c.name): c.xpath for c in result.candidates}
    assert by_tag[("complexType", "Shared")] == "/xs:schema/xs:complexType[@name='Shared']"
    assert by_tag[("element", "Shared")] == (
        "/xs:schema/xs:complexType[@name='Shared']/xs:sequence/xs:element[@name='Shared']"
    )
```

- [ ] **Step 2: Run the tests and verify they pass**

Run: `pytest tests/discovery/test_xsd_discoverer_edge_cases.py -v`
Expected: PASS (4 tests). A failure here is a real bug in Task 1's
implementation, not a test-authoring mistake to paper over — use
`superpowers:systematic-debugging` to find and fix the actual cause in
`discovery/xsd_discoverer.py` before continuing.

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (164 tests: 160 from Task 1, plus 4 new)

- [ ] **Step 4: Commit**

```bash
git add tests/discovery/test_xsd_discoverer_edge_cases.py
git commit -m "Add synthetic-fixture edge case tests for discover_candidates()"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `discovery/xsd_discoverer.py` implements `Candidate`,
  `ExcludedCandidate`, `DiscoveryResult`, and `discover_candidates()` with
  the semantics above.
- [ ] All tests pass: `pytest tests/ -v` → 164 passed.
- [ ] `discover_candidates()` on the real `Meldeart23` schema reproduces
  `AORDNR_XPATH`/`ABGEF_XPATH` exactly.
- [ ] `discover_candidates()` runs clean (no exceptions, at least one
  candidate each) across all 13 real XSD files in the corpus.
