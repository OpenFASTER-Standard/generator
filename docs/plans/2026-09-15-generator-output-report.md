# Generator Output Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `generator/reporting/` — a self-contained HTML report generator that turns a real `xsdo:` graph plus its documentation/plausibility audit results into one file the operator opens in a browser to visually verify the generator's output with their own eyes.

**Architecture:** `reporting/data.py` walks an already-built `rdflib.Graph` (plus the audit result types `extraction/` already produces) into one plain, JSON-serializable dict — this is the only part with real logic, and the only part unit-tested in the traditional sense. `reporting/render.py` embeds that dict as JSON into a static HTML/CSS/JS shell (`reporting/assets/`) with simple string substitution — no templating library. `reporting/__main__.py` is the CLI that runs the real pipeline end to end and writes the file.

**Tech Stack:** Python 3.11+ (no new Python dependency — this plan adds zero packages to `pyproject.toml`), plain vanilla JS/CSS for the report shell (no framework, no build step), `pytest`. Verification uses the `playwright` **Node** package already baked into this box's image (not a Python dependency) for one real-browser sanity check.

**Spec:** `docs/specs/2026-09-15-generator-output-report-design.md`

## Global Constraints

- Every dict this plan produces uses **plain Python types only** (`str`, `int`, `bool`, `list`, `dict`, `None`) — it must be `json.dumps`-able directly, no custom encoders.
- **Correction to the spec's own CLI examples**: this codebase's packages (`extraction`, `equivalence`, `generation`, `ingestion`) are flat, top-level packages under `generator/` — there is no `generator.reporting` nested package (the spec's `python -m generator.reporting ...` examples assumed one that doesn't exist). The real package is `reporting`, invoked as `python -m reporting ...` from within `/work/generator`, exactly matching the existing `extraction`/`equivalence` packages' own layout.
- **Real fixture files for this repo live in a separate sibling repo, `/work/ontologies/`.** Any test or command using real MiKaDiv-FM data must run with `cd /work` first, e.g. `cd /work && python3 -m pytest generator/tests/reporting/ -v` — this has been the working convention throughout sub-project 3a and applies here identically.
- Every real `xsdo:` predicate/shape this plan's code reads is exactly what `extraction/` already produces (verified directly against the current, merged source — not guessed): `XSDO.name`, `XSDO.abstract`, `XSDO.extends`, `XSDO.targetNamespace` (complex types only — simple types don't get this predicate), `XSDO.contentModel` → a blank node typed `XSDO.Sequence`/`XSDO.Choice` with `XSDO.hasParticle` → blank nodes with `XSDO.particlePosition`/`XSDO.minOccurs`/`XSDO.maxOccurs` (or `XSDO.maxOccursUnbounded`)/`XSDO["term"]` (**bracket access, never `.term`** — the established rdflib gotcha), `XSDO.hasAttributeUse` → blank nodes with `XSDO.required`/`XSDO["term"]`, `XSDO.hasIdentityConstraint` → a node typed `XSDO.Key`/`XSDO.Unique`/`XSDO.KeyRef` with `XSDO.selector`/`XSDO.field` (multi-valued)/`XSDO.refer`, `XSDO.hasEnumerationValue` → blank nodes with `XSDO.literalValue`, `XSDO.pattern` (multi-valued), the 10 scalar facet predicates (`XSDO.length`/`minLength`/`maxLength`/`whiteSpace`/`minInclusive`/`maxInclusive`/`minExclusive`/`maxExclusive`/`totalDigits`/`fractionDigits`), `XSDO.hasUnionMember` (multi-valued), `XSDO.type`/`XSDO.defaultValue`/`XSDO.fixedValue` (element/attribute declarations), `XSDO.documentation` (a plain `Literal` per language — `.language` is `None` for untagged German, `"en"`/`"de"` for tagged).
- The real result types this plan's code consumes, exactly as already merged: `extraction.annex_pdf.AttachmentReport` (`attached`/`ambiguous`/`unmatched`, each `list[str]` of names), `extraction.translation_plausibility.CoverageReport` (`total_documented_subjects`/`attached`/`ambiguous`/`unmatched`, each `int`), `extraction.translation_plausibility.PlausibilityIssue` (`kind`/`subject_name`/`detail`, each `str`).
- No server. No CI automation. No history/diffing between report generations. The report shows current reality only, regenerated on demand.

---

## Task 1: Structure section of the report data model

**Files:**
- Create: `reporting/__init__.py`
- Create: `reporting/data.py`
- Test: `tests/reporting/__init__.py`
- Test: `tests/reporting/test_data_structure.py`

**Interfaces:**
- Produces: `XSDO` (the `Namespace("https://purl.openfaster.org/xsdo/")` this whole package uses, matching every `extraction/` module's own convention), `build_structure(graph: rdflib.Graph) -> dict` — used directly by Task 2's `build_report_data`.
- `build_structure`'s return shape (every later task and the JS renderer depend on this exact shape):
  ```python
  {
      "<target_namespace>": {
          "complexTypes": [
              {
                  "uri": str, "name": str | None, "abstract": bool,
                  "extends": str | None,  # base type's own URI, as a string
                  "contentModel": {
                      "kind": "Sequence" | "Choice",
                      "particles": [
                          {
                              "minOccurs": int,
                              "maxOccurs": int | "unbounded",
                              "term": {"nested": <contentModel dict>} | {"ref": str},
                          },
                          ...
                      ],
                  },
                  "attributeUses": [{"required": bool, "ref": str}, ...],
                  "identityConstraints": [
                      {"kind": "Key" | "Unique" | "KeyRef", "selector": str,
                       "fields": list[str], "refer": str | None},
                      ...
                  ],
              },
              ...
          ],
          "simpleTypes": [
              {
                  "uri": str, "name": str | None,
                  "facets": dict[str, int | str | bool],  # facet label -> real value
                  "enumeration": list[str],
                  "patterns": list[str],
                  "unionMembers": list[str],  # each member's own URI, as a string
              },
              ...
          ],
      },
      ...
  }
  ```
- The namespace grouping key is derived from each type's own URI by splitting on the first `#` (`uri.split("#", 1)[0]`) — this works uniformly for every real URI this project mints, since `extraction.uris.global_uri`/`child_uri` always produce `f"{target_namespace}#{local_name}"` for a global component and dotted child paths under that same `#`-containing root for local/anonymous ones. Anonymous types (no `xsdo:name`) still get a full entry with `"name": None` — the report must show everything the graph actually contains, not just named things.

- [ ] **Step 1: Write the failing tests**

```python
# tests/reporting/test_data_structure.py
"""Tests for build_structure: walking a real xsdo:-shaped graph into a
plain, JSON-serializable structure tree. Uses small, hand-built graphs
with the exact real predicates extraction/ produces -- not mocks."""
from rdflib import RDF, BNode, Graph, Literal, Namespace

from reporting.data import XSDO, build_structure

# Namespace deliberately ends with "#", not "/" -- matching the real shape
# extraction.uris.global_uri always produces (f"{target_namespace}#{name}"),
# since build_structure's own namespace-grouping splits on "#".
EX = Namespace("https://example.org/test#")
NS = "https://example.org/test"


def test_abstract_base_and_extending_type_with_nested_choice():
    graph = Graph()

    # Abstract base type with one element particle.
    graph.add((EX.BaseType, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.BaseType, XSDO.name, Literal("BaseType")))
    graph.add((EX.BaseType, XSDO.abstract, Literal(True)))
    base_content = BNode()
    graph.add((EX.BaseType, XSDO.contentModel, base_content))
    graph.add((base_content, RDF.type, XSDO.Sequence))
    base_particle = BNode()
    graph.add((base_content, XSDO.hasParticle, base_particle))
    graph.add((base_particle, XSDO.particlePosition, Literal(1)))
    graph.add((base_particle, XSDO.minOccurs, Literal(1)))
    graph.add((base_particle, XSDO.maxOccurs, Literal(1)))
    graph.add((base_particle, XSDO["term"], EX.BaseElement))
    graph.add((EX.BaseElement, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.BaseElement, XSDO.name, Literal("BaseElement")))

    # Extending type: extends BaseType, adds its own Choice with 2
    # elements, one required attribute use, and one identity constraint.
    graph.add((EX.ExtType, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.ExtType, XSDO.name, Literal("ExtType")))
    graph.add((EX.ExtType, XSDO.abstract, Literal(False)))
    graph.add((EX.ExtType, XSDO.extends, EX.BaseType))
    ext_content = BNode()
    graph.add((EX.ExtType, XSDO.contentModel, ext_content))
    graph.add((ext_content, RDF.type, XSDO.Sequence))
    outer_particle = BNode()
    graph.add((ext_content, XSDO.hasParticle, outer_particle))
    graph.add((outer_particle, XSDO.particlePosition, Literal(1)))
    graph.add((outer_particle, XSDO.minOccurs, Literal(1)))
    graph.add((outer_particle, XSDO.maxOccurs, Literal(1)))
    choice_node = BNode()
    graph.add((outer_particle, XSDO["term"], choice_node))
    graph.add((choice_node, RDF.type, XSDO.Choice))
    for i, elem_name in enumerate(("OptionA", "OptionB"), start=1):
        elem_particle = BNode()
        graph.add((choice_node, XSDO.hasParticle, elem_particle))
        graph.add((elem_particle, XSDO.particlePosition, Literal(i)))
        graph.add((elem_particle, XSDO.minOccurs, Literal(1)))
        graph.add((elem_particle, XSDO.maxOccurs, Literal(1)))
        elem_uri = EX[elem_name]
        graph.add((elem_particle, XSDO["term"], elem_uri))
        graph.add((elem_uri, RDF.type, XSDO.ElementDeclaration))
        graph.add((elem_uri, XSDO.name, Literal(elem_name)))
    use_node = BNode()
    graph.add((EX.ExtType, XSDO.hasAttributeUse, use_node))
    graph.add((use_node, XSDO.required, Literal(True)))
    graph.add((use_node, XSDO["term"], EX.SomeAttr))
    graph.add((EX.SomeAttr, RDF.type, XSDO.AttributeDeclaration))
    graph.add((EX.SomeAttr, XSDO.name, Literal("SomeAttr")))
    graph.add((EX.ExtType, XSDO.hasIdentityConstraint, EX.SomeConstraint))
    graph.add((EX.SomeConstraint, RDF.type, XSDO.Unique))
    graph.add((EX.SomeConstraint, XSDO.selector, Literal("./Row")))
    graph.add((EX.SomeConstraint, XSDO.field, Literal("@id")))

    structure = build_structure(graph)

    assert set(structure.keys()) == {NS}
    complex_types = {t["name"]: t for t in structure[NS]["complexTypes"]}
    assert set(complex_types) == {"BaseType", "ExtType"}

    base = complex_types["BaseType"]
    assert base["abstract"] is True
    assert base["extends"] is None
    assert base["contentModel"]["kind"] == "Sequence"
    assert len(base["contentModel"]["particles"]) == 1

    ext = complex_types["ExtType"]
    assert ext["abstract"] is False
    assert ext["extends"] == str(EX.BaseType)
    outer = ext["contentModel"]
    assert outer["kind"] == "Sequence"
    assert len(outer["particles"]) == 1
    nested = outer["particles"][0]["term"]["nested"]
    assert nested["kind"] == "Choice"
    assert len(nested["particles"]) == 2
    assert ext["attributeUses"] == [{"required": True, "ref": str(EX.SomeAttr)}]
    assert ext["identityConstraints"] == [
        {"kind": "Unique", "selector": "./Row", "fields": ["@id"], "refer": None}
    ]


def test_unbounded_particle_is_reported_as_the_string_unbounded():
    graph = Graph()
    graph.add((EX.T, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.T, XSDO.name, Literal("T")))
    graph.add((EX.T, XSDO.abstract, Literal(False)))
    content = BNode()
    graph.add((EX.T, XSDO.contentModel, content))
    graph.add((content, RDF.type, XSDO.Sequence))
    particle = BNode()
    graph.add((content, XSDO.hasParticle, particle))
    graph.add((particle, XSDO.particlePosition, Literal(1)))
    graph.add((particle, XSDO.minOccurs, Literal(0)))
    graph.add((particle, XSDO.maxOccursUnbounded, Literal(True)))
    graph.add((particle, XSDO["term"], EX.Elem))
    graph.add((EX.Elem, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.Elem, XSDO.name, Literal("Elem")))

    structure = build_structure(graph)

    particle_data = structure[NS]["complexTypes"][0]["contentModel"]["particles"][0]
    assert particle_data["minOccurs"] == 0
    assert particle_data["maxOccurs"] == "unbounded"


def test_anonymous_type_has_no_name_but_still_gets_a_full_entry():
    graph = Graph()
    anon_uri = EX["Owner.Type"]
    graph.add((anon_uri, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((anon_uri, XSDO.abstract, Literal(False)))
    content = BNode()
    graph.add((anon_uri, XSDO.contentModel, content))
    graph.add((content, RDF.type, XSDO.Sequence))

    structure = build_structure(graph)

    entry = structure[NS]["complexTypes"][0]
    assert entry["name"] is None
    assert entry["uri"] == str(anon_uri)


def test_simple_type_with_facets_enumeration_pattern_and_union():
    graph = Graph()
    graph.add((EX.EnumType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.EnumType, XSDO.name, Literal("EnumType")))
    for value in ("A", "B"):
        value_node = BNode()
        graph.add((EX.EnumType, XSDO.hasEnumerationValue, value_node))
        graph.add((value_node, XSDO.literalValue, Literal(value)))

    graph.add((EX.LenType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.LenType, XSDO.name, Literal("LenType")))
    graph.add((EX.LenType, XSDO.length, Literal(5)))
    graph.add((EX.LenType, XSDO.pattern, Literal("[A-Z]{5}")))

    graph.add((EX.UnionType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.UnionType, XSDO.name, Literal("UnionType")))
    graph.add((EX.UnionType, XSDO.hasUnionMember, EX.EnumType))
    graph.add((EX.UnionType, XSDO.hasUnionMember, EX.LenType))

    structure = build_structure(graph)

    simple_types = {t["name"]: t for t in structure[NS]["simpleTypes"]}
    assert sorted(simple_types["EnumType"]["enumeration"]) == ["A", "B"]
    assert simple_types["LenType"]["facets"] == {"length": 5}
    assert simple_types["LenType"]["patterns"] == ["[A-Z]{5}"]
    assert set(simple_types["UnionType"]["unionMembers"]) == {
        str(EX.EnumType), str(EX.LenType)
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `mkdir -p tests/reporting && touch tests/reporting/__init__.py && cd /work && python3 -m pytest generator/tests/reporting/test_data_structure.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reporting'`

- [ ] **Step 3: Write the implementation**

```python
# reporting/__init__.py
"""OpenFASTER generator: reporting package. Turns a real, already-
extracted xsdo: graph (plus its documentation/plausibility audit
results) into one self-contained HTML report -- see
docs/specs/2026-09-15-generator-output-report-design.md and
docs/plans/2026-09-15-generator-output-report.md.
"""
```

```python
# reporting/data.py
"""Walks an already-extracted xsdo: rdflib.Graph into a plain,
JSON-serializable dict for the HTML report's client-side renderer.

Real construct shapes this module reads are exactly what extraction/
already produces (verified directly against the merged source, not
guessed) -- see this plan's own Global Constraints for the full list.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_FACET_PREDICATES = {
    "length": XSDO.length,
    "minLength": XSDO.minLength,
    "maxLength": XSDO.maxLength,
    "whiteSpace": XSDO.whiteSpace,
    "minInclusive": XSDO.minInclusive,
    "maxInclusive": XSDO.maxInclusive,
    "minExclusive": XSDO.minExclusive,
    "maxExclusive": XSDO.maxExclusive,
    "totalDigits": XSDO.totalDigits,
    "fractionDigits": XSDO.fractionDigits,
}


def _target_namespace_of(uri: str) -> str:
    return uri.split("#", 1)[0]


def _build_content_model(graph: Graph, group_node) -> dict:
    kind = "Choice" if (group_node, RDF.type, XSDO.Choice) in graph else "Sequence"
    particles = sorted(
        graph.objects(group_node, XSDO.hasParticle),
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )
    return {"kind": kind, "particles": [_build_particle(graph, p) for p in particles]}


def _build_particle(graph: Graph, particle_node) -> dict:
    min_occurs = int(graph.value(particle_node, XSDO.minOccurs))
    unbounded = graph.value(particle_node, XSDO.maxOccursUnbounded)
    if unbounded is not None:
        max_occurs: int | str = "unbounded"
    else:
        max_occurs = int(graph.value(particle_node, XSDO.maxOccurs))
    term = graph.value(particle_node, XSDO["term"])
    is_nested_group = (term, RDF.type, XSDO.Sequence) in graph or (
        term, RDF.type, XSDO.Choice
    ) in graph
    if is_nested_group:
        term_data = {"nested": _build_content_model(graph, term)}
    else:
        term_data = {"ref": str(term)}
    return {"minOccurs": min_occurs, "maxOccurs": max_occurs, "term": term_data}


def _build_attribute_uses(graph: Graph, type_uri: URIRef) -> list[dict]:
    uses = []
    for use in graph.objects(type_uri, XSDO.hasAttributeUse):
        required = bool(graph.value(use, XSDO.required))
        term = graph.value(use, XSDO["term"])
        uses.append({"required": required, "ref": str(term)})
    return uses


def _identity_constraint_kind(graph: Graph, constraint) -> str:
    for kind in ("Key", "Unique", "KeyRef"):
        if (constraint, RDF.type, XSDO[kind]) in graph:
            return kind
    raise ValueError(f"unknown identity constraint kind for {constraint}")


def _build_identity_constraints(graph: Graph, type_uri: URIRef) -> list[dict]:
    constraints = []
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        fields = [str(f) for f in graph.objects(constraint, XSDO.field)]
        refer = graph.value(constraint, XSDO.refer)
        constraints.append(
            {
                "kind": _identity_constraint_kind(graph, constraint),
                "selector": str(graph.value(constraint, XSDO.selector)),
                "fields": fields,
                "refer": str(refer) if refer is not None else None,
            }
        )
    return constraints


def _build_complex_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    extends = graph.value(type_uri, XSDO.extends)
    content_node = graph.value(type_uri, XSDO.contentModel)
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "abstract": bool(graph.value(type_uri, XSDO.abstract)),
        "extends": str(extends) if extends is not None else None,
        "contentModel": _build_content_model(graph, content_node),
        "attributeUses": _build_attribute_uses(graph, type_uri),
        "identityConstraints": _build_identity_constraints(graph, type_uri),
    }


def _build_simple_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    facets = {}
    for label, predicate in _FACET_PREDICATES.items():
        value = graph.value(type_uri, predicate)
        if value is not None:
            facets[label] = value.toPython()
    enumeration = [
        str(graph.value(value_node, XSDO.literalValue))
        for value_node in graph.objects(type_uri, XSDO.hasEnumerationValue)
    ]
    patterns = [str(p) for p in graph.objects(type_uri, XSDO.pattern)]
    union_members = [str(m) for m in graph.objects(type_uri, XSDO.hasUnionMember)]
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "facets": facets,
        "enumeration": enumeration,
        "patterns": patterns,
        "unionMembers": union_members,
    }


def build_structure(graph: Graph) -> dict:
    structure: dict[str, dict[str, list]] = {}

    for type_uri in graph.subjects(RDF.type, XSDO.ComplexTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["complexTypes"].append(_build_complex_type(graph, type_uri))

    for type_uri in graph.subjects(RDF.type, XSDO.SimpleTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["simpleTypes"].append(_build_simple_type(graph, type_uri))

    return structure
```

- [ ] **Step 4: Register the new package with the editable install**

**Real, verified-necessary step, not optional.** This project's `openfaster-generator` package is installed via `pip install -e .` (editable install), which on this Python/setuptools version uses a finder-based mechanism with a **hardcoded package-name-to-path mapping baked in at install time** (`/usr/local/lib/python3.11/dist-packages/__editable___openfaster_generator_0_1_0_finder.py`, a real, inspectable file) — confirmed live: that mapping currently only lists `equivalence`/`extraction`/`generation`/`ingestion`, so `import reporting` fails with `ModuleNotFoundError` even after `reporting/__init__.py` exists on disk, until the mapping itself is regenerated. Every later task's tests depend on `import reporting` working, so this must happen now, in Task 1, not deferred to Task 4.

In `pyproject.toml`, change:
```toml
[tool.setuptools.packages.find]
include = ["extraction*", "generation*", "equivalence*", "ingestion*"]
```
to:
```toml
[tool.setuptools.packages.find]
include = ["extraction*", "generation*", "equivalence*", "ingestion*", "reporting*"]
```

Then re-run (matching this project's own established pattern for installing/registering packages in this environment):
```bash
cd /work/generator && python3 -m pip install -e . --break-system-packages
```

Verify the fix directly:
```bash
cd /work && python3 -c "import reporting; print(reporting.__file__)"
```
Expected: prints `/work/generator/reporting/__init__.py`, no error.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_data_structure.py -v`
Expected: PASS, 4/4

- [ ] **Step 6: Commit**

```bash
git add reporting/__init__.py reporting/data.py tests/reporting/ pyproject.toml
git commit -m "feat: add structure-tree section of the report data model"
```

---

## Task 2: Declarations, documentation pairs, and audit sections

**Files:**
- Modify: `reporting/data.py`
- Test: `tests/reporting/test_data_declarations_and_audit.py`

**Interfaces:**
- Consumes: `XSDO` from Task 1 (same module, already imported).
- Produces: `build_declarations(graph) -> dict`, `build_documentation_pairs(graph, occurrences, plausibility_issues) -> dict`, `build_audit(attachment, coverage, plausibility_issues) -> dict`, and the combining `build_report_data(graph, occurrences, plausibility_issues, coverage, attachment) -> dict` — this last one is what Task 3/4 actually call.
- `build_declarations`'s shape (keyed by URI string, used by the JS renderer to render an element/attribute's own full info wherever it's referenced by a particle/attribute-use `ref`):
  ```python
  {
      "<uri>": {
          "name": str, "kind": "Element" | "Attribute",
          "type": str | None,  # the referenced type's own URI, as a string
          "default": str | None, "fixed": str | None,
          "documentation": {"de": str | None, "en": str | None},
      },
      ...
  }
  ```
- `build_documentation_pairs`'s shape:
  ```python
  {
      "matched": [{"uri": str, "name": str, "de": str, "en": str,
                   "issues": [{"kind": str, "detail": str}]}, ...],
      "unmatched": [{"uri": str, "name": str, "de": str}, ...],
      "ambiguous": [{"uri": str, "name": str, "de": str, "candidates": list[str]}, ...],
  }
  ```
  Built from **every** real subject with an `xsdo:documentation` triple (not just element/attribute declarations — Task 1's own complex/simple types and identity constraints carry documentation too, per the already-merged `extraction.documentation` module) — matching exactly the same universe `check_translation_coverage`/`check_translation_plausibility` already audit. A subject with German-but-no-English documentation is `ambiguous` if `occurrences` shows 2+ distinct real PDF texts for its name, `unmatched` otherwise.
- `build_audit`'s shape:
  ```python
  {
      "attachment": {"attached": int, "ambiguous": int, "unmatched": int},
      "coverage": {"total": int, "attached": int, "ambiguous": int, "unmatched": int},
      "issues": [{"kind": str, "subjectName": str, "detail": str}, ...],
  }
  ```

- [ ] **Step 1: Write the failing tests**

```python
# tests/reporting/test_data_declarations_and_audit.py
"""Tests for build_declarations, build_documentation_pairs, build_audit,
and the combining build_report_data."""
from rdflib import RDF, Graph, Literal, Namespace

from extraction.annex_pdf import AttachmentReport
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue
from reporting.data import (
    XSDO,
    build_audit,
    build_declarations,
    build_documentation_pairs,
    build_report_data,
)

EX = Namespace("https://example.org/test#")


def test_build_declarations_covers_elements_and_attributes():
    graph = Graph()
    graph.add((EX.Elem, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.Elem, XSDO.name, Literal("Elem")))
    graph.add((EX.Elem, XSDO.type, EX.SomeType))
    graph.add((EX.Elem, XSDO.documentation, Literal("Deutsch.")))
    graph.add((EX.Elem, XSDO.documentation, Literal("English.", lang="en")))

    graph.add((EX.Attr, RDF.type, XSDO.AttributeDeclaration))
    graph.add((EX.Attr, XSDO.name, Literal("Attr")))
    graph.add((EX.Attr, XSDO.type, EX.SomeType))
    graph.add((EX.Attr, XSDO.defaultValue, Literal("false")))

    declarations = build_declarations(graph)

    assert declarations[str(EX.Elem)] == {
        "name": "Elem", "kind": "Element", "type": str(EX.SomeType),
        "default": None, "fixed": None,
        "documentation": {"de": "Deutsch.", "en": "English."},
    }
    assert declarations[str(EX.Attr)] == {
        "name": "Attr", "kind": "Attribute", "type": str(EX.SomeType),
        "default": "false", "fixed": None,
        "documentation": {"de": None, "en": None},
    }


def _documented(graph, uri, name, german, english=None):
    graph.add((uri, XSDO.name, Literal(name)))
    graph.add((uri, XSDO.documentation, Literal(german)))
    if english is not None:
        graph.add((uri, XSDO.documentation, Literal(english, lang="en")))


def test_documentation_pairs_groups_matched_unmatched_and_ambiguous():
    graph = Graph()
    _documented(graph, EX.Matched, "Matched", "Deutsch.", "English.")
    _documented(graph, EX.Unmatched, "Unmatched", "Nur Deutsch.")
    _documented(graph, EX.Ambiguous, "Ambiguous", "Mehrdeutig.")

    occurrences = {
        "Matched": ["English."],
        "Ambiguous": ["Meaning one.", "Meaning two."],
    }
    issues = [PlausibilityIssue("length_ratio", "Matched", "ratio=9.99")]

    pairs = build_documentation_pairs(graph, occurrences, issues)

    assert pairs["matched"] == [
        {
            "uri": str(EX.Matched), "name": "Matched", "de": "Deutsch.",
            "en": "English.", "issues": [{"kind": "length_ratio", "detail": "ratio=9.99"}],
        }
    ]
    assert pairs["unmatched"] == [
        {"uri": str(EX.Unmatched), "name": "Unmatched", "de": "Nur Deutsch."}
    ]
    assert pairs["ambiguous"] == [
        {
            "uri": str(EX.Ambiguous), "name": "Ambiguous", "de": "Mehrdeutig.",
            "candidates": ["Meaning one.", "Meaning two."],
        }
    ]


def test_build_audit_reshapes_the_already_computed_reports():
    attachment = AttachmentReport(attached=["A", "B"], ambiguous=["C"], unmatched=["D", "E", "F"])
    coverage = CoverageReport(total_documented_subjects=6, attached=2, ambiguous=1, unmatched=3)
    issues = [PlausibilityIssue("untranslated", "A", "identical text")]

    audit = build_audit(attachment, coverage, issues)

    assert audit == {
        "attachment": {"attached": 2, "ambiguous": 1, "unmatched": 3},
        "coverage": {"total": 6, "attached": 2, "ambiguous": 1, "unmatched": 3},
        "issues": [{"kind": "untranslated", "subjectName": "A", "detail": "identical text"}],
    }


def test_build_report_data_combines_all_four_sections():
    graph = Graph()
    graph.add((EX.T, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.T, XSDO.name, Literal("T")))

    data = build_report_data(
        graph,
        occurrences={},
        plausibility_issues=[],
        coverage=CoverageReport(0, 0, 0, 0),
        attachment=AttachmentReport(),
    )

    assert set(data.keys()) == {"structure", "declarations", "documentationPairs", "audit"}
    assert data["structure"]["https://example.org/test"]["simpleTypes"][0]["name"] == "T"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_data_declarations_and_audit.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_declarations' from 'reporting.data'`

- [ ] **Step 3: Write the implementation**

Append to `reporting/data.py`:

```python
def build_declarations(graph: Graph) -> dict:
    declarations: dict[str, dict] = {}
    for kind_label, rdf_type in (
        ("Element", XSDO.ElementDeclaration),
        ("Attribute", XSDO.AttributeDeclaration),
    ):
        for uri in graph.subjects(RDF.type, rdf_type):
            type_ref = graph.value(uri, XSDO.type)
            default = graph.value(uri, XSDO.defaultValue)
            fixed = graph.value(uri, XSDO.fixedValue)
            docs = list(graph.objects(uri, XSDO.documentation))
            de = next((str(d) for d in docs if d.language in (None, "de")), None)
            en = next((str(d) for d in docs if d.language == "en"), None)
            declarations[str(uri)] = {
                "name": str(graph.value(uri, XSDO.name)),
                "kind": kind_label,
                "type": str(type_ref) if type_ref is not None else None,
                "default": str(default) if default is not None else None,
                "fixed": str(fixed) if fixed is not None else None,
                "documentation": {"de": de, "en": en},
            }
    return declarations


def build_documentation_pairs(
    graph: Graph, occurrences: dict[str, list[str]], plausibility_issues: list
) -> dict:
    issues_by_name: dict[str, list[dict]] = {}
    for issue in plausibility_issues:
        issues_by_name.setdefault(issue.subject_name, []).append(
            {"kind": issue.kind, "detail": issue.detail}
        )

    matched, unmatched, ambiguous = [], [], []
    for subject in graph.subjects(XSDO.documentation, None):
        name_literal = graph.value(subject, XSDO.name)
        name = str(name_literal) if name_literal is not None else str(subject)
        docs = list(graph.objects(subject, XSDO.documentation))
        de = next((str(d) for d in docs if d.language in (None, "de")), None)
        en = next((str(d) for d in docs if d.language == "en"), None)
        if de is None:
            continue  # every real documented subject in this corpus has German

        if en is not None:
            matched.append(
                {
                    "uri": str(subject), "name": name, "de": de, "en": en,
                    "issues": issues_by_name.get(name, []),
                }
            )
            continue

        candidates = occurrences.get(name, [])
        if len(set(candidates)) > 1:
            ambiguous.append(
                {
                    "uri": str(subject), "name": name, "de": de,
                    "candidates": sorted(set(candidates)),
                }
            )
        else:
            unmatched.append({"uri": str(subject), "name": name, "de": de})

    return {"matched": matched, "unmatched": unmatched, "ambiguous": ambiguous}


def build_audit(attachment, coverage, plausibility_issues: list) -> dict:
    return {
        "attachment": {
            "attached": len(attachment.attached),
            "ambiguous": len(attachment.ambiguous),
            "unmatched": len(attachment.unmatched),
        },
        "coverage": {
            "total": coverage.total_documented_subjects,
            "attached": coverage.attached,
            "ambiguous": coverage.ambiguous,
            "unmatched": coverage.unmatched,
        },
        "issues": [
            {"kind": i.kind, "subjectName": i.subject_name, "detail": i.detail}
            for i in plausibility_issues
        ],
    }


def build_report_data(
    graph: Graph,
    occurrences: dict[str, list[str]],
    plausibility_issues: list,
    coverage,
    attachment,
) -> dict:
    return {
        "structure": build_structure(graph),
        "declarations": build_declarations(graph),
        "documentationPairs": build_documentation_pairs(graph, occurrences, plausibility_issues),
        "audit": build_audit(attachment, coverage, plausibility_issues),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/reporting/ -v`
Expected: PASS, 8/8 (4 from Task 1 + 4 new)

- [ ] **Step 5: Commit**

```bash
git add reporting/data.py tests/reporting/test_data_declarations_and_audit.py
git commit -m "feat: add declarations/documentation-pairs/audit sections and build_report_data"
```

---

## Task 3: HTML/CSS/JS report shell and renderer

**Files:**
- Create: `reporting/render.py`
- Create: `reporting/assets/report.html`
- Create: `reporting/assets/report.css`
- Create: `reporting/assets/report.js`
- Test: `tests/reporting/test_render.py`

**Interfaces:**
- Consumes: a plain dict shaped like `build_report_data`'s output (Task 2) — `render_report` itself has no dependency on `reporting.data` directly, it just embeds whatever dict it's given.
- Produces: `render_report(data: dict) -> str` — used by Task 4's CLI.
- **No templating library.** `render_report` reads the 3 static asset files as plain strings and does 3 literal substring replacements: `/*__REPORT_CSS__*/` → the real CSS, `/*__REPORT_JS__*/` → the real JS, `/*__REPORT_DATA__*/` → `json.dumps(data)` with every `</` replaced by `<\/` (so a `</script>` sequence inside real documentation text can never prematurely close the embedding `<script>` tag).

- [ ] **Step 1: Write the failing tests**

```python
# tests/reporting/test_render.py
"""Tests for render_report's substitution/escaping logic, against small,
controlled fixture asset files (not the real, full assets -- those are
presentation content, not unit-testable line by line; this test proves
the substitution mechanism itself is correct, including the real
</script>-in-data edge case)."""
import json

import reporting.render as render_module
from reporting.render import render_report


def test_render_report_embeds_css_js_and_data(tmp_path, monkeypatch):
    (tmp_path / "report.html").write_text(
        "<html><style>/*__REPORT_CSS__*/</style>"
        "<script id=\"report-data\" type=\"application/json\">/*__REPORT_DATA__*/</script>"
        "<script>/*__REPORT_JS__*/</script></html>"
    )
    (tmp_path / "report.css").write_text("body { color: red; }")
    (tmp_path / "report.js").write_text("console.log('hi');")
    monkeypatch.setattr(render_module, "_ASSETS_DIR", tmp_path)

    data = {"structure": {}, "note": "plain"}
    html = render_report(data)

    assert "body { color: red; }" in html
    assert "console.log('hi');" in html
    assert json.dumps(data) in html


def test_render_report_escapes_closing_script_tags_in_data(tmp_path, monkeypatch):
    (tmp_path / "report.html").write_text(
        "<script id=\"report-data\" type=\"application/json\">/*__REPORT_DATA__*/</script>"
    )
    (tmp_path / "report.css").write_text("")
    (tmp_path / "report.js").write_text("")
    monkeypatch.setattr(render_module, "_ASSETS_DIR", tmp_path)

    data = {"documentationPairs": {"matched": [{"de": "Enthält </script> Text."}]}}
    html = render_report(data)

    assert "</script> Text" not in html  # the raw, unescaped form must not appear
    # The embedded JSON must still round-trip to the exact original data once
    # the escape is reversed, proving no real data was lost or corrupted.
    start = html.index('type="application/json">') + len('type="application/json">')
    end = html.index("</script>", start)
    embedded = html[start:end].replace("<\\/", "</")
    assert json.loads(embedded) == data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reporting.render'`

- [ ] **Step 3: Write the implementation**

```python
# reporting/render.py
"""Combines report data with the static HTML/CSS/JS shell into one
self-contained HTML string -- no templating library: the shell's own
CSS/JS are inlined at generation time via plain string substitution,
and the report data is embedded as one JSON blob a small vanilla-JS
renderer (reporting/assets/report.js) reads client-side. This keeps
the generated file genuinely self-contained: it opens correctly from a
plain file:// path, no server, no external requests.
"""
from __future__ import annotations

import json
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent / "assets"


def render_report(data: dict) -> str:
    html = (_ASSETS_DIR / "report.html").read_text()
    css = (_ASSETS_DIR / "report.css").read_text()
    js = (_ASSETS_DIR / "report.js").read_text()

    # Escape a real, if rare, risk: documentation text containing a literal
    # "</script>" substring would otherwise prematurely close the embedding
    # <script> tag and corrupt the page. "<\/" is valid inside a JS/JSON
    # string and browsers render it back to "</" -- a standard, simple fix.
    data_json = json.dumps(data).replace("</", "<\\/")

    html = html.replace("/*__REPORT_CSS__*/", css)
    html = html.replace("/*__REPORT_JS__*/", js)
    html = html.replace("/*__REPORT_DATA__*/", data_json)
    return html
```

```html
<!-- reporting/assets/report.html -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Generator Output Report</title>
<style>
/*__REPORT_CSS__*/
</style>
</head>
<body>
<nav id="nav">
  <button data-section="structure" class="active">Structure</button>
  <button data-section="docs">Documentation Pairs</button>
  <button data-section="audit">Audit</button>
  <input id="search" type="text" placeholder="Filter by name...">
</nav>
<main id="app"></main>
<script id="report-data" type="application/json">/*__REPORT_DATA__*/</script>
<script>
/*__REPORT_JS__*/
</script>
</body>
</html>
```

```css
/* reporting/assets/report.css */
body { font-family: system-ui, sans-serif; margin: 0; color: #1a1a1a; }
#nav { position: sticky; top: 0; background: #1a1a1a; padding: 0.75rem 1rem;
       display: flex; gap: 0.5rem; align-items: center; z-index: 10; }
#nav button { background: #333; color: #fff; border: none; padding: 0.4rem 0.8rem;
              border-radius: 4px; cursor: pointer; }
#nav button:hover { background: #555; }
#nav button.active { background: #0b5fff; }
#search { margin-left: auto; padding: 0.4rem 0.6rem; border-radius: 4px;
          border: 1px solid #ccc; min-width: 240px; }
#app { padding: 1rem 1.5rem; max-width: 1100px; margin: 0 auto; }
.namespace { margin-bottom: 2rem; }
.namespace > h3 { border-bottom: 2px solid #ddd; padding-bottom: 0.25rem; }
.entry { border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.75rem 1rem;
         margin: 0.5rem 0; background: #fafafa; }
.entry h4 { margin: 0 0 0.35rem 0; }
.meta { font-size: 0.9rem; color: #444; margin: 0.15rem 0; }
.content-model { margin: 0.3rem 0 0.3rem 0.5rem; padding-left: 1rem;
                 border-left: 2px solid #ddd; list-style: none; }
.model-kind { font-weight: 600; color: #666; }
.particle { list-style: none; }
.attribute-uses, .identity-constraints, .candidates { margin: 0.3rem 0;
    padding-left: 1.2rem; font-size: 0.9rem; }
a.ref { color: #0b5fff; text-decoration: none; }
a.ref:hover { text-decoration: underline; }
.declaration { background: #fff; border-style: dashed; }
.doc-group { margin-bottom: 1.5rem; }
.doc-pair.matched { border-left: 4px solid #2e7d32; }
.doc-pair.unmatched { border-left: 4px solid #999; }
.doc-pair.ambiguous { border-left: 4px solid #c62828; }
.doc-pair .de, .doc-pair .en { font-size: 0.9rem; margin: 0.2rem 0; }
.issue { font-size: 0.85rem; color: #c62828; margin-top: 0.3rem; }
.audit-numbers { display: flex; gap: 2rem; font-size: 1.05rem; margin-bottom: 1rem; }
.audit-issues { list-style: none; padding: 0; }
.audit-issues li { font-size: 0.9rem; margin: 0.25rem 0; }
```

```javascript
// reporting/assets/report.js
(function () {
  var data = JSON.parse(document.getElementById("report-data").textContent);
  var app = document.getElementById("app");

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    attrs = attrs || {};
    for (var k in attrs) {
      if (k === "class") { e.className = attrs[k]; }
      else { e.setAttribute(k, attrs[k]); }
    }
    (children || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }

  function text(s) { return document.createTextNode(s); }

  function refLink(uri) {
    return el("a", { href: "#" + uri, class: "ref", "data-name": uri }, [text(uri)]);
  }

  // An element/attribute declaration is rendered fully inline wherever a
  // particle or attribute-use references it -- declarations in this
  // corpus are always locally scoped to exactly one containing type, so
  // there is never a second place that would need the same content
  // duplicated. A reference to a named TYPE (extends, an attribute's own
  // type, a union member) instead becomes a real anchor link into that
  // type's own, separately-rendered top-level entry in Structure.
  function renderTermRef(ref) {
    var decl = data.declarations[ref];
    if (!decl) return refLink(ref);
    var box = el("div", { class: "entry declaration", id: ref, "data-name": decl.name });
    box.appendChild(el("h4", {}, [text(decl.kind + " " + decl.name)]));
    if (decl.type) {
      var typeLine = el("div", { class: "meta" }, [text("type: ")]);
      typeLine.appendChild(refLink(decl.type));
      box.appendChild(typeLine);
    }
    if (decl.default !== null) {
      box.appendChild(el("div", { class: "meta" }, [text("default=" + decl.default)]));
    }
    if (decl.fixed !== null) {
      box.appendChild(el("div", { class: "meta" }, [text("fixed=" + decl.fixed)]));
    }
    if (decl.documentation.de) {
      box.appendChild(el("div", { class: "de" }, [text("DE: " + decl.documentation.de)]));
    }
    if (decl.documentation.en) {
      box.appendChild(el("div", { class: "en" }, [text("EN: " + decl.documentation.en)]));
    }
    return box;
  }

  function renderContentModel(model) {
    var wrap = el("ul", { class: "content-model" });
    wrap.appendChild(el("li", { class: "model-kind" }, [text(model.kind)]));
    model.particles.forEach(function (p) {
      var li = el("li", { class: "particle" });
      li.appendChild(text("[" + p.minOccurs + ".." + p.maxOccurs + "] "));
      if (p.term.nested) {
        li.appendChild(renderContentModel(p.term.nested));
      } else {
        li.appendChild(renderTermRef(p.term.ref));
      }
      wrap.appendChild(li);
    });
    return wrap;
  }

  function renderComplexType(t) {
    var box = el("div", {
      class: "entry complex-type", id: t.uri, "data-name": t.name || t.uri,
    });
    box.appendChild(
      el("h4", {}, [text((t.name || "(anonymous)") + (t.abstract ? " [abstract]" : ""))])
    );
    if (t.extends) {
      var extendsLine = el("div", { class: "meta" }, [text("extends ")]);
      extendsLine.appendChild(refLink(t.extends));
      box.appendChild(extendsLine);
    }
    box.appendChild(renderContentModel(t.contentModel));
    if (t.attributeUses.length) {
      var uses = el("ul", { class: "attribute-uses" });
      t.attributeUses.forEach(function (u) {
        var li = el("li");
        li.appendChild(text(u.required ? "[required] " : "[optional] "));
        li.appendChild(renderTermRef(u.ref));
        uses.appendChild(li);
      });
      box.appendChild(uses);
    }
    if (t.identityConstraints.length) {
      var ics = el("ul", { class: "identity-constraints" });
      t.identityConstraints.forEach(function (ic) {
        var line = ic.kind + " selector=" + ic.selector + " fields=[" +
          ic.fields.join(", ") + "]" + (ic.refer ? " refer=" + ic.refer : "");
        ics.appendChild(el("li", {}, [text(line)]));
      });
      box.appendChild(ics);
    }
    return box;
  }

  function renderSimpleType(t) {
    var box = el("div", {
      class: "entry simple-type", id: t.uri, "data-name": t.name || t.uri,
    });
    box.appendChild(el("h4", {}, [text(t.name || "(anonymous)")]));
    var facetKeys = Object.keys(t.facets);
    if (facetKeys.length) {
      var facetsText = facetKeys.map(function (k) { return k + "=" + t.facets[k]; }).join(", ");
      box.appendChild(el("div", { class: "meta" }, [text("facets: " + facetsText)]));
    }
    if (t.enumeration.length) {
      box.appendChild(el("div", { class: "meta" }, [text("enumeration: " + t.enumeration.join(", "))]));
    }
    if (t.patterns.length) {
      box.appendChild(el("div", { class: "meta" }, [text("pattern: " + t.patterns.join(", "))]));
    }
    if (t.unionMembers.length) {
      var um = el("div", { class: "meta" }, [text("union of: ")]);
      t.unionMembers.forEach(function (m, i) {
        if (i > 0) um.appendChild(text(", "));
        um.appendChild(refLink(m));
      });
      box.appendChild(um);
    }
    return box;
  }

  function renderStructure() {
    var root = el("div", { class: "section", id: "section-structure" });
    Object.keys(data.structure).sort().forEach(function (ns) {
      var nsBlock = data.structure[ns];
      var nsBox = el("div", { class: "namespace" });
      nsBox.appendChild(el("h3", {}, [text(ns)]));
      nsBlock.complexTypes.forEach(function (t) { nsBox.appendChild(renderComplexType(t)); });
      nsBlock.simpleTypes.forEach(function (t) { nsBox.appendChild(renderSimpleType(t)); });
      root.appendChild(nsBox);
    });
    return root;
  }

  function renderDocPair(pair, kind) {
    var box = el("div", {
      class: "entry doc-pair " + kind, id: pair.uri, "data-name": pair.name,
    });
    box.appendChild(el("h4", {}, [text(pair.name)]));
    box.appendChild(el("div", { class: "de" }, [text("DE: " + pair.de)]));
    if (kind === "matched") {
      box.appendChild(el("div", { class: "en" }, [text("EN: " + pair.en)]));
      pair.issues.forEach(function (issue) {
        box.appendChild(el("div", { class: "issue" }, [text(issue.kind + ": " + issue.detail)]));
      });
    } else if (kind === "ambiguous") {
      var cand = el("ul", { class: "candidates" });
      pair.candidates.forEach(function (c) { cand.appendChild(el("li", {}, [text(c)])); });
      box.appendChild(cand);
    }
    return box;
  }

  function renderDocs() {
    var root = el("div", { class: "section", id: "section-docs" });
    [["matched", "Matched"], ["unmatched", "Unmatched"], ["ambiguous", "Ambiguous"]]
      .forEach(function (pair) {
        var key = pair[0], label = pair[1];
        var groupBox = el("div", { class: "doc-group" });
        groupBox.appendChild(
          el("h3", {}, [text(label + " (" + data.documentationPairs[key].length + ")")])
        );
        data.documentationPairs[key].forEach(function (p) {
          groupBox.appendChild(renderDocPair(p, key));
        });
        root.appendChild(groupBox);
      });
    return root;
  }

  function renderAudit() {
    var root = el("div", { class: "section", id: "section-audit" });
    var numbers = el("div", { class: "audit-numbers" });
    ["attachment", "coverage"].forEach(function (key) {
      var block = data.audit[key];
      var line = Object.keys(block).map(function (k) { return k + "=" + block[k]; }).join(", ");
      numbers.appendChild(el("div", {}, [text(key + ": " + line)]));
    });
    root.appendChild(numbers);
    var issues = el("ul", { class: "audit-issues" });
    data.audit.issues.forEach(function (issue) {
      var li = el("li", { "data-name": issue.subjectName });
      li.appendChild(text("[" + issue.kind + "] " + issue.subjectName + " -- " + issue.detail));
      issues.appendChild(li);
    });
    root.appendChild(issues);
    return root;
  }

  var sections = {
    structure: renderStructure(),
    docs: renderDocs(),
    audit: renderAudit(),
  };
  Object.keys(sections).forEach(function (key) {
    app.appendChild(sections[key]);
    sections[key].style.display = key === "structure" ? "" : "none";
  });

  document.querySelectorAll("#nav button[data-section]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      Object.keys(sections).forEach(function (key) {
        sections[key].style.display = key === btn.dataset.section ? "" : "none";
      });
      document.querySelectorAll("#nav button[data-section]").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  document.getElementById("search").addEventListener("input", function (e) {
    var term = e.target.value.toLowerCase();
    document.querySelectorAll(".entry").forEach(function (entry) {
      var name = (entry.dataset.name || "").toLowerCase();
      entry.style.display = name.indexOf(term) === -1 ? "none" : "";
    });
  });
})();
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_render.py -v`
Expected: PASS, 2/2

- [ ] **Step 5: Commit**

```bash
git add reporting/render.py reporting/assets/
git commit -m "feat: add self-contained HTML/CSS/JS report shell and renderer"
```

---

## Task 4: CLI, real report generation, and browser verification

**Files:**
- Create: `reporting/__main__.py`
- Create: `report.html` (in `/work/generator`, the real, committed report)
- Test: `tests/reporting/test_cli_smoke.py`

**Interfaces:**
- Consumes: `build_report_data` (Task 2), `render_report` (Task 3), and the already-merged `extraction.extract.extract`, `extraction.annex_pdf.attach_english_documentation`/`extract_name_occurrences`, `extraction.translation_plausibility.check_translation_coverage`/`check_translation_plausibility`.
- Produces: a `main()` function run via `python -m reporting <xsd_path> <pdf_path> -o <output>`.
- The `reporting*` package-include entry and the editable-install re-registration already happened in Task 1, Step 4 — nothing left to do for that here.

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/reporting/test_cli_smoke.py
"""A real, whole-corpus smoke test: the CLI's own main() runs the full
real pipeline end to end and produces a non-trivial HTML file. This is
deliberately not a mock of the pipeline -- it's the same real pipeline
the operator will actually run, exercised once here so a real breakage
(e.g. an import error, an argument-parsing bug) fails in CI/test runs
too, not only when a human happens to run the CLI by hand.

Both real fixture paths are given as absolute paths, and the subprocess
runs with cwd=/work/generator explicitly -- this repo's real fixture
files live in a separate sibling repo at /work/ontologies/, so a
cwd-relative path here would resolve incorrectly regardless of which
directory pytest itself happens to be invoked from."""
import subprocess
import sys

ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_cli_generates_a_real_non_trivial_report(tmp_path):
    output = tmp_path / "report.html"

    result = subprocess.run(
        [sys.executable, "-m", "reporting", ROOT_XSD, ANNEX_PDF, "-o", str(output)],
        cwd="/work/generator",
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    html = output.read_text()
    assert "<html" in html
    assert "MiKaDivFMRoot" in html  # a real, known type/element name must appear
    assert len(html) > 100_000  # a real, non-trivial report, not an empty shell
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_cli_smoke.py -v`
Expected: FAIL — `reporting/__main__.py` doesn't exist yet, so `python -m reporting` exits non-zero with a "No module named reporting.__main__" error, and the assertion on `result.returncode == 0` fails.

- [ ] **Step 3: Write the implementation**

```python
# reporting/__main__.py
"""CLI: python -m reporting <xsd_path> <pdf_path> -o report.html

Runs the real generator pipeline end to end (extract -> attach English
documentation -> coverage/plausibility audit) and writes one
self-contained HTML report. No flags beyond -o/--output -- YAGNI on
configurability until a real second use case demands it.
"""
from __future__ import annotations

import argparse

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.translation_plausibility import (
    check_translation_coverage,
    check_translation_plausibility,
)

from reporting.data import build_report_data
from reporting.render import render_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the generator-output visual verification report."
    )
    parser.add_argument("xsd_path", help="Path to the real XSD entry point")
    parser.add_argument("pdf_path", help="Path to the real Annex PDF")
    parser.add_argument("-o", "--output", default="report.html")
    args = parser.parse_args()

    graph = extract(args.xsd_path)
    attachment = attach_english_documentation(graph, args.pdf_path)
    occurrences = extract_name_occurrences(args.pdf_path)
    coverage = check_translation_coverage(graph, occurrences)
    plausibility_issues = check_translation_plausibility(graph)

    data = build_report_data(graph, occurrences, plausibility_issues, coverage, attachment)
    html = render_report(data)

    with open(args.output, "w") as f:
        f.write(html)
    print(f"Wrote {args.output} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /work && python3 -m pytest generator/tests/reporting/test_cli_smoke.py -v`
Expected: PASS, 1/1

- [ ] **Step 5: Run the full reporting test suite**

Run: `cd /work && python3 -m pytest generator/tests/reporting/ -v`
Expected: PASS, all tests across all 4 tasks

- [ ] **Step 6: Generate the real report for the operator to actually look at**

Run from `/work`, not `/work/generator` — the real fixture files live at `/work/ontologies/...`, and `python -m reporting` resolves correctly regardless of cwd (it's a real, top-level editable-installed package, not a submodule of anything path-relative):

```bash
cd /work
python3 -m reporting ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf -o generator/report.html
```

Confirm the printed byte count is non-trivial (hundreds of KB expected, given the real corpus's ~415 documented subjects and ~415 real types/elements/attributes).

- [ ] **Step 7: Verify the real report in an actual browser (Playwright, Node)**

This project's own convention (see `CLAUDE.md`) is to verify UI work in a real browser before calling it done — not a substitute for the operator's own review, but a sanity check that catches an obviously broken render first. `playwright` is a **Node** package already baked into this box's image (not a Python dependency of this project) — use it directly, not via any Python binding:

```bash
cd /work/generator
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + require('path').resolve('report.html'));

  // Structure section renders and contains a real, known type.
  await page.waitForSelector('#section-structure .complex-type');
  const hasKnownType = await page.locator('text=MiKaDivFMRoot').count();
  if (hasKnownType === 0) throw new Error('Known type MiKaDivFMRoot not found in Structure');

  // Section switching works.
  await page.click('#nav button[data-section=\"audit\"]');
  await page.waitForSelector('#section-audit', { state: 'visible' });
  const auditVisible = await page.locator('#section-audit').isVisible();
  const structureHidden = !(await page.locator('#section-structure').isVisible());
  if (!auditVisible || !structureHidden) throw new Error('Section switching is broken');

  // Search/filter works.
  await page.click('#nav button[data-section=\"structure\"]');
  await page.fill('#search', 'MiKaDivFMRoot');
  await page.waitForTimeout(200);
  const visibleEntries = await page.locator('.entry:visible').count();
  if (visibleEntries === 0) throw new Error('Search filtered out everything, including the real match');

  await page.screenshot({ path: 'report-screenshot.png', fullPage: false });
  await browser.close();
  console.log('Playwright verification passed.');
})().catch((err) => { console.error(err); process.exit(1); });
"
```

If this script raises any error, fix the underlying HTML/CSS/JS bug in `reporting/assets/` (not the verification script) and re-run both this check and the full test suite before proceeding. Delete `report-screenshot.png` afterward — it's a throwaway sanity-check artifact, not part of the deliverable.

- [ ] **Step 8: Commit**

```bash
git add reporting/__main__.py report.html
git commit -m "feat: add reporting CLI, generate and commit the real report"
```

---

## Definition of Done

- `python -m reporting <xsd_path> <pdf_path> -o report.html` runs against the real MiKaDiv-FM family and produces a single, self-contained `report.html` that opens correctly from a plain file path (no server) and shows all three sections (Structure, Documentation Pairs, Audit) with real data.
- `report.html` is committed to the `generator` repo.
- The report generator's own input types (`Graph`, `AttachmentReport`, `CoverageReport`, `list[PlausibilityIssue]`) are exactly the types `extraction/` already produces — no new, sub-project-specific extraction logic invented in this plan.
- Verified once in a real browser (Playwright) that the Structure/Documentation-Pairs/Audit sections render, section-switching works, and the search/filter box works — not a substitute for the operator's own review, but a sanity check before asking for it.
