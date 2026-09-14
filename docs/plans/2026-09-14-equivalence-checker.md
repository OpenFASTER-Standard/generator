# Equivalence Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the equivalence-checking algorithm in `generator/equivalence/` that proves a graph-generated XSD is behaviorally equivalent to an official one, via bounded-exhaustive/pairwise structural testing plus exact leaf-facet checking — validated with real, hand-crafted synthetic fixtures, not real government XSDs.

**Architecture:** Seven single-responsibility modules: a guardrail that refuses unsupported constructs, a leaf-value generator (boundary-value analysis per facet kind), a structural-case generator (bounded-exhaustive or pairwise, per a configurable ceiling), a document builder (case → real XML fragment), a type-correspondence matcher (by element name, not type name), an identity-constraint comparator, and an orchestrator that ties them together and validates fragments via `xmlschema`.

**Tech Stack:** Python 3.11+, `rdflib` (RDF graph queries), `lxml` (XML fragment construction), `xmlschema` (validation — already a pipeline dependency), `exrex` (regex-matching string generation, new dependency), `allpairspy` (pairwise combination generation, new dependency), `pytest`.

**Spec:** `docs/specs/2026-09-14-equivalence-checker-design.md`

## Global Constraints

- Every RDF vocabulary term used is `https://purl.openfaster.org/xsdo/<Name>` (the `XSDO` namespace) — matches the deprecated project's own real, validated convention, even though the new `xsd-ontology` itself has no curated OWL classes yet (that doesn't block using the vocabulary's URIs directly in RDF graphs and Python code).
- **MVP scope reduction, flagged explicitly, not silently:** `structural_cases.py` handles `xsdo:Sequence` content models only for this plan. `xsdo:Choice`/`xsdo:All` support is an explicit, flagged fast-follow, not part of this plan's Definition of Done — the real schemas are overwhelmingly sequence-based, with `xs:choice` used only in isolated places, so this is a deliberate, bounded scope cut, not an oversight.
- Combinatorial ceiling: full enumeration below 1024 combinations; pairwise coverage (via `allpairspy`) above it.
- `maxOccurs="unbounded"` is treated as a ceiling of 5, never literal unboundedness.
- Every finding/divergence the checker reports must include the literal generated XML document and which schema accepted/rejected it — never an abstract pass/fail with no evidence.
- Any real library API used (especially `xmlschema`'s per-type/per-element validation, which this plan hasn't personally verified against the library's real current interface) must be confirmed against the installed library's actual behavior before being relied on in a test or implementation — verify, don't guess, matching this project's own established norm (a prior version of this codebase shipped a test using a guessed, wrong `xmlschema` facets API and had to fix it after the fact).

## Non-Goals for this plan

Beyond the spec's own Non-Goals (real extraction, real generation, wiring
into any real module — none of that is built here):

- **Validating a matched type that isn't the schema's own document
  root.** Every fixture built in Task 6 tests an element that stands as
  its schema's root (matching `document_builder.build`'s own design,
  which always builds a document root, never an embedded fragment).
  Real modules have plenty of matched types that are nested deep inside
  a larger document (KaFE's real `NatP_Struct` is never itself a
  document root) — validating those needs a different, not-yet-designed
  approach and is deferred to whichever of sub-projects 3/4/5 first
  needs it.
- **The secondary real-document regression corpus** the spec describes.
  It's only meaningful once real submitted documents exist from some
  module's future ingestion work — none do yet, so there's nothing to
  build or test against right now. Revisit once sub-projects 3/4/5
  produce real ingested documents.

---

## Task 1: Preconditions guardrail

**Files:**
- Create: `equivalence/preconditions.py`
- Test: `tests/equivalence/test_preconditions.py`

**Interfaces:**
- Produces: `XSDO` (an `rdflib.Namespace` for `https://purl.openfaster.org/xsdo/`, importable by every other task in this plan), `UnsupportedConstructError` (exception class), `check(graph: rdflib.Graph) -> None` (raises `UnsupportedConstructError` if the graph contains an `xsdo:Assertion` or `xsdo:Wildcard` node — the two component kinds the XSD 1.1 Schema Component Model itself names for `xs:assert` and `xs:any`/`xs:anyAttribute`; raises nothing otherwise).

- [ ] **Step 1: Write the failing tests**

```python
# tests/equivalence/test_preconditions.py
"""Tests for the xs:assert/xs:any guardrail."""
import pytest
from rdflib import RDF, Graph, Namespace

from equivalence.preconditions import XSDO, UnsupportedConstructError, check

EX = Namespace("https://example.org/test/")


def test_check_passes_on_a_graph_with_no_assertion_or_wildcard():
    graph = Graph()
    graph.add((EX.SomeType, RDF.type, XSDO.ComplexTypeDefinition))
    check(graph)  # must not raise


def test_check_raises_on_assertion():
    graph = Graph()
    graph.add((EX.SomeAssertion, RDF.type, XSDO.Assertion))
    with pytest.raises(UnsupportedConstructError):
        check(graph)


def test_check_raises_on_wildcard():
    graph = Graph()
    graph.add((EX.SomeWildcard, RDF.type, XSDO.Wildcard))
    with pytest.raises(UnsupportedConstructError):
        check(graph)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `mkdir -p tests/equivalence && touch tests/equivalence/__init__.py && pytest tests/equivalence/test_preconditions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'equivalence.preconditions'`

- [ ] **Step 3: Write the implementation**

```python
# equivalence/preconditions.py
"""Guardrail: refuses to proceed if a graph contains a construct outside
the decidable fragment this checker's bounded-exhaustive method covers.

xs:assert (arbitrary XPath 2.0 boolean predicates) and xs:any/
xs:anyAttribute (open-content wildcards) are the two XSD constructs that
put correctness checking out of reach here -- neither can be meaningfully
covered by enumerating structural cases and boundary leaf values. This
module is the loud, explicit failure that fires if either ever appears,
rather than silently producing a weaker guarantee.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


class UnsupportedConstructError(Exception):
    """Raised when a graph contains xsdo:Assertion or xsdo:Wildcard."""


def check(graph: Graph) -> None:
    for unsupported_class in (XSDO.Assertion, XSDO.Wildcard):
        if (None, RDF.type, unsupported_class) in graph:
            raise UnsupportedConstructError(
                f"graph contains a {unsupported_class} node -- equivalence "
                "cannot be checked by this method while it's present"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_preconditions.py -v`
Expected: PASS, 3/3

- [ ] **Step 5: Commit**

```bash
git add equivalence/preconditions.py tests/equivalence/
git commit -m "feat: add the xs:assert/xs:any guardrail"
```

---

## Task 2: Leaf boundary-value generation

**Files:**
- Create: `equivalence/leaf_values.py`
- Test: `tests/equivalence/test_leaf_values.py`
- Modify: `pyproject.toml` (add `exrex` dependency)

**Interfaces:**
- Consumes: `XSDO` from Task 1.
- Produces: `LeafValueCase` (frozen dataclass: `value: str`, `should_be_valid: bool`), `generate(graph: rdflib.Graph, simple_type: rdflib.URIRef) -> list[LeafValueCase]` — used by Task 6 (`checker.py`) to get boundary values for each leaf-typed element it tests.

- [ ] **Step 1: Add the `exrex` dependency**

In `pyproject.toml`, add `"exrex>=0.11"` to the `dependencies` list (alongside the existing `rdflib`/`lxml`/`xmlschema`/`openpyxl`).

```bash
pip install -e ".[dev]"
python3 -c "import exrex; print(exrex.getone('[A-Z]{2}[0-9]{4}'))"
```

Expected: prints a string matching the pattern (e.g. `AB1234`) — confirms the library installed and works before writing code against it.

- [ ] **Step 2: Write the failing tests**

```python
# tests/equivalence/test_leaf_values.py
"""Tests for leaf boundary-value generation, one test per facet kind."""
import re

from rdflib import Graph, Literal, Namespace, XSD

from equivalence.leaf_values import XSDO, generate

EX = Namespace("https://example.org/test/")


def _valid_values(cases):
    return {c.value for c in cases if c.should_be_valid}


def _invalid_values(cases):
    return {c.value for c in cases if not c.should_be_valid}


def test_enumeration_facet_returns_every_value_plus_one_rejection():
    graph = Graph()
    graph.add((EX.AnredeEnum, XSDO.hasEnumerationValue, EX.Frau))
    graph.add((EX.Frau, XSDO.literalValue, Literal("FRAU")))
    graph.add((EX.AnredeEnum, XSDO.hasEnumerationValue, EX.Herr))
    graph.add((EX.Herr, XSDO.literalValue, Literal("HERR")))

    cases = generate(graph, EX.AnredeEnum)

    assert _valid_values(cases) == {"FRAU", "HERR"}
    assert len(_invalid_values(cases)) == 1


def test_exact_length_facet_returns_boundary_and_off_by_one_cases():
    graph = Graph()
    graph.add((EX.FixedLen, XSDO.length, Literal(3)))

    cases = generate(graph, EX.FixedLen)

    assert "xxx" in _valid_values(cases)
    assert "xxxx" in _invalid_values(cases)
    assert "xx" in _invalid_values(cases)


def test_min_max_length_facets_return_both_boundaries_and_rejections():
    graph = Graph()
    graph.add((EX.Vorname, XSDO.minLength, Literal(1)))
    graph.add((EX.Vorname, XSDO.maxLength, Literal(80)))

    cases = generate(graph, EX.Vorname)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert "x" in valid  # at minLength
    assert "x" * 80 in valid  # at maxLength
    assert "" in invalid  # below minLength
    assert "x" * 81 in invalid  # above maxLength


def test_pattern_facet_returns_a_matching_and_a_non_matching_value():
    graph = Graph()
    pattern = r"[A-Z]{2}[0-9]{4}"
    graph.add((EX.CodeType, XSDO.pattern, Literal(pattern)))

    cases = generate(graph, EX.CodeType)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert len(valid) == 1
    assert re.fullmatch(pattern, next(iter(valid)))
    assert len(invalid) == 1
    assert not re.fullmatch(pattern, next(iter(invalid)))


def test_numeric_range_facets_return_boundaries_and_out_of_range_values():
    graph = Graph()
    graph.add((EX.SmallInt, XSDO.minInclusive, Literal(0)))
    graph.add((EX.SmallInt, XSDO.maxInclusive, Literal(100)))

    cases = generate(graph, EX.SmallInt)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert "0" in valid
    assert "100" in valid
    assert "-1" in invalid
    assert "101" in invalid


def test_digit_facets_return_a_boundary_and_an_over_precision_value():
    graph = Graph()
    graph.add((EX.Amount, XSDO.totalDigits, Literal(5)))
    graph.add((EX.Amount, XSDO.fractionDigits, Literal(2)))

    cases = generate(graph, EX.Amount)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert any(v.replace(".", "").replace("-", "") for v in valid)
    assert len(invalid) >= 1


def test_unconstrained_type_returns_one_representative_value():
    graph = Graph()
    graph.add((EX.PlainString, XSDO.baseTypeDefinition, XSD.string))

    cases = generate(graph, EX.PlainString)

    assert len(cases) == 1
    assert cases[0].should_be_valid
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/equivalence/test_leaf_values.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'equivalence.leaf_values'`

- [ ] **Step 4: Write the implementation**

```python
# equivalence/leaf_values.py
"""Boundary-value generation for xsdo:SimpleTypeDefinition facets, per
standard boundary-value analysis (Kaner/Myers-style equivalence-class
partitioning) -- not exhaustive enumeration of the underlying domain.
Enumerating "all possible strings" is both intractable and not what
boundary-value analysis calls for; the boundary points are where real
schema-divergence bugs actually live.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import exrex
from rdflib import Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class LeafValueCase:
    value: str
    should_be_valid: bool


def generate(graph: Graph, simple_type: URIRef) -> list[LeafValueCase]:
    enumeration_cases = _enumeration_cases(graph, simple_type)
    if enumeration_cases is not None:
        return enumeration_cases

    length_cases = _length_cases(graph, simple_type)
    if length_cases is not None:
        return length_cases

    pattern_cases = _pattern_cases(graph, simple_type)
    if pattern_cases is not None:
        return pattern_cases

    numeric_cases = _numeric_range_cases(graph, simple_type)
    if numeric_cases is not None:
        return numeric_cases

    digit_cases = _digit_precision_cases(graph, simple_type)
    if digit_cases is not None:
        return digit_cases

    return [LeafValueCase("sample", should_be_valid=True)]


def _enumeration_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    enum_values = list(graph.objects(simple_type, XSDO.hasEnumerationValue))
    if not enum_values:
        return None
    cases = [
        LeafValueCase(str(graph.value(v, XSDO.literalValue)), should_be_valid=True)
        for v in enum_values
    ]
    cases.append(LeafValueCase("__NOT_IN_ENUMERATION__", should_be_valid=False))
    return cases


def _length_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    exact = graph.value(simple_type, XSDO.length)
    min_len = graph.value(simple_type, XSDO.minLength)
    max_len = graph.value(simple_type, XSDO.maxLength)
    if exact is None and min_len is None and max_len is None:
        return None

    cases: list[LeafValueCase] = []
    if exact is not None:
        n = int(exact)
        cases.append(LeafValueCase("x" * n, should_be_valid=True))
        cases.append(LeafValueCase("x" * (n + 1), should_be_valid=False))
        if n > 0:
            cases.append(LeafValueCase("x" * (n - 1), should_be_valid=False))
        return cases

    lo = int(min_len) if min_len is not None else 0
    hi = int(max_len) if max_len is not None else None
    cases.append(LeafValueCase("x" * lo, should_be_valid=True))
    if lo > 0:
        cases.append(LeafValueCase("x" * (lo - 1), should_be_valid=False))
    if hi is not None:
        cases.append(LeafValueCase("x" * hi, should_be_valid=True))
        cases.append(LeafValueCase("x" * (hi + 1), should_be_valid=False))
    return cases


def _pattern_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    pattern = graph.value(simple_type, XSDO.pattern)
    if pattern is None:
        return None
    pattern_str = str(pattern)
    matching = exrex.getone(pattern_str)
    cases = [LeafValueCase(matching, should_be_valid=True)]
    non_matching = matching + "\x00"
    if re.fullmatch(pattern_str, non_matching) is None:
        cases.append(LeafValueCase(non_matching, should_be_valid=False))
    return cases


def _numeric_range_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    min_inclusive = graph.value(simple_type, XSDO.minInclusive)
    max_inclusive = graph.value(simple_type, XSDO.maxInclusive)
    if min_inclusive is None and max_inclusive is None:
        return None

    cases: list[LeafValueCase] = []
    if min_inclusive is not None:
        lo = Decimal(str(min_inclusive))
        cases.append(LeafValueCase(str(lo), should_be_valid=True))
        cases.append(LeafValueCase(str(lo - 1), should_be_valid=False))
    if max_inclusive is not None:
        hi = Decimal(str(max_inclusive))
        cases.append(LeafValueCase(str(hi), should_be_valid=True))
        cases.append(LeafValueCase(str(hi + 1), should_be_valid=False))
    return cases


def _digit_precision_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    total_digits = graph.value(simple_type, XSDO.totalDigits)
    fraction_digits = graph.value(simple_type, XSDO.fractionDigits)
    if total_digits is None and fraction_digits is None:
        return None

    total = int(total_digits) if total_digits is not None else 18
    fraction = int(fraction_digits) if fraction_digits is not None else 0
    integer_digits = max(total - fraction, 1)

    valid = "1" * integer_digits + ("." + "1" * fraction if fraction else "")
    too_much_fraction = "1" * integer_digits + "." + "1" * (fraction + 1)
    return [
        LeafValueCase(valid, should_be_valid=True),
        LeafValueCase(too_much_fraction, should_be_valid=False),
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_leaf_values.py -v`
Expected: PASS, 7/7

- [ ] **Step 6: Commit**

```bash
git add equivalence/leaf_values.py tests/equivalence/test_leaf_values.py pyproject.toml
git commit -m "feat: add leaf boundary-value generation"
```

---

## Task 3: Structural case enumeration

**Files:**
- Create: `equivalence/structural_cases.py`
- Test: `tests/equivalence/test_structural_cases.py`
- Modify: `pyproject.toml` (add `allpairspy` dependency)

**Interfaces:**
- Consumes: `XSDO` from Task 1.
- Produces: `ParticleOccurrence` (frozen dataclass: `term: URIRef`, `count: int`), `StructuralCase` (frozen dataclass: `occurrences: tuple[ParticleOccurrence, ...]`, `should_be_valid: bool`), `enumerate_cases(graph: rdflib.Graph, content_model: rdflib.URIRef) -> list[StructuralCase]` — used by Task 6.
- **MVP scope reduction (see Global Constraints): only `xsdo:Sequence` content models are handled.** If `content_model`'s `rdf:type` is not `xsdo:Sequence`, raise `NotImplementedError` naming the unsupported content-model kind — an explicit, loud failure, not silent wrong output.

- [ ] **Step 1: Add the `allpairspy` dependency**

In `pyproject.toml`, add `"allpairspy>=2.5"` to `dependencies`.

```bash
pip install -e ".[dev]"
python3 -c "from allpairspy import AllPairs; print(list(AllPairs([[1,2],[3,4]])))"
```

Expected: prints a list of pairwise-covering combinations (e.g. `[[1, 3], [1, 4], [2, 3], [2, 4]]` or similar reduced set) — confirms the library installed and works.

- [ ] **Step 2: Write the failing tests**

```python
# tests/equivalence/test_structural_cases.py
"""Tests for bounded-exhaustive/pairwise structural case enumeration."""
import pytest
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.structural_cases import XSDO, enumerate_cases

EX = Namespace("https://example.org/test/")


def _make_particle(graph, particle, term, position, min_occurs, max_occurs, unbounded=False):
    graph.add((particle, XSDO.particlePosition, Literal(position)))
    graph.add((particle, XSDO.minOccurs, Literal(min_occurs)))
    graph.add((particle, XSDO["term"], term))  # bracket access -- see note below
    if unbounded:
        graph.add((particle, XSDO.maxOccursUnbounded, Literal(True)))
    else:
        graph.add((particle, XSDO.maxOccurs, Literal(max_occurs)))


def test_raises_on_non_sequence_content_model():
    graph = Graph()
    graph.add((EX.SomeChoice, RDF.type, XSDO.Choice))
    with pytest.raises(NotImplementedError):
        enumerate_cases(graph, EX.SomeChoice)


def test_single_required_particle_produces_one_valid_case():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=1)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)

    assert len(cases) == 1
    assert cases[0].should_be_valid
    assert cases[0].occurrences == (
        __import__("equivalence.structural_cases", fromlist=["ParticleOccurrence"]).ParticleOccurrence(
            term=EX.FieldA, count=1
        ),
    )


def test_optional_particle_produces_present_and_absent_cases():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=0, max_occurs=1)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert counts == [0, 1]
    assert all(c.should_be_valid for c in cases)


def test_repeating_particle_produces_min_min_plus_one_max_and_over_max():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=3)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert counts == [1, 2, 3, 4]
    valid_by_count = {c.occurrences[0].count: c.should_be_valid for c in cases}
    assert valid_by_count[1] and valid_by_count[2] and valid_by_count[3]
    assert not valid_by_count[4]


def test_unbounded_particle_uses_the_ceiling_not_literal_infinity():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=None, unbounded=True)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert max(counts) == 5  # the fixed ceiling, not a huge or infinite number


def test_many_independent_particles_falls_back_to_pairwise_below_full_count():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    for i in range(15):
        particle = EX[f"P{i}"]
        field = EX[f"Field{i}"]
        _make_particle(graph, particle, field, i, min_occurs=0, max_occurs=1)
        graph.add((EX.Content, XSDO.hasParticle, particle))

    cases = enumerate_cases(graph, EX.Content)

    # 15 independent optional particles = 2**15 = 32768 combinations if
    # fully enumerated -- must be far fewer via pairwise fallback.
    assert len(cases) < 100
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/equivalence/test_structural_cases.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'equivalence.structural_cases'`

- [ ] **Step 4: Write the implementation**

```python
# equivalence/structural_cases.py
"""Bounded-exhaustive / pairwise enumeration of a xsdo:Sequence content
model's structural variations: which optional particles are present, at
which occurrence-count boundary. xsdo:Choice/xsdo:All are an explicit,
flagged fast-follow (see this plan's Global Constraints), not handled
here -- the real schemas are overwhelmingly sequence-based.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from allpairspy import AllPairs
from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

UNBOUNDED_CEILING = 5
FULL_ENUMERATION_CEILING = 1024


@dataclass(frozen=True)
class ParticleOccurrence:
    term: URIRef
    count: int


@dataclass(frozen=True)
class StructuralCase:
    occurrences: tuple[ParticleOccurrence, ...]
    should_be_valid: bool


def _occurrence_options(graph: Graph, particle: URIRef) -> list[tuple[int, bool]]:
    """The occurrence-count boundary points this module actually tests:
    minOccurs itself, minOccurs+1 (only when there's room below the max),
    the effective max, and one past the effective max -- but never a
    below-minimum count (that's a "particle omitted" case, validated
    elsewhere, not this module's job), and never an over-max case for a
    plain 0-or-1 particle or for a genuinely unbounded one (claiming "6
    occurrences is invalid" when the schema permits unbounded repetition
    would be a factually wrong test case, not just a redundant one).

    Two rdflib gotchas to not reintroduce (both hit and root-caused
    while building this function -- see this task's own report):
    `graph.value(...)` returns `None`, never a falsy-but-present value
    like `Literal(0)`, so check `is not None` explicitly rather than
    `... or default` (which silently turns a real `minOccurs=0` into the
    fallback default, since `bool(Literal(0))` is `False`).
    """
    min_occurs_literal = graph.value(particle, XSDO.minOccurs)
    min_occurs = int(min_occurs_literal) if min_occurs_literal is not None else 1

    unbounded = graph.value(particle, XSDO.maxOccursUnbounded)
    is_unbounded = unbounded is not None and str(unbounded).lower() == "true"
    if is_unbounded:
        max_occurs = UNBOUNDED_CEILING
    else:
        max_occurs_literal = graph.value(particle, XSDO.maxOccurs)
        max_occurs = int(max_occurs_literal) if max_occurs_literal is not None else 1

    options: dict[int, bool] = {min_occurs: True}
    if max_occurs > min_occurs:
        options[min_occurs + 1] = True
    options[max_occurs] = True
    if not is_unbounded and max_occurs > 1:
        options[max_occurs + 1] = False
    return sorted(options.items())


def enumerate_cases(graph: Graph, content_model: URIRef) -> list[StructuralCase]:
    if (content_model, RDF.type, XSDO.Sequence) not in graph:
        actual_type = graph.value(content_model, RDF.type)
        raise NotImplementedError(
            f"structural_cases only handles xsdo:Sequence content models, "
            f"got {actual_type}"
        )

    particles = sorted(
        graph.objects(content_model, XSDO.hasParticle),
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )
    # XSDO["term"], not XSDO.term: rdflib.Namespace has a real built-in
    # .term() method, which attribute access resolves to instead of
    # building a URIRef -- bracket access avoids it.
    terms = [graph.value(p, XSDO["term"]) for p in particles]
    per_particle_options = [_occurrence_options(graph, p) for p in particles]

    total_combinations = 1
    for options in per_particle_options:
        total_combinations *= len(options)

    if total_combinations <= FULL_ENUMERATION_CEILING:
        combos = list(product(*per_particle_options))
    else:
        combos = list(AllPairs(per_particle_options))

    cases = []
    for combo in combos:
        occurrences = tuple(
            ParticleOccurrence(term=term, count=count)
            for term, (count, _valid) in zip(terms, combo)
        )
        should_be_valid = all(valid for _count, valid in combo)
        cases.append(StructuralCase(occurrences=occurrences, should_be_valid=should_be_valid))
    return cases
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_structural_cases.py -v`
Expected: PASS, 6/6

- [ ] **Step 6: Commit**

```bash
git add equivalence/structural_cases.py tests/equivalence/test_structural_cases.py pyproject.toml
git commit -m "feat: add bounded-exhaustive/pairwise structural case enumeration"
```

---

## Task 4: Document builder

**Files:**
- Create: `equivalence/document_builder.py`
- Test: `tests/equivalence/test_document_builder.py`

**Interfaces:**
- Consumes: `XSDO` from Task 1; `StructuralCase`, `ParticleOccurrence` from Task 3.
- Produces: `build(graph: rdflib.Graph, root_element: rdflib.URIRef, target_namespace: str, case: StructuralCase, leaf_values: dict[URIRef, str]) -> bytes` — a well-formed, namespace-qualified XML fragment for one structural case, used by Task 6.

- [ ] **Step 1: Write the failing tests**

```python
# tests/equivalence/test_document_builder.py
"""Tests for building a real XML fragment from a structural case."""
from lxml import etree
from rdflib import Graph, Literal, Namespace

from equivalence.document_builder import build
from equivalence.structural_cases import ParticleOccurrence, StructuralCase

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
EX = Namespace("https://example.org/test/")
NS = "urn:example:test:v1"


def test_build_produces_namespace_qualified_root_and_children():
    graph = Graph()
    graph.add((EX.NatPStruct, XSDO.name, Literal("NatPStruct")))
    graph.add((EX.Vorname, XSDO.name, Literal("Vorname")))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Vorname, count=1),),
        should_be_valid=True,
    )
    xml_bytes = build(
        graph, EX.NatPStruct, NS, case, leaf_values={EX.Vorname: "Hans"}
    )

    root = etree.fromstring(xml_bytes)
    assert root.tag == f"{{{NS}}}NatPStruct"
    children = list(root)
    assert len(children) == 1
    assert children[0].tag == f"{{{NS}}}Vorname"
    assert children[0].text == "Hans"


def test_build_repeats_a_particle_the_requested_number_of_times():
    graph = Graph()
    graph.add((EX.Root, XSDO.name, Literal("Root")))
    graph.add((EX.Item, XSDO.name, Literal("Item")))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Item, count=3),),
        should_be_valid=True,
    )
    xml_bytes = build(graph, EX.Root, NS, case, leaf_values={EX.Item: "x"})

    root = etree.fromstring(xml_bytes)
    assert len(list(root)) == 3
    assert all(c.tag == f"{{{NS}}}Item" for c in root)


def test_build_omits_a_particle_with_zero_count():
    graph = Graph()
    graph.add((EX.Root, XSDO.name, Literal("Root")))
    graph.add((EX.Optional, XSDO.name, Literal("Optional")))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Optional, count=0),),
        should_be_valid=True,
    )
    xml_bytes = build(graph, EX.Root, NS, case, leaf_values={})

    root = etree.fromstring(xml_bytes)
    assert len(list(root)) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/equivalence/test_document_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'equivalence.document_builder'`

- [ ] **Step 3: Write the implementation**

```python
# equivalence/document_builder.py
"""(structural case, leaf value choices) -> a real, well-formed,
namespace-qualified XML fragment, for validating one complex type's
shape independently of the rest of a real document.
"""
from __future__ import annotations

from lxml import etree
from rdflib import Graph, Namespace, URIRef

from equivalence.structural_cases import StructuralCase

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


def build(
    graph: Graph,
    root_element: URIRef,
    target_namespace: str,
    case: StructuralCase,
    leaf_values: dict[URIRef, str],
) -> bytes:
    nsmap = {"tns": target_namespace}
    root_name = str(graph.value(root_element, XSDO.name))
    root = etree.Element(f"{{{target_namespace}}}{root_name}", nsmap=nsmap)

    for occurrence in case.occurrences:
        term_name = str(graph.value(occurrence.term, XSDO.name))
        for _ in range(occurrence.count):
            child = etree.SubElement(root, f"{{{target_namespace}}}{term_name}")
            if occurrence.term in leaf_values:
                child.text = leaf_values[occurrence.term]

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_document_builder.py -v`
Expected: PASS, 3/3

- [ ] **Step 5: Commit**

```bash
git add equivalence/document_builder.py tests/equivalence/test_document_builder.py
git commit -m "feat: add XML fragment builder for structural cases"
```

---

## Task 5: Type correspondence and identity constraints

**Files:**
- Create: `equivalence/type_correspondence.py`
- Create: `equivalence/identity_constraints.py`
- Test: `tests/equivalence/test_type_correspondence.py`
- Test: `tests/equivalence/test_identity_constraints.py`

**Interfaces:**
- Consumes: `XSDO` from Task 1.
- Produces: `MatchResult` (frozen dataclass: `matched: list[tuple[URIRef, URIRef]]` — pairs of (official element, generated element); `official_only: list[URIRef]`; `generated_only: list[URIRef]`), `match(official_graph: Graph, generated_graph: Graph) -> MatchResult` — used by Task 6. Also `IdentityConstraintMismatch` (frozen dataclass: `constraint_kind: str`, `official_selector: str | None`, `generated_selector: str | None`, `official_detail: str | None`, `generated_detail: str | None` — `*_detail` carries per-constraint field-list/`refer` info so a mismatch stays human-readable even when only fields or `refer` differ, not the selector), `compare(official_graph: Graph, generated_graph: Graph, official_type: URIRef, generated_type: URIRef) -> list[IdentityConstraintMismatch]` — empty list means the two types' identity constraints match exactly (all fields of every xs:key/xs:unique/xs:keyref of each kind, plus xs:keyref's `refer`, not just its selector).

- [ ] **Step 1: Write the failing tests**

```python
# tests/equivalence/test_type_correspondence.py
"""Tests for matching ElementDeclarations across two graphs by name."""
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.type_correspondence import XSDO, match

EX = Namespace("https://example.org/test/")


def _element(graph, uri, name):
    graph.add((uri, RDF.type, XSDO.ElementDeclaration))
    graph.add((uri, XSDO.name, Literal(name)))


def test_elements_with_the_same_name_are_matched():
    official = Graph()
    _element(official, EX.OffVorname, "Vorname")
    generated = Graph()
    _element(generated, EX.GenVorname, "Vorname")

    result = match(official, generated)

    assert result.matched == [(EX.OffVorname, EX.GenVorname)]
    assert result.official_only == []
    assert result.generated_only == []


def test_element_only_in_official_is_reported_as_official_only():
    official = Graph()
    _element(official, EX.OffTitel, "Titel")
    generated = Graph()

    result = match(official, generated)

    assert result.matched == []
    assert result.official_only == [EX.OffTitel]


def test_element_only_in_generated_is_reported_as_generated_only():
    official = Graph()
    generated = Graph()
    _element(generated, EX.GenExtra, "Extra")

    result = match(official, generated)

    assert result.matched == []
    assert result.generated_only == [EX.GenExtra]
```

```python
# tests/equivalence/test_identity_constraints.py
"""Tests for direct xs:key/xs:unique/xs:keyref comparison."""
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.identity_constraints import XSDO, compare

EX = Namespace("https://example.org/test/")


def _key(graph, type_uri, constraint_uri, kind, selector, field):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, kind))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    graph.add((constraint_uri, XSDO.field, Literal(field)))


def _key_multi_field(graph, type_uri, constraint_uri, kind, selector, fields):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, kind))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    for field in fields:
        graph.add((constraint_uri, XSDO.field, Literal(field)))


def _keyref(graph, type_uri, constraint_uri, selector, fields, refer):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, XSDO.KeyRef))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    for field in fields:
        graph.add((constraint_uri, XSDO.field, Literal(field)))
    graph.add((constraint_uri, XSDO.refer, Literal(refer)))


def test_identical_key_constraints_produce_no_mismatches():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []


def test_differing_selector_is_reported_as_a_mismatch():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Item", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].official_selector == "./Row"
    assert mismatches[0].generated_selector == "./Item"


def test_constraint_present_only_on_official_side_is_a_mismatch():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].generated_selector is None


def test_multiple_constraints_of_same_kind_are_all_compared():
    """A single-entry-per-kind model (the original bug fixed in commit
    3553a2a) would let one matching constraint of a kind mask another,
    unmatched one of the same kind on the same type -- e.g. two xs:key
    declarations on the same complex type. Every constraint of a kind
    must be compared as a set, not just "the" one."""
    official = Graph()
    _key(official, EX.OffType, EX.OffKey1, XSDO.Key, "./Row", "@id")
    _key(official, EX.OffType, EX.OffKey2, XSDO.Key, "./Item", "business_key")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].constraint_kind == str(XSDO.Key)
    assert "./Row" in mismatches[0].official_selector
    assert "./Item" in mismatches[0].official_selector
    assert mismatches[0].generated_selector == "./Row"


def test_composite_key_missing_a_field_is_caught_as_a_mismatch():
    """A real xs:key/xs:unique can have more than one xs:field child (a
    composite key) -- collecting only the first field (graph.value
    instead of graph.objects) would make a mismatch in the second-or-later
    field invisible."""
    official = Graph()
    _key_multi_field(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", ["@id", "@type"])
    generated = Graph()
    _key_multi_field(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", ["@id"])

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].official_selector == "./Row"
    assert mismatches[0].generated_selector == "./Row"
    assert "@type" in mismatches[0].official_detail
    assert "@type" not in (mismatches[0].generated_detail or "")


def test_composite_key_with_identical_fields_in_different_order_matches():
    official = Graph()
    _key_multi_field(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", ["@type", "@id"])
    generated = Graph()
    _key_multi_field(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", ["@id", "@type"])

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []


def test_keyref_with_differing_refer_is_caught_as_a_mismatch():
    """Two xs:keyrefs with the same selector/field but a different
    `refer` target reference different keys and are not equivalent --
    `refer` must actually be compared, not silently dropped."""
    official = Graph()
    _keyref(official, EX.OffType, EX.OffKeyRef, "./Row", ["@id"], "OffKey")
    generated = Graph()
    _keyref(generated, EX.GenType, EX.GenKeyRef, "./Row", ["@id"], "GenKey")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].constraint_kind == str(XSDO.KeyRef)
    assert "OffKey" in mismatches[0].official_detail
    assert "GenKey" in mismatches[0].generated_detail


def test_keyref_with_identical_refer_matches():
    official = Graph()
    _keyref(official, EX.OffType, EX.OffKeyRef, "./Row", ["@id"], "SharedKey")
    generated = Graph()
    _keyref(generated, EX.GenType, EX.GenKeyRef, "./Row", ["@id"], "SharedKey")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/equivalence/test_type_correspondence.py tests/equivalence/test_identity_constraints.py -v`
Expected: FAIL with `ModuleNotFoundError` for both new modules

- [ ] **Step 3: Write the implementations**

```python
# equivalence/type_correspondence.py
"""Matches xsdo:ElementDeclarations across two graphs by their real XSD
element name -- not by type name, since the generated graph is allowed
to organize/name its types differently than the official schema. Any
official element with no same-named counterpart, or vice versa, is
reported explicitly, never silently skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class MatchResult:
    matched: list[tuple[URIRef, URIRef]] = field(default_factory=list)
    official_only: list[URIRef] = field(default_factory=list)
    generated_only: list[URIRef] = field(default_factory=list)


def _elements_by_name(graph: Graph) -> dict[str, URIRef]:
    result = {}
    for element in graph.subjects(RDF.type, XSDO.ElementDeclaration):
        name = graph.value(element, XSDO.name)
        result[str(name)] = element
    return result


def match(official_graph: Graph, generated_graph: Graph) -> MatchResult:
    official_by_name = _elements_by_name(official_graph)
    generated_by_name = _elements_by_name(generated_graph)

    matched = []
    official_only = []
    for name, official_element in official_by_name.items():
        if name in generated_by_name:
            matched.append((official_element, generated_by_name[name]))
        else:
            official_only.append(official_element)

    generated_only = [
        element
        for name, element in generated_by_name.items()
        if name not in official_by_name
    ]

    return MatchResult(matched=matched, official_only=official_only, generated_only=generated_only)
```

```python
# equivalence/identity_constraints.py
"""Direct comparison of xs:key/xs:unique/xs:keyref declarations between
two matched complex types. XSD restricts an identity constraint's
selector/field to a narrow, non-Turing-complete XPath subset, so direct
structural comparison is exact here, not heuristic -- unlike xs:assert's
arbitrary predicates, which preconditions.py refuses to handle at all.

Two things a real xs:key/xs:unique/xs:keyref can do that a naive
"one selector, one field" model misses:

- A composite key (xs:key/xs:unique with more than one xs:field child)
  is a real, common XSD pattern. Collecting only ONE field per constraint
  (via graph.value, which just returns some one object) silently drops
  every field past the first, so a mismatch in a composite key's second
  (or later) field would never be detected.
- xs:keyref's `refer` attribute (which key/unique constraint it points at)
  is part of its identity too: two keyrefs with the same selector/fields
  but different `refer` targets are not equivalent, but comparing only
  selector+fields would say they are.

(This module was fixed once already, in commit 3553a2a, to compare ALL
identity constraints of a given kind on a type -- not just "the" one --
after the original `dict[str, tuple[str, str]]` shape let a second
constraint of the same kind silently mask the first. The two field/refer
issues above are a second, deeper fix to the same file, at the level of
one individual constraint's own data rather than how many constraints of
a kind there can be.)
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class IdentityConstraintMismatch:
    constraint_kind: str
    official_selector: str | None
    generated_selector: str | None
    official_detail: str | None = None
    generated_detail: str | None = None


@dataclass(frozen=True)
class _ConstraintEntry:
    selector: str
    fields: tuple[str, ...]
    refer: str | None = None


def _constraint_entry(graph: Graph, constraint: URIRef, kind: str) -> _ConstraintEntry:
    selector = str(graph.value(constraint, XSDO.selector))
    fields = tuple(sorted(str(f) for f in graph.objects(constraint, XSDO.field)))
    refer = None
    if kind == str(XSDO.KeyRef):
        refer_value = graph.value(constraint, XSDO.refer)
        refer = str(refer_value) if refer_value is not None else None
    return _ConstraintEntry(selector=selector, fields=fields, refer=refer)


def _constraints_by_kind(graph: Graph, type_uri: URIRef) -> dict[str, list[_ConstraintEntry]]:
    result: dict[str, list[_ConstraintEntry]] = {}
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        kind = str(graph.value(constraint, RDF.type))
        result.setdefault(kind, []).append(_constraint_entry(graph, constraint, kind))
    return result


def _describe_selectors(entries: list[_ConstraintEntry]) -> str | None:
    if not entries:
        return None
    return ", ".join(sorted(entry.selector for entry in entries))


def _format_entry(entry: _ConstraintEntry) -> str:
    text = f"{entry.selector} [{', '.join(entry.fields)}]"
    if entry.refer is not None:
        text += f" refer={entry.refer}"
    return text


def _describe_detail(entries: list[_ConstraintEntry]) -> str | None:
    if not entries:
        return None
    return ", ".join(sorted(_format_entry(entry) for entry in entries))


def compare(
    official_graph: Graph,
    generated_graph: Graph,
    official_type: URIRef,
    generated_type: URIRef,
) -> list[IdentityConstraintMismatch]:
    official_constraints = _constraints_by_kind(official_graph, official_type)
    generated_constraints = _constraints_by_kind(generated_graph, generated_type)

    mismatches = []
    all_kinds = set(official_constraints) | set(generated_constraints)
    for kind in all_kinds:
        official_entries = official_constraints.get(kind, [])
        generated_entries = generated_constraints.get(kind, [])
        if set(official_entries) != set(generated_entries):
            mismatches.append(
                IdentityConstraintMismatch(
                    constraint_kind=kind,
                    official_selector=_describe_selectors(official_entries),
                    generated_selector=_describe_selectors(generated_entries),
                    official_detail=_describe_detail(official_entries),
                    generated_detail=_describe_detail(generated_entries),
                )
            )
    return mismatches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_type_correspondence.py tests/equivalence/test_identity_constraints.py -v`
Expected: PASS, 11/11 (3 in `test_type_correspondence.py` + 8 in `test_identity_constraints.py`)

- [ ] **Step 5: Commit**

```bash
git add equivalence/type_correspondence.py equivalence/identity_constraints.py tests/equivalence/test_type_correspondence.py tests/equivalence/test_identity_constraints.py
git commit -m "feat: add type correspondence matching and identity-constraint comparison"
```

---

## Task 6: Orchestrator (checker.py)

**Files:**
- Create: `equivalence/checker.py`
- Test: `tests/equivalence/test_checker.py`
- Test fixtures: `tests/equivalence/fixtures/equivalent_official.ttl`, `tests/equivalence/fixtures/equivalent_generated.ttl`, `tests/equivalence/fixtures/divergent_official.ttl`, `tests/equivalence/fixtures/divergent_generated.ttl`, `tests/equivalence/fixtures/unmatched_type_official.ttl`, `tests/equivalence/fixtures/assertion_official.ttl`, `tests/equivalence/fixtures/*.xsd` (real, hand-written XSD files matching each `.ttl` pair, used as the actual schemas `xmlschema` validates against)

**Interfaces:**
- Consumes: everything from Tasks 1-5 (`preconditions.check`, `leaf_values.generate`, `structural_cases.enumerate_cases`, `document_builder.build`, `type_correspondence.match`, `identity_constraints.compare`).
- Produces: `Divergence` (frozen dataclass: `element_name: str`, `xml_document: bytes`, `official_verdict: bool`, `generated_verdict: bool`, `official_error: str | None`, `generated_error: str | None`), `Report` (frozen dataclass: `divergences: list[Divergence]`, `unmatched_official: list[str]`, `unmatched_generated: list[str]`, `identity_constraint_mismatches: list`, `confidence_note: str` — always set to the exact sentence from this plan's Global Constraints, never omitted), `check_equivalence(official_xsd_path: str, generated_xsd_path: str, official_graph: Graph, generated_graph: Graph) -> Report`.

**Scope note carried into this task's Non-Goals below: this task only validates a matched element when it can stand as the schema's own document root** (exactly what every fixture in Step 2 is built as — `document_builder.build`'s own `root_element` parameter always builds its output as a document root, not an embedded fragment). Validating a type that's nested deep inside a larger real document — e.g. KaFE's real `NatP_Struct`, which is never itself a document root — needs a different, not-yet-designed validation approach and is explicitly deferred to whichever of sub-projects 3/4/5 first needs it, not solved here.

- [ ] **Step 1: Confirm the real `xmlschema` whole-document validation API**

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('/dev/stdin')
" <<'EOF'
<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="X" type="xs:string"/></xs:schema>
EOF
python3 -c "
import xmlschema
help(xmlschema.XMLSchema.is_valid)
"
```

Confirm `is_valid` accepts a schema instance loaded from a file path and an XML source (bytes or a string of XML), returning a plain `bool`. If the installed version's real signature differs from `schema.is_valid(xml_source)`, adjust Step 5's implementation below to match what you actually found — do not silently keep code that calls a nonexistent method.

- [ ] **Step 2: Write the hand-crafted fixture files**

`tests/equivalence/fixtures/equivalent_official.xsd` and `equivalent_generated.xsd` (identical on purpose, to prove the checker reports no divergence for truly equivalent schemas):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:example:test:v1"
           xmlns:tns="urn:example:test:v1"
           elementFormDefault="qualified">
  <xs:element name="Person">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Vorname" minOccurs="1" maxOccurs="1">
          <xs:simpleType>
            <xs:restriction base="xs:string">
              <xs:minLength value="1"/>
              <xs:maxLength value="80"/>
            </xs:restriction>
          </xs:simpleType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
```

Copy this file verbatim to both `equivalent_official.xsd` and `equivalent_generated.xsd`.

`tests/equivalence/fixtures/equivalent_official.ttl`:

```turtle
@prefix xsdo: <https://purl.openfaster.org/xsdo/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <https://example.org/test/> .

ex:PersonType a xsdo:ComplexTypeDefinition ;
    xsdo:targetNamespace "urn:example:test:v1"^^xsd:anyURI ;
    xsdo:contentModel [
        a xsdo:Sequence ;
        xsdo:hasParticle [
            xsdo:particlePosition 1 ;
            xsdo:minOccurs 1 ;
            xsdo:maxOccurs 1 ;
            xsdo:term ex:Vorname
        ]
    ] .

ex:Person a xsdo:ElementDeclaration ;
    xsdo:name "Person" ;
    xsdo:type ex:PersonType .

ex:Vorname a xsdo:ElementDeclaration ;
    xsdo:name "Vorname" ;
    xsdo:type ex:VornameType .

ex:VornameType a xsdo:SimpleTypeDefinition ;
    xsdo:minLength 1 ;
    xsdo:maxLength 80 .
```

Copy this file verbatim to `equivalent_generated.ttl` too (same graph shape on both sides — proves the "no divergence" path).

`tests/equivalence/fixtures/divergent_official.xsd` — same shape as above but `maxLength` is `80`. `divergent_generated.xsd` — identical except `maxLength` is `60` (a genuine, deliberate divergence). `divergent_official.ttl`/`divergent_generated.ttl` — same graph shape as the equivalent fixtures, but `divergent_generated.ttl`'s `ex:VornameType` has `xsdo:maxLength 60` instead of `80`.

`tests/equivalence/fixtures/unmatched_type_official.ttl` — same as `equivalent_official.ttl` plus one extra `ElementDeclaration` (`ex:Nachname`, name `"Nachname"`) that isn't in any generated-side fixture. (The test below reuses `equivalent_official.ttl` directly as the "generated" side, since it's already missing `Nachname` — no separate `unmatched_type_generated.ttl` file is needed.)

`tests/equivalence/fixtures/assertion_official.ttl` — same shape as `equivalent_official.ttl`, plus one extra triple: `ex:PersonType xsdo:contentModel [ ... ] .` unchanged, but add a standalone node `ex:SomeAssertion a xsdo:Assertion .` anywhere in the same file, to prove the guardrail fires at the `check_equivalence` integration level, not just in Task 1's own isolated unit test of `preconditions.check`.

- [ ] **Step 3: Write the failing tests**

```python
# tests/equivalence/test_checker.py
"""Integration tests for the orchestrator, against small hand-crafted
fixtures -- not real government XSDs (see this plan's spec, Testing
strategy)."""
import pathlib

from rdflib import Graph

from equivalence.checker import check_equivalence

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name: str) -> Graph:
    graph = Graph()
    graph.parse(FIXTURES / name, format="turtle")
    return graph


def test_truly_equivalent_schemas_produce_no_divergences():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
        official_graph=_load("equivalent_official.ttl"),
        generated_graph=_load("equivalent_official.ttl"),
    )

    assert report.divergences == []
    assert report.unmatched_official == []
    assert report.unmatched_generated == []
    assert report.confidence_note  # must always be set, never blank


def test_divergent_max_length_is_caught_with_a_concrete_counterexample():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "divergent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "divergent_generated.xsd"),
        official_graph=_load("divergent_official.ttl"),
        generated_graph=_load("divergent_generated.ttl"),
    )

    assert len(report.divergences) >= 1
    divergence = report.divergences[0]
    assert divergence.xml_document  # the literal generated document is included
    assert divergence.official_verdict != divergence.generated_verdict


def test_unmatched_type_is_reported_not_silently_skipped():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
        official_graph=_load("unmatched_type_official.ttl"),
        generated_graph=_load("equivalent_official.ttl"),
    )

    assert "Nachname" in report.unmatched_official


def test_guardrail_fires_at_the_integration_level_not_just_in_isolation():
    """preconditions.check has its own unit test (Task 1) proving it
    raises in isolation -- this proves check_equivalence actually calls
    it and doesn't swallow the error."""
    import pytest

    from equivalence.preconditions import UnsupportedConstructError

    with pytest.raises(UnsupportedConstructError):
        check_equivalence(
            official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
            generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
            official_graph=_load("assertion_official.ttl"),
            generated_graph=_load("equivalent_official.ttl"),
        )
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/equivalence/test_checker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'equivalence.checker'`

- [ ] **Step 5: Write the implementation**

```python
# equivalence/checker.py
"""Orchestrator: ties preconditions, type correspondence, leaf values,
structural cases, document building, and identity constraints together
into one equivalence check, producing a Report with a concrete
counterexample for every divergence found.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import xmlschema
from rdflib import RDF, Graph, Namespace, URIRef

from equivalence import identity_constraints, preconditions, type_correspondence
from equivalence.document_builder import build
from equivalence.leaf_values import generate as generate_leaf_values
from equivalence.structural_cases import enumerate_cases

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

CONFIDENCE_NOTE = (
    "No counterexample found across an exhaustively enumerated (or "
    "rigorously pairwise-covered) structural scope, combined with exact "
    "leaf-facet boundary checking and exact identity-constraint "
    "comparison. This is not a completeness proof over all possible XML "
    "documents."
)


@dataclass(frozen=True)
class Divergence:
    element_name: str
    xml_document: bytes
    official_verdict: bool
    generated_verdict: bool
    official_error: str | None
    generated_error: str | None


@dataclass(frozen=True)
class Report:
    divergences: list[Divergence] = field(default_factory=list)
    unmatched_official: list[str] = field(default_factory=list)
    unmatched_generated: list[str] = field(default_factory=list)
    identity_constraint_mismatches: list = field(default_factory=list)
    confidence_note: str = CONFIDENCE_NOTE


def _target_namespace(graph: Graph, type_uri: URIRef) -> str:
    ns = graph.value(type_uri, XSDO.targetNamespace)
    return str(ns) if ns is not None else ""


def _leaf_children(graph: Graph, content_model: URIRef) -> list[URIRef]:
    """Direct child ElementDeclarations of a Sequence content model that
    are themselves simple-typed (leaves, not nested complex types)."""
    leaves = []
    for particle in graph.objects(content_model, XSDO.hasParticle):
        # XSDO["term"], not XSDO.term: rdflib.Namespace has a real
        # built-in .term() method, which attribute access resolves to
        # instead of building a URIRef -- a real bug Task 3 hit and
        # documented (see its report). Bracket access avoids it.
        term = graph.value(particle, XSDO["term"])
        term_type = graph.value(term, XSDO.type)
        if term_type is not None and (term_type, RDF.type, XSDO.SimpleTypeDefinition) in graph:
            leaves.append(term)
    return leaves


def _validate(schema: xmlschema.XMLSchema, xml_document: bytes) -> tuple[bool, str | None]:
    """True/None on success. On failure, get a human-readable message by
    calling validate() (which raises) only on the already-known failure
    path -- cheap, and never assumes an exact exception class name."""
    if schema.is_valid(xml_document):
        return True, None
    try:
        schema.validate(xml_document)
    except Exception as error:
        return False, str(error)
    return False, "invalid, but validate() raised no exception"


def _check_one_document(
    element_name: str,
    xml_document: bytes,
    official_schema: xmlschema.XMLSchema,
    generated_schema: xmlschema.XMLSchema,
) -> Divergence | None:
    official_valid, official_error = _validate(official_schema, xml_document)
    generated_valid, generated_error = _validate(generated_schema, xml_document)
    if official_valid == generated_valid:
        return None
    return Divergence(
        element_name=element_name,
        xml_document=xml_document,
        official_verdict=official_valid,
        generated_verdict=generated_valid,
        official_error=official_error,
        generated_error=generated_error,
    )


def check_equivalence(
    official_xsd_path: str,
    generated_xsd_path: str,
    official_graph: Graph,
    generated_graph: Graph,
) -> Report:
    preconditions.check(official_graph)
    preconditions.check(generated_graph)

    official_schema = xmlschema.XMLSchema(official_xsd_path)
    generated_schema = xmlschema.XMLSchema(generated_xsd_path)

    match_result = type_correspondence.match(official_graph, generated_graph)

    divergences: list[Divergence] = []
    mismatches = []

    for official_element, generated_element in match_result.matched:
        official_type = official_graph.value(official_element, XSDO.type)
        generated_type = generated_graph.value(generated_element, XSDO.type)
        element_name = str(official_graph.value(official_element, XSDO.name))

        mismatches.extend(
            identity_constraints.compare(
                official_graph, generated_graph, official_type, generated_type
            )
        )

        official_content_model = official_graph.value(official_type, XSDO.contentModel)
        if official_content_model is None:
            continue  # a simple-typed root element has no structure to vary

        cases = enumerate_cases(official_graph, official_content_model)
        leaf_terms = _leaf_children(official_graph, official_content_model)
        namespace = _target_namespace(official_graph, official_type)

        # One-factor-at-a-time boundary testing, not a full cross-product
        # of every structural case with every leaf's every candidate
        # value (which would both explode combinatorially and, worse,
        # would still risk under-testing if reduced naively). Two passes:
        # (1) vary structural cases while every leaf sits at its own
        # baseline (first should-be-valid) value; (2) vary each leaf's
        # own full candidate set (including its rejection-boundary
        # values) one leaf at a time, holding structure at a single
        # baseline case. A leaf-value bug (e.g. a maxLength mismatch)
        # would never surface if only ever tested at its baseline value
        # -- this is what pass (2) exists to catch.
        leaf_candidates: dict[URIRef, list] = {}
        baseline_leaf_values: dict[URIRef, str] = {}
        for leaf_term in leaf_terms:
            leaf_type = official_graph.value(leaf_term, XSDO.type)
            candidates = generate_leaf_values(official_graph, leaf_type)
            leaf_candidates[leaf_term] = candidates
            baseline_leaf_values[leaf_term] = next(
                c.value for c in candidates if c.should_be_valid
            )

        for case in cases:
            xml_document = build(
                official_graph, official_element, namespace, case, baseline_leaf_values
            )
            divergence = _check_one_document(
                element_name, xml_document, official_schema, generated_schema
            )
            if divergence is not None:
                divergences.append(divergence)

        baseline_case = next(c for c in cases if c.should_be_valid)
        for leaf_term, candidates in leaf_candidates.items():
            for candidate in candidates:
                leaf_values = dict(baseline_leaf_values)
                leaf_values[leaf_term] = candidate.value
                xml_document = build(
                    official_graph, official_element, namespace, baseline_case, leaf_values
                )
                divergence = _check_one_document(
                    element_name, xml_document, official_schema, generated_schema
                )
                if divergence is not None:
                    divergences.append(divergence)

    return Report(
        divergences=divergences,
        unmatched_official=[
            str(official_graph.value(e, XSDO.name)) for e in match_result.official_only
        ],
        unmatched_generated=[
            str(generated_graph.value(e, XSDO.name)) for e in match_result.generated_only
        ],
        identity_constraint_mismatches=mismatches,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/equivalence/test_checker.py -v`
Expected: PASS, 4/4

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests across all 6 tasks pass, pristine output (no warnings)

- [ ] **Step 8: Commit**

```bash
git add equivalence/checker.py tests/equivalence/test_checker.py tests/equivalence/fixtures/
git commit -m "feat: add equivalence-checker orchestrator, wiring all components together"
```

---

## Task 7: Package export and README

**Files:**
- Modify: `equivalence/__init__.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: `equivalence.check_equivalence`, `equivalence.Report`, `equivalence.Divergence`, `equivalence.UnsupportedConstructError` importable directly from the package root (not just from their individual submodules) — the public interface later sub-projects (3/4/5) will actually import from.

- [ ] **Step 1: Write the failing test**

```python
# tests/equivalence/test_package_exports.py
"""The public interface later sub-projects import must be stable and
importable from the package root, not just individual submodules."""
def test_public_names_are_importable_from_the_package_root():
    from equivalence import (
        Divergence,
        Report,
        UnsupportedConstructError,
        check_equivalence,
    )

    assert callable(check_equivalence)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/equivalence/test_package_exports.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Update `equivalence/__init__.py`**

```python
"""OpenFASTER generator: equivalence package.

Proves a graph-generated XSD is behaviorally equivalent to an official
one, via bounded-exhaustive/pairwise structural testing and exact
leaf-facet checking. See docs/specs/2026-09-14-equivalence-checker-design.md
for the full design and its confidence characterization.
"""
from equivalence.checker import Divergence, Report, check_equivalence
from equivalence.preconditions import UnsupportedConstructError

__all__ = [
    "Divergence",
    "Report",
    "UnsupportedConstructError",
    "check_equivalence",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/equivalence/test_package_exports.py -v`
Expected: PASS

- [ ] **Step 5: Update `README.md`'s `equivalence/` bullet**

Replace the existing one-line `equivalence/` description with:

```markdown
- `equivalence/` -- proves a generated XSD is behaviorally equivalent to
  an official one, via bounded-exhaustive/pairwise structural testing
  and exact leaf-facet checking (not document sampling, not a formal
  completeness proof either -- see `docs/specs/2026-09-14-equivalence-checker-design.md`
  for the exact confidence characterization). Public interface:
  `check_equivalence`, `Report`, `Divergence`, `UnsupportedConstructError`.
```

Also remove the top-level "Status: skeleton only, no pipeline logic implemented yet." line if it now only applies to the other three packages — replace with a line noting `equivalence/` is implemented, `extraction/`/`generation/`/`ingestion/` are not yet.

- [ ] **Step 6: Run the full test suite one final time**

Run: `pytest tests/ -v`
Expected: all tests pass, pristine output

- [ ] **Step 7: Commit and push**

```bash
git add equivalence/__init__.py README.md tests/equivalence/test_package_exports.py
git commit -m "feat: export equivalence's public interface from the package root"
git push
```
