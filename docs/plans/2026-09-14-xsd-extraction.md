# XSD Extraction Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `generator/extraction/`'s `extract(xsd_path) -> rdflib.Graph`, which turns the real, official MiKaDiv-FM XSD family into a complete `xsdo:`-shaped RDF graph — every construct genuinely present in the real files, not a representative subset — plus a separate function that augments that graph with English documentation matched from BZSt's official Annex PDF.

**Architecture:** Seven single-responsibility modules, built bottom-up: URI minting, simple-type facet/union extraction, identity-constraint extraction, element/attribute declaration extraction, complex-type/content-model extraction (which closes a deliberate, temporary gap left in the declaration module — the two are mutually recursive by nature, resolved via dependency injection instead of a circular import), top-level orchestration, and the Annex-PDF documentation matcher.

**Tech Stack:** Python 3.11+, `xmlschema` (parses the real XSD family — already a pipeline dependency), `rdflib` (RDF graph construction), `pdfplumber` (new dependency — real-verified word-position table extraction from the Annex PDF), `pytest`.

**Spec:** `docs/specs/2026-09-14-xsd-extraction-design.md`

## Global Constraints

- Every RDF vocabulary term used is `https://purl.openfaster.org/xsdo/<Name>` (the `XSDO` namespace), matching the equivalence checker's own convention.
- **`XSDO["term"]` bracket access, never `XSDO.term` attribute access** — `rdflib.Namespace` has a real built-in `.term()` method that attribute access resolves to instead of building a URIRef. This has already bitten this codebase twice; do not reintroduce it a third time.
- **Governing principle (from the spec, stated after getting it wrong twice during brainstorming): every construct genuinely present in the real, official XSDs is supported — full stop.** The only constructs this plan does not implement are the ones the spec's census confirms are **absent** from every real file examined: `xs:all`, `substitutionGroup`, `mixed="true"`, `xs:assert`/`xs:assertion`/`xs:any`/`xs:anyAttribute`, and `xs:appinfo` (checked, deliberately not extracted — real but different-kind metadata, not a smaller version of `xs:documentation`). Each of these raises a named, loud error or is simply never reached — never silent wrong output.
- **`xsdo:hasIdentityConstraint` attaches to the URI of the type that governs the element the constraint is declared on — not the element itself, and not whatever outer type's content model happens to contain that element as a particle.** This is required for compatibility with the already-built equivalence checker (`generator/equivalence/identity_constraints.py`), whose `compare()` reads `hasIdentityConstraint` from a *type* URI, even though XSD itself syntactically nests `xs:key`/`xs:unique`/`xs:keyref` under `xs:element`. Concretely: for an element whose own type is named (e.g. `Verwahrkette`, type `fmfach:VerwahrketteType`), constraints attach to that named type's URI; for an element with an anonymous inline type (e.g. `KontoListe`), constraints attach to that anonymous type's own minted URI — computed the exact same way as the element's own `xsdo:type` link, never to the URI of an enclosing type that merely contains the element as a particle. Verified directly against `Meldeart13.xsd`'s real `EindeutigesKonto` (declared on `KontoListe`, sibling to `KontoListe`'s own anonymous `<xs:complexType>`, not related to `Meldeart13`'s own type at all) and `MiKaDiv_FM_1.02.xsd`'s real `UUIDIstEindeutig`/`ZulassungsnummerIstEindeutig` (declared directly on the global root element `MiKaDivFMRoot`, sibling to its own anonymous complex type).
- **Anonymous types (no `name=` in the real XSD) get a URI scoped under their owning declaration** (`child_uri(owning_uri, "Type")`) — never a name-based global URI, since nothing else in the schema could reference them. **Named/global types get a stable `{targetNamespace}#{localName}` URI.** Distinguished via `xsd_type.name is None` / `xsd_type.is_global()` (confirmed real API, verified live against `PersonNatDatenType`'s attributes: `Geburtsdatum`'s type is named (`GeburtsdatumType`, `is_global()==True`), `Name`'s type is anonymous (`.name is None`, `is_global()==False`)).
- **Local element/attribute declarations are minted scoped under their owning type/element's own URI, never by bare local name.** Verified real and necessary: this corpus has 149 real `xs:attribute` declarations and **zero** are global or `ref=`-based (`grep -c '^  <xs:attribute name=' *.xsd` and `grep -rn 'xs:attribute ref='` both confirm this) — a bare local name like `"Name"` is not guaranteed unique across different types, so minting must be `child_uri(owning_type_or_element_uri, local_name)`, never `global_uri(namespace, local_name)`.
- **`xsdo:documentation` is a plain RDF-native language-tagged literal** — `rdflib.Literal(text, lang="de")`/`Literal(text, lang="en")` for MiKaDiv-VIB/KaFE's real `xml:lang`-tagged documentation, and an untagged `Literal(text)` (no `lang`) for MiKaDiv-FM's own real untagged-German documentation (verified: all 410 of FM's real `xs:documentation` blocks have no `xml:lang` at all). Not a custom node shape — `rdf:langString`'s own native tagging already models this exactly.
- **`pdfplumber`'s `extract_tables()` must not be used against the Annex PDF.** Verified directly (see Task 7, Step 1): it garbles the real PDF's nested Attributes/Elements sub-tables, merging distinct columns into one blob string, even though the page has real ruling lines. Word-position clustering via `extract_words()` is the verified-working mechanism.
- Any real library API used, especially anything from `xmlschema`'s or `pdfplumber`'s object models this codebase hasn't used before, has already been empirically verified against the real installed library and the real MiKaDiv-FM files/Annex PDF during this plan's own design — every API call below reflects what was actually observed, not a guess. If an implementer's own local install disagrees with what's documented here, stop and re-verify rather than silently patching around the mismatch.

## Non-Goals for this plan

Beyond the spec's own scope boundaries (curating real MiKaDiv-FM concepts; teaching the equivalence checker to consume `xsdo:Choice`/`xsdo:extends`/`xsdo:AttributeUse` — both explicitly separate work, not part of extraction):

- **Full-schema content coverage.** This plan proves every real *construct kind* extracts correctly against real examples; it does not assert every one of the real family's ~123 elements/149 attributes/111 complex types/56 simple types has been individually extracted and reviewed. That's real content-curation work for a later sub-project.
- **The German Annex PDF.** Confirmed redundant with the XSD's own documentation (see spec) — not parsed at all.

---

## Task 1: URI minting

**Files:**
- Create: `extraction/uris.py`
- Modify: `extraction/__init__.py` (replace the placeholder docstring)
- Test: `tests/extraction/test_uris.py`

**Interfaces:**
- Produces: `global_uri(target_namespace: str, local_name: str) -> URIRef`, `child_uri(parent_uri: URIRef, local_name: str) -> URIRef`, `type_uri(xsd_type, owner_uri: URIRef) -> URIRef` (named/global type → `global_uri`; anonymous type → `child_uri(owner_uri, "Type")`) — used by every other task in this plan.

- [ ] **Step 1: Write the failing tests**

```python
# tests/extraction/test_uris.py
"""Tests for URI minting: real, stable URIs for named/global XSD
components, and collision-free scoped URIs for local/anonymous ones
that have no global identity of their own.
"""
from rdflib import URIRef

from extraction.uris import child_uri, global_uri, type_uri


class _FakeXsdType:
    def __init__(self, name, target_namespace, local_name, is_global):
        self.name = name
        self.target_namespace = target_namespace
        self.local_name = local_name
        self._is_global = is_global

    def is_global(self):
        return self._is_global


def test_global_uri_joins_namespace_and_local_name_with_hash():
    assert global_uri("http://example.org/ns", "Foo") == URIRef(
        "http://example.org/ns#Foo"
    )


def test_child_uri_appends_a_dotted_segment_to_the_parent():
    parent = URIRef("http://example.org/ns#Foo")
    assert child_uri(parent, "Bar") == URIRef("http://example.org/ns#Foo.Bar")


def test_child_uri_can_be_chained_for_deep_nesting():
    root = global_uri("http://example.org/ns", "Meldeart13")
    konto_liste = child_uri(root, "KontoListe")
    konto = child_uri(konto_liste, "Konto")
    attribute = child_uri(konto, "@Kontonummer")
    assert attribute == URIRef(
        "http://example.org/ns#Meldeart13.KontoListe.Konto.@Kontonummer"
    )


def test_type_uri_of_a_named_type_is_its_own_global_uri():
    named = _FakeXsdType(
        name="{http://example.org/ns}GeburtsdatumType",
        target_namespace="http://example.org/ns",
        local_name="GeburtsdatumType",
        is_global=True,
    )
    owner = global_uri("http://example.org/ns", "Geburtsdatum")
    assert type_uri(named, owner) == URIRef(
        "http://example.org/ns#GeburtsdatumType"
    )


def test_type_uri_of_an_anonymous_type_is_scoped_under_its_owner():
    anonymous = _FakeXsdType(
        name=None,
        target_namespace="http://example.org/ns",
        local_name=None,
        is_global=False,
    )
    owner = global_uri("http://example.org/ns", "Name")
    assert type_uri(anonymous, owner) == URIRef("http://example.org/ns#Name.Type")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `mkdir -p tests/extraction && touch tests/extraction/__init__.py && pytest tests/extraction/test_uris.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.uris'`

- [ ] **Step 3: Write the implementation**

```python
# extraction/uris.py
"""URI minting for extracted xsdo: facts. Only components with real
global XSD identity (named complexType/simpleType, global element) get
a stable, name-based URI -- everything else (local element/attribute
declarations, anonymous types) is scoped under whichever declaration
owns it, since XSD itself gives those no identity outside that scope.
Real, confirmed necessary: this corpus has 149 real xs:attribute
declarations and zero are global -- a bare local name is not unique
across types, so local declarations must be scoped, not minted flat.
"""
from __future__ import annotations

from rdflib import URIRef


def global_uri(target_namespace: str, local_name: str) -> URIRef:
    return URIRef(f"{target_namespace}#{local_name}")


def child_uri(parent_uri: URIRef, local_name: str) -> URIRef:
    return URIRef(f"{parent_uri}.{local_name}")


def type_uri(xsd_type, owner_uri: URIRef) -> URIRef:
    if xsd_type.name is not None:
        return global_uri(xsd_type.target_namespace, xsd_type.local_name)
    return child_uri(owner_uri, "Type")
```

```python
# extraction/__init__.py
"""OpenFASTER generator: extraction package. Turns a real, official
XSD family into an xsdo:-shaped rdflib.Graph -- see
docs/specs/2026-09-14-xsd-extraction-design.md and
docs/plans/2026-09-14-xsd-extraction.md.
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/extraction/test_uris.py -v`
Expected: PASS, 5/5

- [ ] **Step 5: Commit**

```bash
git add extraction/uris.py extraction/__init__.py tests/extraction/
git commit -m "feat: add URI minting for extracted xsdo: facts"
```

---

## Task 2: Simple-type facet and union extraction

**Files:**
- Create: `extraction/simple_types.py`
- Test: `tests/extraction/test_simple_types.py`

**Interfaces:**
- Consumes: `type_uri` from Task 1.
- Produces: `XSDO`, `extract_simple_type(graph: Graph, xsd_type, uri: URIRef) -> None` — used by Task 4 (declarations) and Task 6 (orchestrator).

- [ ] **Step 1: Confirm the real `xmlschema` facets API**

Already verified live during this plan's design against the real `MiKaDiv_FM_Standardtypen_1.02.xsd` (`DepotverhaeltnisEnumType`, `WIDType`) and re-confirmed here as an executable check:

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Standardtypen_1.02.xsd')
t = schema.maps.types['{http://www.itzbund.de/MiKaDiv/FMStd/1.02}WIDType']
print(t.facets)
pattern = t.facets['{http://www.w3.org/2001/XMLSchema}pattern']
print('regexps:', pattern.regexps)
u = schema.maps.types['{http://www.itzbund.de/MiKaDiv/FMStd/1.02}GeburtsdatumType']
print('member_types:', u.member_types)
"
```
(run from `/work/generator`, adjusting the relative path to `/work` if run elsewhere)

Expected: a `facets` dict keyed by `{http://www.w3.org/2001/XMLSchema}<facetname>`; scalar facets (`length`, `minLength`, etc.) expose `.value`; `enumeration` exposes `.enumeration` (a list of raw string values); `pattern` exposes `.regexps` (a list of raw pattern strings, not compiled-with-anchors); `xs:union` types expose `.member_types` (a list of the real member type objects, each with its own `.name`/`.local_name`/`.target_namespace`). If any of this differs on the actual installed `xmlschema` version, stop and adjust Step 3 below to match what you actually find.

- [ ] **Step 2: Write the failing tests**

```python
# tests/extraction/test_simple_types.py
"""Tests for facet and xs:union extraction, against real MiKaDiv-FM
simple types -- the complete closed set of 12 standard facets, not
just the subset this project's own census happened to observe."""
from rdflib import RDF, Graph, Namespace, URIRef
import xmlschema

from extraction.simple_types import XSDO, extract_simple_type

FIXTURE = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Standardtypen_1.02.xsd"
EX = Namespace("https://example.org/test/")


def _schema():
    return xmlschema.XMLSchema(FIXTURE)


def test_enumeration_facet_is_extracted_as_a_literal_value_per_option():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}NatuerlicheGeschlechtType"] \
        if "{http://www.itzbund.de/MiKaDiv/FMStd/1.02}NatuerlicheGeschlechtType" in schema.maps.types \
        else next(
            t for name, t in schema.maps.types.items()
            if "{http://www.w3.org/2001/XMLSchema}enumeration" in getattr(t, "facets", {})
        )
    uri = EX.SomeEnumType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    values = {
        str(graph.value(v, XSDO.literalValue))
        for v in graph.objects(uri, XSDO.hasEnumerationValue)
    }
    real_enum = xsd_type.facets["{http://www.w3.org/2001/XMLSchema}enumeration"].enumeration
    assert values == set(real_enum)


def test_length_and_pattern_facets_are_extracted_from_wid_type():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}WIDType"]
    uri = EX.WIDType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    assert (uri, RDF.type, XSDO.SimpleTypeDefinition) in graph
    assert int(graph.value(uri, XSDO.length)) == 16
    patterns = {str(p) for p in graph.objects(uri, XSDO.pattern)}
    assert patterns == {"DE[0-9]{14}"}


def test_union_member_types_are_linked_by_their_own_real_uri():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}GeburtsdatumType"]
    uri = EX.GeburtsdatumType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    members = {str(m) for m in graph.objects(uri, XSDO.hasUnionMember)}
    assert members == {
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum0Type",
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum1880Type",
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum0000Type",
    }


def test_type_with_no_facets_still_gets_the_definition_triple():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}Datum0Type"]
    uri = EX.Datum0Type
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    assert (uri, RDF.type, XSDO.SimpleTypeDefinition) in graph
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extraction/test_simple_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.simple_types'`

- [ ] **Step 4: Write the implementation**

```python
# extraction/simple_types.py
"""Facet and xs:union extraction for xsdo:SimpleTypeDefinition -- the
complete, closed set of 12 standard XSD constraining facets, not just
the subset this project's own census happened to observe (matches this
project's established principle: maxExclusive stays supported even
though unobserved, exactly like xs:key/xs:keyref in identity
constraints -- see the extraction design spec).
"""
from __future__ import annotations

from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from extraction.uris import type_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_XS = "{http://www.w3.org/2001/XMLSchema}"

_SCALAR_FACETS = {
    f"{_XS}length": XSDO.length,
    f"{_XS}minLength": XSDO.minLength,
    f"{_XS}maxLength": XSDO.maxLength,
    f"{_XS}whiteSpace": XSDO.whiteSpace,
    f"{_XS}minInclusive": XSDO.minInclusive,
    f"{_XS}maxInclusive": XSDO.maxInclusive,
    f"{_XS}minExclusive": XSDO.minExclusive,
    f"{_XS}maxExclusive": XSDO.maxExclusive,
    f"{_XS}totalDigits": XSDO.totalDigits,
    f"{_XS}fractionDigits": XSDO.fractionDigits,
}
_ENUMERATION_KEY = f"{_XS}enumeration"
_PATTERN_KEY = f"{_XS}pattern"


def extract_simple_type(graph: Graph, xsd_type, uri: URIRef) -> None:
    graph.add((uri, RDF.type, XSDO.SimpleTypeDefinition))

    facets = getattr(xsd_type, "facets", None) or {}

    for facet_key, predicate in _SCALAR_FACETS.items():
        facet = facets.get(facet_key)
        if facet is not None:
            graph.add((uri, predicate, Literal(facet.value)))

    enumeration_facet = facets.get(_ENUMERATION_KEY)
    if enumeration_facet is not None:
        for value in enumeration_facet.enumeration:
            value_node = BNode()
            graph.add((uri, XSDO.hasEnumerationValue, value_node))
            graph.add((value_node, XSDO.literalValue, Literal(value)))

    pattern_facet = facets.get(_PATTERN_KEY)
    if pattern_facet is not None:
        for regexp in pattern_facet.regexps:
            graph.add((uri, XSDO.pattern, Literal(regexp)))

    member_types = getattr(xsd_type, "member_types", None)
    if member_types is not None:
        for member in member_types:
            member_uri = type_uri(member, uri)
            graph.add((uri, XSDO.hasUnionMember, member_uri))
            if member.name is None:
                extract_simple_type(graph, member, member_uri)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_simple_types.py -v`
Expected: PASS, 4/4

- [ ] **Step 6: Commit**

```bash
git add extraction/simple_types.py tests/extraction/test_simple_types.py
git commit -m "feat: add facet and xs:union extraction for simple types"
```

---

## Task 3: Identity-constraint extraction

**Files:**
- Create: `extraction/identity_constraints.py`
- Test: `tests/extraction/test_identity_constraints.py`

**Interfaces:**
- Consumes: `child_uri` from Task 1.
- Produces: `XSDO`, `extract_identity_constraints(graph: Graph, xsd_element, owner_uri: URIRef) -> None` — iterates `xsd_element.identities`, attaching each to `owner_uri` (the caller decides which type's URI that is, per this plan's Global Constraints — this module does not compute it). Used by Task 5 (complex types).

- [ ] **Step 1: Confirm the real `xmlschema` identity-constraint API**

Already verified live during this plan's design against `MiKaDiv_FM_Meldeart13_1.02.xsd`'s real `EindeutigesKonto` (a composite 2-field `xs:unique`) and a hand-built synthetic `xs:key`/`xs:keyref` pair (real `xs:key`/`xs:keyref` usage was searched for across every real XSD file on disk and confirmed **absent** everywhere — see the spec's corrected census). Re-confirm as an executable check:

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd')
t = schema.maps.types['{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13']
for p in t.content.iter_model():
    for ic in p.identities:
        print(ic.local_name, type(ic).__name__, ic.selector.path, [f.path for f in ic.fields])
"
```
Expected: prints `KnotenpositionInVerwahrketteEindeutig XsdUnique fmfach:Verwahrstelle | fmfach:DepotfuehrendeStelle ['@Position']` (on the `Verwahrkette` particle) and `EindeutigesKonto XsdUnique fmma13:Konto ['@ArtDesDepotkontos', '@Kontonummer']` (on the `KontoListe` particle). `XsdKey`/`XsdUnique`/`XsdKeyref` all expose `.local_name`, `.selector.path`, `.fields` (each with `.path`); `XsdKeyref` additionally exposes `.refer` (the referenced `XsdKey`/`XsdUnique` object itself, not a string — use `.refer.local_name`).

- [ ] **Step 2: Write the failing tests**

```python
# tests/extraction/test_identity_constraints.py
"""Tests for xs:key/xs:unique/xs:keyref extraction. xs:unique is
tested against the real Meldeart13.xsd; xs:key/xs:keyref are tested
via a hand-built synthetic fixture since neither is confirmed present
in any real file on disk (see the extraction design spec's corrected
census) -- they stay supported anyway as part of the same closed,
standard identity-constraint kind set as xs:unique.
"""
import os

import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.identity_constraints import XSDO, extract_identity_constraints

EX = Namespace("https://example.org/test/")
FIXTURE = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd"

_SYNTHETIC_KEYREF_XSD = """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:test:keyref" xmlns:tns="urn:test:keyref"
           elementFormDefault="qualified">
  <xs:element name="Root">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Item" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType><xs:attribute name="id" type="xs:string"/></xs:complexType>
        </xs:element>
        <xs:element name="Ref" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType><xs:attribute name="itemId" type="xs:string"/></xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
    <xs:key name="ItemKey">
      <xs:selector xpath="tns:Item"/>
      <xs:field xpath="@id"/>
    </xs:key>
    <xs:keyref name="RefToItem" refer="tns:ItemKey">
      <xs:selector xpath="tns:Ref"/>
      <xs:field xpath="@itemId"/>
    </xs:keyref>
  </xs:element>
</xs:schema>
"""


def test_real_composite_unique_constraint_extracts_all_fields():
    schema = xmlschema.XMLSchema(FIXTURE)
    meldeart13 = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    konto_liste = next(
        p for p in meldeart13.content.iter_model() if p.local_name == "KontoListe"
    )
    graph = Graph()

    extract_identity_constraints(graph, konto_liste, EX.KontoListeType)

    constraints = list(graph.objects(EX.KontoListeType, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    constraint = constraints[0]
    assert (constraint, RDF.type, XSDO.Unique) in graph
    assert str(graph.value(constraint, XSDO.selector)) == "fmma13:Konto"
    fields = {str(f) for f in graph.objects(constraint, XSDO.field)}
    assert fields == {"@ArtDesDepotkontos", "@Kontonummer"}


def test_synthetic_key_and_keyref_extract_kind_and_refer(tmp_path):
    xsd_path = tmp_path / "keyref.xsd"
    xsd_path.write_text(_SYNTHETIC_KEYREF_XSD)
    schema = xmlschema.XMLSchema(str(xsd_path))
    root = schema.maps.elements["{urn:test:keyref}Root"]
    graph = Graph()

    extract_identity_constraints(graph, root, EX.RootType)

    kinds = {
        str(graph.value(c, RDF.type))
        for c in graph.objects(EX.RootType, XSDO.hasIdentityConstraint)
    }
    assert kinds == {str(XSDO.Key), str(XSDO.KeyRef)}

    keyref = next(
        c
        for c in graph.objects(EX.RootType, XSDO.hasIdentityConstraint)
        if (c, RDF.type, XSDO.KeyRef) in graph
    )
    assert str(graph.value(keyref, XSDO.refer)) == "ItemKey"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extraction/test_identity_constraints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.identity_constraints'`

- [ ] **Step 4: Write the implementation**

```python
# extraction/identity_constraints.py
"""Identity-constraint extraction: xs:key/xs:unique/xs:keyref, the
complete closed set of XSD identity-constraint kinds. Only xs:unique
is confirmed real anywhere in this corpus (an earlier claim of real
xs:key/xs:keyref usage in KaFE did not survive re-verification against
every real XSD file on disk -- see the extraction design spec's
corrected census); xs:key/xs:keyref stay supported regardless, as the
same closed kind set xs:unique belongs to.

Attachment (which URI hasIdentityConstraint is linked from) is the
caller's decision, not this module's -- see this plan's Global
Constraints for why it must be a type URI, computed the same way as
the owning element's own xsdo:type link.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from extraction.uris import child_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_KIND_BY_CLASS = (
    (xmlschema.validators.identities.XsdKey, XSDO.Key),
    (xmlschema.validators.identities.XsdUnique, XSDO.Unique),
    (xmlschema.validators.identities.XsdKeyref, XSDO.KeyRef),
)


def _kind_of(identity_constraint):
    for cls, kind in _KIND_BY_CLASS:
        if isinstance(identity_constraint, cls):
            return kind
    raise NotImplementedError(
        f"unknown identity constraint kind: {type(identity_constraint)}"
    )


def extract_identity_constraints(graph: Graph, xsd_element, owner_uri: URIRef) -> None:
    for identity_constraint in xsd_element.identities:
        constraint_uri = child_uri(owner_uri, identity_constraint.local_name)
        graph.add((constraint_uri, RDF.type, _kind_of(identity_constraint)))
        graph.add(
            (constraint_uri, XSDO.selector, Literal(identity_constraint.selector.path))
        )
        for field in identity_constraint.fields:
            graph.add((constraint_uri, XSDO.field, Literal(field.path)))
        if isinstance(identity_constraint, xmlschema.validators.identities.XsdKeyref):
            graph.add(
                (constraint_uri, XSDO.refer, Literal(identity_constraint.refer.local_name))
            )
        graph.add((owner_uri, XSDO.hasIdentityConstraint, constraint_uri))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_identity_constraints.py -v`
Expected: PASS, 2/2

- [ ] **Step 6: Commit**

```bash
git add extraction/identity_constraints.py tests/extraction/test_identity_constraints.py
git commit -m "feat: add xs:key/xs:unique/xs:keyref extraction"
```

---

## Task 4: Element and attribute declaration extraction

**Files:**
- Create: `extraction/declarations.py`
- Test: `tests/extraction/test_declarations.py`

**Interfaces:**
- Consumes: `type_uri` from Task 1, `extract_simple_type` from Task 2.
- Produces: `XSDO`, `extract_element_declaration(graph, xsd_element, uri, extract_anonymous_complex_type=None) -> None`, `extract_attribute_declaration(graph, xsd_attribute, uri, extract_anonymous_complex_type=None) -> None` — used by Task 5 (complex types) and Task 6 (orchestrator).
- **Deliberate, temporary gap, closed within this same plan (not a permanent scope cut like the equivalence checker's Sequence-only MVP):** an element whose own type is an anonymous **complex** type (real, confirmed: `MiKaDiv_FM_Meldeart13_1.02.xsd`'s `KontoListe`/`Konto`) raises `NotImplementedError` unless `extract_anonymous_complex_type` is supplied — Task 5 supplies it, since extracting a complex type's shape needs this module's own declaration functions in turn (elements are made of elements/attributes; an element's type can itself be an inline complex type). Attributes never have this gap: XSD only allows attributes to have simple types.

- [ ] **Step 1: Confirm the real `xmlschema` declaration API**

Already verified live during this plan's design against real `MiKaDiv_FM_Fachtypen_1.02.xsd`/`MiKaDiv_FM_Personentypen_1.02.xsd` declarations. Re-confirm as an executable check:

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd')
t = schema.maps.types['{http://www.itzbund.de/MiKaDiv/FMFach/1.02}AuszahlendeStellePositionType']
attr = t.attributes['Position']
print('use=', attr.use, 'default=', attr.default, 'fixed=', attr.fixed, 'type.name=', attr.type.name)
print('doc attrib:', [d.attrib for d in attr.annotation.documentation])
"
```

Expected: `XsdAttribute` exposes `.use` (`'required'`/`'optional'`), `.default`, `.fixed` directly (both `None` when absent, real string values when present — confirmed real: `Position` has `fixed='1'`; `VerwahrketteType`'s `AuszahlStelleIstDepotfuehrStelle` has `default='false'`); `.type.name` is `None` for an anonymous type, a Clark-notation string for a named one; `.annotation.documentation` is a list of real `xml.etree` `Element`s whose `.attrib` dict is empty for FM's own untagged German documentation (confirmed: `{}` for every one of FM's 410 real blocks) and contains `{http://www.w3.org/XML/1998/namespace}lang: '...'}` for MiKaDiv-VIB/KaFE's tagged form instead. `XsdElement` exposes the identical `.use`-less but otherwise symmetric `.default`/`.fixed`/`.type`/`.annotation` shape.

- [ ] **Step 2: Write the failing tests**

```python
# tests/extraction/test_declarations.py
"""Tests for ElementDeclaration/AttributeDeclaration extraction:
name/type/default/fixed/documentation, against real MiKaDiv-FM
declarations covering both real documentation forms (FM's own
untagged German, and the tagged form used elsewhere in this project).
"""
import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.declarations import XSDO, extract_attribute_declaration, extract_element_declaration
from extraction.uris import child_uri, global_uri

EX = Namespace("https://example.org/test/")
FACHTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd"


def test_attribute_with_fixed_value_and_named_type():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}AuszahlendeStellePositionType"]
    attr = t.attributes["Position"]
    uri = EX.Position
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    assert (uri, RDF.type, XSDO.AttributeDeclaration) in graph
    assert str(graph.value(uri, XSDO.name)) == "Position"
    assert str(graph.value(uri, XSDO.fixedValue)) == "1"
    assert graph.value(uri, XSDO.defaultValue) is None


def test_attribute_with_default_value():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}VerwahrketteType"]
    attr = t.attributes["AuszahlStelleIstDepotfuehrStelle"]
    uri = EX.Flag
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    assert str(graph.value(uri, XSDO.defaultValue)) == "false"


def test_attribute_with_anonymous_simple_type_extracts_its_facets():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonNatDatenType"]
    attr = t.attributes["Name"]
    uri = EX.NameAttr
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    type_uri_value = graph.value(uri, XSDO.type)
    assert type_uri_value == child_uri(EX.NameAttr, "Type")
    assert (type_uri_value, RDF.type, XSDO.SimpleTypeDefinition) in graph
    assert int(graph.value(type_uri_value, XSDO.minLength)) == 1


def test_element_with_default_type_reference_and_no_anonymous_complex_type():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FM/1.02}DLZertifiziert"]
    element = next(p for p in t.content.iter_model() if p.local_name == "ZertifizierteStelle")
    uri = EX.ZertifizierteStelle
    graph = Graph()

    extract_element_declaration(graph, element, uri)

    assert (uri, RDF.type, XSDO.ElementDeclaration) in graph
    assert str(graph.value(uri, XSDO.name)) == "ZertifizierteStelle"
    expected_type = global_uri(
        "http://www.itzbund.de/MiKaDiv/FMPers/1.02", "ZertifizierteStelleType"
    )
    assert graph.value(uri, XSDO.type) == expected_type
    docs = list(graph.objects(uri, XSDO.documentation))
    assert len(docs) == 1
    assert docs[0].language is None
    assert str(docs[0]) == "Das zertifizierte Institut."


def test_element_with_anonymous_complex_type_raises_without_a_callback():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    konto_liste = next(p for p in t.content.iter_model() if p.local_name == "KontoListe")
    graph = Graph()

    with pytest.raises(NotImplementedError):
        extract_element_declaration(graph, konto_liste, EX.KontoListe)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extraction/test_declarations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.declarations'`

- [ ] **Step 4: Write the implementation**

```python
# extraction/declarations.py
"""Element and attribute declaration extraction: xsdo:name, xsdo:type,
xsdo:defaultValue/xsdo:fixedValue, and xsdo:documentation in both real
forms this project's modules use -- FM's own untagged German
xs:documentation, and MiKaDiv-VIB/KaFE's xml:lang-tagged pairs --
captured uniformly via RDF's own native language-tagged literal, not a
custom shape.

An element's anonymous COMPLEX type is deliberately not handled here
alone (see this module's own NotImplementedError below) -- Task 5's
extraction.complex_types supplies the missing piece via a callback,
since a complex type's own extraction needs this module's functions in
turn. This is genuine mutual recursion between "a type's content is
elements" and "an element's type can be an inline complex type",
resolved via dependency injection instead of a circular import.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from extraction.simple_types import extract_simple_type
from extraction.uris import type_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _extract_documentation(graph: Graph, uri: URIRef, xsd_component) -> None:
    annotation = xsd_component.annotation
    if annotation is None:
        return
    for doc in annotation.documentation:
        text = (doc.text or "").strip()
        if not text:
            continue
        lang = doc.attrib.get(_XML_LANG)
        literal = Literal(text, lang=lang) if lang else Literal(text)
        graph.add((uri, XSDO.documentation, literal))


def _is_complex(xsd_type) -> bool:
    return isinstance(xsd_type, xmlschema.validators.complex_types.XsdComplexType)


def _extract_type_reference(
    graph: Graph, uri: URIRef, xsd_component, extract_anonymous_complex_type
) -> None:
    referenced_type = xsd_component.type
    referenced_uri = type_uri(referenced_type, uri)
    graph.add((uri, XSDO.type, referenced_uri))

    if referenced_type.name is not None:
        return  # named type -- extracted independently at the top level

    if _is_complex(referenced_type):
        if extract_anonymous_complex_type is None:
            raise NotImplementedError(
                "anonymous complex types need extract_anonymous_complex_type "
                "(see extraction/complex_types.py, which supplies this)"
            )
        extract_anonymous_complex_type(graph, referenced_type, referenced_uri)
        return

    extract_simple_type(graph, referenced_type, referenced_uri)


def extract_element_declaration(
    graph: Graph, xsd_element, uri: URIRef, extract_anonymous_complex_type=None
) -> None:
    graph.add((uri, RDF.type, XSDO.ElementDeclaration))
    graph.add((uri, XSDO.name, Literal(xsd_element.local_name)))
    _extract_type_reference(graph, uri, xsd_element, extract_anonymous_complex_type)
    if xsd_element.default is not None:
        graph.add((uri, XSDO.defaultValue, Literal(xsd_element.default)))
    if xsd_element.fixed is not None:
        graph.add((uri, XSDO.fixedValue, Literal(xsd_element.fixed)))
    _extract_documentation(graph, uri, xsd_element)


def extract_attribute_declaration(
    graph: Graph, xsd_attribute, uri: URIRef, extract_anonymous_complex_type=None
) -> None:
    graph.add((uri, RDF.type, XSDO.AttributeDeclaration))
    graph.add((uri, XSDO.name, Literal(xsd_attribute.local_name)))
    _extract_type_reference(graph, uri, xsd_attribute, extract_anonymous_complex_type)
    if xsd_attribute.default is not None:
        graph.add((uri, XSDO.defaultValue, Literal(xsd_attribute.default)))
    if xsd_attribute.fixed is not None:
        graph.add((uri, XSDO.fixedValue, Literal(xsd_attribute.fixed)))
    _extract_documentation(graph, uri, xsd_attribute)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_declarations.py -v`
Expected: PASS, 5/5

- [ ] **Step 6: Commit**

```bash
git add extraction/declarations.py tests/extraction/test_declarations.py
git commit -m "feat: add element/attribute declaration extraction"
```

---

## Task 5: Complex-type and content-model extraction

**Files:**
- Create: `extraction/complex_types.py`
- Test: `tests/extraction/test_complex_types.py`

**Interfaces:**
- Consumes: `child_uri`, `type_uri` from Task 1; `extract_identity_constraints` from Task 3; `extract_element_declaration`, `extract_attribute_declaration` from Task 4.
- Produces: `XSDO`, `extract_complex_type(graph: Graph, xsd_type, uri: URIRef) -> None`, `extract_element_declaration_with_recursion(graph: Graph, xsd_element, uri: URIRef) -> None` (wraps Task 4's `extract_element_declaration`, supplying `extract_complex_type` as the anonymous-complex-type callback, and additionally extracting the element's own identity constraints, per this plan's Global Constraints on attachment) — both used by Task 6 (orchestrator); `extract_element_declaration_with_recursion` is also what closes Task 4's gap for nested particles within this module itself.
- **Real, confirmed behavior this task's tests must reproduce:** `xmlschema`'s `XsdComplexType.content` returns the type's own *additional* particles only for a type using `xs:extension` — never a duplicate of the base type's own particles. `.attributes` returns the *merged* view (own + inherited); `.attributes.base_attributes` (`None` if there's no base) gives the inherited subset, used to compute the type's own-only attributes.

- [ ] **Step 1: Confirm the real `xmlschema` extension/content/attribute-group API**

Already verified live during this plan's design against real `MiKaDiv_FM_1.02.xsd`/`MiKaDiv_FM_Fachtypen_1.02.xsd` types. Re-confirm as an executable check:

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd')
t = schema.maps.types['{http://www.itzbund.de/MiKaDiv/FM/1.02}DLZertifiziert']
print('base_type=', t.base_type, 'abstract=', t.abstract, 'base abstract=', t.base_type.abstract)
print('own content particles:', [p.name for p in t.content.iter_model()])

schema2 = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd')
ext = schema2.maps.types['{http://www.itzbund.de/MiKaDiv/FMFach/1.02}Paymentline45BBasisType']
print('merged attrs:', list(ext.attributes.keys()))
print('base_attributes:', list(ext.attributes.base_attributes.keys()))

no_ext = schema2.maps.types['{http://www.itzbund.de/MiKaDiv/FMFach/1.02}PaymentlineBasisType']
print('no-extension base_type:', no_ext.base_type, 'base_attributes:', no_ext.attributes.base_attributes)
"
```

Expected: `base_type` is `None` for a type with no `xs:extension`; `.content.iter_model()` returns only the type's own additional particles for an extending type (`DLZertifiziert` shows only `ZertifizierteStelle`/`Dienstleister`, not `NachrichtenType`'s own base particles); `.attributes` is the merged (own + inherited) view; `.attributes.base_attributes` is `None` when there's no extension, and an `XsdAttributeGroup` of just the inherited attributes otherwise.

- [ ] **Step 2: Write the failing tests**

```python
# tests/extraction/test_complex_types.py
"""Tests for complex-type extraction: extends/abstract, the recursive
Sequence/Choice content model (including nested groups and anonymous
complex types), and attribute uses -- against real MiKaDiv-FM types.
"""
import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.complex_types import (
    XSDO,
    extract_complex_type,
    extract_element_declaration_with_recursion,
)
from extraction.uris import global_uri

EX = Namespace("https://example.org/test/")
FACHTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd"
PERSONENTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
MELDEART13 = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd"
ROOT = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"


def test_plain_sequence_type_with_no_extension():
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonBasisType"]
    uri = EX.PersonBasisType
    graph = Graph()

    extract_complex_type(graph, t, uri)

    assert (uri, RDF.type, XSDO.ComplexTypeDefinition) in graph
    assert graph.value(uri, XSDO.abstract).toPython() is True
    assert graph.value(uri, XSDO.extends) is None
    content = graph.value(uri, XSDO.contentModel)
    assert (content, RDF.type, XSDO.Sequence) in graph
    particles = list(graph.objects(content, XSDO.hasParticle))
    assert len(particles) == 1


def test_extension_from_abstract_base_captures_only_own_particles():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    base = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}PaymentlineBasisType"]
    ext = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}Paymentline45BBasisType"]
    ext_uri, base_uri = EX.Ext, EX.Base
    graph = Graph()

    extract_complex_type(graph, base, base_uri)
    extract_complex_type(graph, ext, ext_uri)

    assert graph.value(base_uri, XSDO.abstract).toPython() is True
    assert graph.value(ext_uri, XSDO.abstract).toPython() is False
    assert graph.value(ext_uri, XSDO.extends) == global_uri(
        "http://www.itzbund.de/MiKaDiv/FMFach/1.02", "PaymentlineBasisType"
    )
    content = graph.value(ext_uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    assert len(particles) == 1  # only AusschuettendeGesellschaft -- not ISIN/Zahlungstag


def test_extension_attribute_uses_exclude_inherited_attributes():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    ext = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}Paymentline45BBasisType"]
    uri = EX.Ext
    graph = Graph()

    extract_complex_type(graph, ext, uri)

    attribute_uses = list(graph.objects(uri, XSDO.hasAttributeUse))
    names = set()
    for use in attribute_uses:
        term = graph.value(use, XSDO["term"])
        names.add(str(graph.value(term, XSDO.name)))
    assert names == {"ArtDesWertpapieres", "COAF"}  # not ISIN/Zahlungstag (inherited)

    coaf_use = next(
        u for u in attribute_uses
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name)) == "COAF"
    )
    assert graph.value(coaf_use, XSDO.required).toPython() is True
    art_use = next(
        u for u in attribute_uses
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name)) == "ArtDesWertpapieres"
    )
    assert graph.value(art_use, XSDO.required).toPython() is False


def test_choice_nested_inside_sequence_is_extracted_recursively():
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonType"]
    uri = EX.PersonType
    graph = Graph()

    extract_complex_type(graph, t, uri)

    outer = graph.value(uri, XSDO.contentModel)
    assert (outer, RDF.type, XSDO.Sequence) in graph
    outer_particles = list(graph.objects(outer, XSDO.hasParticle))
    assert len(outer_particles) == 1
    nested = graph.value(outer_particles[0], XSDO["term"])
    assert (nested, RDF.type, XSDO.Choice) in graph
    nested_particles = list(graph.objects(nested, XSDO.hasParticle))
    assert len(nested_particles) == 2
    element_names = set()
    for particle in nested_particles:
        element_uri = graph.value(particle, XSDO["term"])
        element_names.add(str(graph.value(element_uri, XSDO.name)))
    assert element_names == {"EinzelPerson", "SonstigeGemeinschaft"}


def test_anonymous_complex_type_recurses_through_nested_levels():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    content = graph.value(uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    konto_liste_uri = next(
        graph.value(p, XSDO["term"])
        for p in particles
        if str(graph.value(graph.value(p, XSDO["term"]), XSDO.name)) == "KontoListe"
    )
    konto_liste_type_uri = graph.value(konto_liste_uri, XSDO.type)
    assert (konto_liste_type_uri, RDF.type, XSDO.ComplexTypeDefinition) in graph

    konto_content = graph.value(konto_liste_type_uri, XSDO.contentModel)
    konto_particle = next(iter(graph.objects(konto_content, XSDO.hasParticle)))
    konto_uri = graph.value(konto_particle, XSDO["term"])
    assert str(graph.value(konto_uri, XSDO.name)) == "Konto"

    konto_type_uri = graph.value(konto_uri, XSDO.type)
    attribute_uses = list(graph.objects(konto_type_uri, XSDO.hasAttributeUse))
    assert len(attribute_uses) == 2


def test_identity_constraint_attaches_to_the_elements_own_named_type():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    verwahrkette_type_uri = global_uri(
        "http://www.itzbund.de/MiKaDiv/FMFach/1.02", "VerwahrketteType"
    )
    constraints = list(graph.objects(verwahrkette_type_uri, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    assert str(graph.value(constraints[0], XSDO.selector)) == (
        "fmfach:Verwahrstelle | fmfach:DepotfuehrendeStelle"
    )
    # and NOT attached to Meldeart13 itself
    assert list(graph.objects(uri, XSDO.hasIdentityConstraint)) == []


def test_identity_constraint_attaches_to_an_anonymous_owning_type():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    content = graph.value(uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    konto_liste_uri = next(
        graph.value(p, XSDO["term"])
        for p in particles
        if str(graph.value(graph.value(p, XSDO["term"]), XSDO.name)) == "KontoListe"
    )
    konto_liste_type_uri = graph.value(konto_liste_uri, XSDO.type)

    constraints = list(graph.objects(konto_liste_type_uri, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    fields = {str(f) for f in graph.objects(constraints[0], XSDO.field)}
    assert fields == {"@ArtDesDepotkontos", "@Kontonummer"}


def test_all_content_model_raises_named_error():
    import tempfile, os
    xsd = """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:test:all" xmlns:tns="urn:test:all"
           elementFormDefault="qualified">
  <xs:complexType name="AllType">
    <xs:all>
      <xs:element name="A" type="xs:string"/>
    </xs:all>
  </xs:complexType>
</xs:schema>
"""
    fd, path = tempfile.mkstemp(suffix=".xsd")
    os.write(fd, xsd.encode())
    os.close(fd)
    schema = xmlschema.XMLSchema(path)
    t = schema.maps.types["{urn:test:all}AllType"]
    graph = Graph()

    with pytest.raises(NotImplementedError):
        extract_complex_type(graph, t, EX.AllType)


def test_element_declaration_with_recursion_extracts_the_root_elements_own_identity_constraints():
    schema = xmlschema.XMLSchema(ROOT)
    root_element = schema.maps.elements["{http://www.itzbund.de/MiKaDiv/FM/1.02}MiKaDivFMRoot"]
    uri = EX.MiKaDivFMRoot
    graph = Graph()

    extract_element_declaration_with_recursion(graph, root_element, uri)

    type_uri_value = graph.value(uri, XSDO.type)
    constraint_names = set()
    for c in graph.objects(type_uri_value, XSDO.hasIdentityConstraint):
        constraint_names.add(str(c).rsplit(".", 1)[-1])
    assert constraint_names == {"UUIDIstEindeutig", "ZulassungsnummerIstEindeutig"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extraction/test_complex_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.complex_types'`

- [ ] **Step 4: Write the implementation**

```python
# extraction/complex_types.py
"""Complex-type extraction: xsdo:extends/xsdo:abstract, the recursive
Sequence/Choice content model (including nested groups and anonymous
complex types -- both real, confirmed in this corpus:
MiKaDiv_FM_Personentypen's PersonType nests a Choice inside a Sequence;
MiKaDiv_FM_Meldeart13's KontoListe/Konto nests an anonymous complex
type three levels deep), and xsdo:hasAttributeUse.

This module and extraction.declarations are mutually recursive by
nature (a type's content is elements; an element's type can itself be
an anonymous complex type) -- resolved via dependency injection:
extract_element_declaration_with_recursion below supplies this
module's own extract_complex_type as declarations.py's
extract_anonymous_complex_type callback, instead of a circular import.

Per this plan's Global Constraints, xsdo:hasIdentityConstraint attaches
to the URI of the type that governs the element the constraint is
declared on -- computed the same way as that element's own xsdo:type
link -- not to whatever type's content model happens to contain the
element as a particle. Required for compatibility with the already-
built equivalence checker, whose identity_constraints.compare() reads
this property from a type URI.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from extraction.declarations import extract_attribute_declaration, extract_element_declaration
from extraction.identity_constraints import extract_identity_constraints
from extraction.uris import child_uri, type_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


def extract_element_declaration_with_recursion(
    graph: Graph, xsd_element, uri: URIRef
) -> None:
    extract_element_declaration(
        graph, xsd_element, uri, extract_anonymous_complex_type=extract_complex_type
    )
    if xsd_element.identities:
        constraint_owner_uri = type_uri(xsd_element.type, uri)
        extract_identity_constraints(graph, xsd_element, constraint_owner_uri)


def extract_complex_type(graph: Graph, xsd_type, uri: URIRef) -> None:
    graph.add((uri, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((uri, XSDO.targetNamespace, Literal(xsd_type.target_namespace)))
    graph.add((uri, XSDO.abstract, Literal(bool(xsd_type.abstract))))

    if xsd_type.base_type is not None:
        graph.add((uri, XSDO.extends, type_uri(xsd_type.base_type, uri)))

    content_node = _extract_content_model(graph, xsd_type.content, uri)
    graph.add((uri, XSDO.contentModel, content_node))

    base_attribute_names = set(xsd_type.attributes.base_attributes or ())
    for name, attribute in xsd_type.attributes.items():
        if name in base_attribute_names:
            continue
        attribute_uri = child_uri(uri, f"@{attribute.local_name}")
        extract_attribute_declaration(
            graph, attribute, attribute_uri, extract_anonymous_complex_type=extract_complex_type
        )
        use_node = BNode()
        graph.add((uri, XSDO.hasAttributeUse, use_node))
        graph.add((use_node, XSDO.required, Literal(attribute.use == "required")))
        graph.add((use_node, XSDO["term"], attribute_uri))


def _extract_content_model(graph: Graph, group, owner_uri: URIRef) -> BNode:
    if group.model == "all":
        raise NotImplementedError(
            "xs:all is confirmed absent from every real file this extractor "
            "targets -- see the extraction design spec's census"
        )

    group_node = BNode()
    graph.add(
        (group_node, RDF.type, XSDO.Choice if group.model == "choice" else XSDO.Sequence)
    )

    for position, particle in enumerate(group.iter_model(), start=1):
        particle_node = BNode()
        graph.add((group_node, XSDO.hasParticle, particle_node))
        graph.add((particle_node, XSDO.particlePosition, Literal(position)))
        graph.add((particle_node, XSDO.minOccurs, Literal(particle.min_occurs)))
        if particle.max_occurs is None:
            graph.add((particle_node, XSDO.maxOccursUnbounded, Literal(True)))
        else:
            graph.add((particle_node, XSDO.maxOccurs, Literal(particle.max_occurs)))

        if isinstance(particle, xmlschema.validators.groups.XsdGroup):
            nested_node = _extract_content_model(graph, particle, owner_uri)
            graph.add((particle_node, XSDO["term"], nested_node))
        else:
            element_uri = child_uri(owner_uri, particle.local_name)
            extract_element_declaration_with_recursion(graph, particle, element_uri)
            graph.add((particle_node, XSDO["term"], element_uri))

    return group_node
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_complex_types.py -v`
Expected: PASS, 8/8

- [ ] **Step 6: Commit**

```bash
git add extraction/complex_types.py tests/extraction/test_complex_types.py
git commit -m "feat: add complex-type and recursive content-model extraction"
```

---

## Task 6: Top-level orchestration

**Files:**
- Create: `extraction/extract.py`
- Test: `tests/extraction/test_extract.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: `extract(xsd_path: str) -> rdflib.Graph` — the spec's own top-level signature, used by future sub-projects and by Task 7's `attach_english_documentation`.

- [ ] **Step 1: Confirm the real entry-point enumeration API**

Already verified live during this plan's design against `MiKaDiv_FM_1.02.xsd`:

```bash
python3 -c "
import xmlschema
schema = xmlschema.XMLSchema('ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd')
own_types = [t for name, t in schema.maps.types.items() if not name.startswith('{http://www.w3.org/2001/XMLSchema}')]
print('non-builtin types:', len(own_types))
own_elements = [e for name, e in schema.maps.elements.items() if not name.startswith('{http://www.w3.org/2001/XMLSchema}')]
print('global elements:', len(own_elements), [e.local_name for e in own_elements])
"
```

Expected: 143 non-builtin types (99 complex + 44 simple, reachable transitively via the entry point's own real `xs:import`s — confirms extraction only needs to be pointed at the entry point, matching the spec's own design) and exactly 1 real global element, `MiKaDivFMRoot` (every other real element in the family is a local particle, reached recursively via content-model walking, not top-level iteration).

- [ ] **Step 2: Write the failing tests**

```python
# tests/extraction/test_extract.py
"""End-to-end tests for extract(xsd_path) against the real, official
MiKaDiv-FM package -- one real construct per spec test case, all
sharing one real parse via a module-scoped fixture.
"""
import pytest
from rdflib import RDF, Namespace

from extraction.extract import extract
from extraction.uris import global_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
ROOT = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"

FM = "http://www.itzbund.de/MiKaDiv/FM/1.02"
FMSTD = "http://www.itzbund.de/MiKaDiv/FMStd/1.02"
FMPERS = "http://www.itzbund.de/MiKaDiv/FMPers/1.02"
FMFACH = "http://www.itzbund.de/MiKaDiv/FMFach/1.02"


@pytest.fixture(scope="module")
def graph():
    return extract(ROOT)


def test_abstract_base_and_extending_type_are_both_present(graph):
    base = global_uri(FMSTD, "NachrichtenType")
    ext = global_uri(FM, "DLZertifiziert")
    assert graph.value(base, XSDO.abstract).toPython() is True
    assert graph.value(ext, XSDO.extends) == base


def test_choice_affected_person_type_is_reachable(graph):
    person_type = global_uri(FMPERS, "PersonType")
    assert (person_type, RDF.type, XSDO.ComplexTypeDefinition) in graph
    outer = graph.value(person_type, XSDO.contentModel)
    particles = list(graph.objects(outer, XSDO.hasParticle))
    nested = graph.value(particles[0], XSDO["term"])
    assert (nested, RDF.type, XSDO.Choice) in graph


def test_union_type_is_reachable_with_all_three_members(graph):
    geburtsdatum = global_uri(FMSTD, "GeburtsdatumType")
    members = {str(m).rsplit("#", 1)[-1] for m in graph.objects(geburtsdatum, XSDO.hasUnionMember)}
    assert members == {"Datum0Type", "Datum1880Type", "Datum0000Type"}


def test_real_facet_set_is_reachable():
    schema_graph = extract(ROOT)
    wid_type = global_uri(FMSTD, "WIDType")
    assert int(schema_graph.value(wid_type, XSDO.length)) == 16
    patterns = {str(p) for p in schema_graph.objects(wid_type, XSDO.pattern)}
    assert patterns == {"DE[0-9]{14}"}


def test_composite_identity_constraint_is_reachable(graph):
    verwahrkette_type = global_uri(FMFACH, "VerwahrketteType")
    assert list(graph.objects(verwahrkette_type, XSDO.hasIdentityConstraint))


def test_required_and_optional_attribute_uses_are_both_present(graph):
    ext = global_uri(FMFACH, "Paymentline45BBasisType")
    required_names, optional_names = set(), set()
    for use in graph.objects(ext, XSDO.hasAttributeUse):
        term = graph.value(use, XSDO["term"])
        name = str(graph.value(term, XSDO.name))
        if graph.value(use, XSDO.required).toPython():
            required_names.add(name)
        else:
            optional_names.add(name)
    assert "COAF" in required_names
    assert "ArtDesWertpapieres" in optional_names


def test_default_and_fixed_values_are_reachable(graph):
    position = global_uri(FMFACH, "AuszahlendeStellePositionType.@Position")
    # Position is a local attribute of an anonymous type in this corpus;
    # locate it via the real declaring type's own attribute use instead.
    verwahrkette_type = global_uri(FMFACH, "VerwahrketteType")
    flag_uses = [
        u for u in graph.objects(verwahrkette_type, XSDO.hasAttributeUse)
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name))
        == "AuszahlStelleIstDepotfuehrStelle"
    ]
    assert len(flag_uses) == 1
    flag_attr = graph.value(flag_uses[0], XSDO["term"])
    assert str(graph.value(flag_attr, XSDO.defaultValue)) == "false"


def test_untagged_german_documentation_is_reachable(graph):
    root_uri = global_uri(FM, "MiKaDivFMRoot")
    docs = list(graph.objects(root_uri, XSDO.documentation))
    assert len(docs) == 1
    assert docs[0].language is None
    assert str(docs[0]) == "Root-Element für die Nutzdaten."
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extraction/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.extract'`

- [ ] **Step 4: Write the implementation**

```python
# extraction/extract.py
"""Top-level orchestration: extract(xsd_path) -> rdflib.Graph. Walks
every global complex/simple type plus the real family's own global
element(s) (confirmed: exactly one, MiKaDivFMRoot -- every other real
element is a local particle, reached recursively via
extraction.complex_types's own content-model walk, not this loop).
"""
from __future__ import annotations

import xmlschema
from rdflib import Graph

from extraction.complex_types import extract_complex_type, extract_element_declaration_with_recursion
from extraction.simple_types import extract_simple_type
from extraction.uris import global_uri

_XS_NAMESPACE_PREFIX = "{http://www.w3.org/2001/XMLSchema}"


def extract(xsd_path: str) -> Graph:
    schema = xmlschema.XMLSchema(xsd_path)
    graph = Graph()

    for name, xsd_type in schema.maps.types.items():
        if name.startswith(_XS_NAMESPACE_PREFIX):
            continue
        uri = global_uri(xsd_type.target_namespace, xsd_type.local_name)
        if isinstance(xsd_type, xmlschema.validators.complex_types.XsdComplexType):
            extract_complex_type(graph, xsd_type, uri)
        elif isinstance(xsd_type, xmlschema.validators.simple_types.XsdSimpleType):
            extract_simple_type(graph, xsd_type, uri)

    for name, xsd_element in schema.maps.elements.items():
        if name.startswith(_XS_NAMESPACE_PREFIX):
            continue
        uri = global_uri(xsd_element.target_namespace, xsd_element.local_name)
        extract_element_declaration_with_recursion(graph, xsd_element, uri)

    return graph
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extraction/test_extract.py -v`
Expected: PASS, 8/8

- [ ] **Step 6: Commit**

```bash
git add extraction/extract.py tests/extraction/test_extract.py
git commit -m "feat: add top-level extract(xsd_path) orchestration"
```

---

## Task 7: English documentation from the official Annex PDF

**Files:**
- Create: `extraction/annex_pdf.py`
- Modify: `pyproject.toml` (add `pdfplumber` dependency)
- Test: `tests/extraction/test_annex_pdf.py`

**Interfaces:**
- Consumes: `XSDO` (own definition, matching this plan's convention).
- Produces: `attach_english_documentation(graph: Graph, pdf_path: str) -> None` — mutates an already-extracted graph in place, adding an `@en`-tagged `xsdo:documentation` value to every subject whose `xsdo:name` matches a name found in the PDF. Matches the spec's own explicit scope: "do it as part of this sub-project," not deferred.

- [ ] **Step 1: Confirm the real `pdfplumber` extraction approach**

**`pdfplumber`'s own `extract_tables()` does not work for this PDF** — already verified directly during this plan's design and worth re-confirming as an executable check before writing real code against it:

```bash
python3 -m pip install --break-system-packages pdfplumber
python3 -c "
import pdfplumber
path = 'ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[15]  # page 16, 0-indexed -- contains NachrichtUUID
    for t in page.extract_tables():
        for row in t:
            print(row)
"
```

Expected: the `Attributes` row's Name/Type/Use/Documentation columns come back merged into one blob string (e.g. `'Attributes', 'Name Type Use Default Documentation\\nNachrichtUUID std:UUIDType M\\nUnique\\nidentifier for\\nthe\\nmessage.'`) even though the page has real ruling lines (`len(page.edges)` is in the hundreds) — `extract_tables()`'s row/column splitting is defeated by this PDF's nested sub-table layout.

The real, verified-working alternative — word-position clustering:

```bash
python3 -c "
import pdfplumber
path = 'ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf'
with pdfplumber.open(path) as pdf:
    page = pdf.pages[15]
    words = page.extract_words()
    header = [w for w in words if w['text'] in ('Name', 'Documentation') and 630 < w['top'] < 645]
    print(sorted((round(w['x0'],1), w['text']) for w in header))
    sub = [w for w in words if 637 < w['top'] < 730]
    for w in sorted(sub, key=lambda w: w['top']):
        print(round(w['x0'], 1), round(w['top'], 1), w['text'])
"
```

Expected: the header row gives clean column x-positions (`Name` at `x0≈122.4`, `Documentation` at `x0≈473.3`); the data rows below cluster cleanly by `top` (y-position) into visual rows, with `NachrichtUUID`'s wrapped documentation ("Unique identifier for the message.") appearing as separate one-or-two-word visual rows all at the Documentation column's `x0≈478.7` — confirming that clustering words by `top` into rows, then classifying each row by whether it has a word at the Name column's `x0` (a new record) or only at the Documentation column's `x0` (a continuation of the previous record's text), correctly recovers the real per-attribute documentation.

- [ ] **Step 2: Add the `pdfplumber` dependency**

In `pyproject.toml`, add `"pdfplumber>=0.11"` to `dependencies`.

- [ ] **Step 3: Write the failing tests**

```python
# tests/extraction/test_annex_pdf.py
"""Tests for English documentation extraction from the real Annex PDF,
matched by name against an already-extracted graph."""
from rdflib import Graph, Literal, Namespace, RDF

from extraction.annex_pdf import attach_english_documentation
from extraction.extract import extract
from extraction.uris import global_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
ROOT_XSD = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"

FM = "http://www.itzbund.de/MiKaDiv/FM/1.02"


def test_root_elements_english_documentation_is_attached_alongside_german():
    graph = extract(ROOT_XSD)
    root_uri = global_uri(FM, "MiKaDivFMRoot")

    attach_english_documentation(graph, ANNEX_PDF)

    docs = {(str(d), d.language) for d in graph.objects(root_uri, XSDO.documentation)}
    assert ("Root-Element für die Nutzdaten.", None) in docs
    assert ("Root element for the user data.", "en") in docs


def test_wrapped_multi_line_documentation_is_joined_into_one_string():
    graph = extract(ROOT_XSD)
    # NachrichtUUID is a local attribute of the anonymous MeldungListe45bType
    # extension chain -- easiest to locate via a fresh, minimal fixture graph
    # instead of threading through the real nesting.
    subject = global_uri(FM, "NachrichtUUID")
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("NachrichtUUID")))

    attach_english_documentation(graph, ANNEX_PDF)

    english_docs = [d for d in graph.objects(subject, XSDO.documentation) if d.language == "en"]
    assert len(english_docs) == 1
    assert str(english_docs[0]) == "Unique identifier for the message."


def test_a_name_not_present_in_the_pdf_gets_no_english_documentation():
    graph = Graph()
    subject = global_uri(FM, "SomeNameNotInThePdf")
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("SomeNameNotInThePdf")))

    attach_english_documentation(graph, ANNEX_PDF)

    assert list(graph.objects(subject, XSDO.documentation)) == []
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/extraction/test_annex_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'extraction.annex_pdf'`

- [ ] **Step 5: Write the implementation**

```python
# extraction/annex_pdf.py
"""English documentation extraction from BZSt's official Annex PDF
(khb_mikadiv_fm_anlage_en_v3.pdf), matched by real element/attribute
name against an already-extracted xsdo: graph, attached as a second,
@en-tagged xsdo:documentation value alongside the XSD's own untagged
German text. In scope for this sub-project per explicit instruction
(see the extraction design spec) -- not deferred.

pdfplumber's own extract_tables() garbles this PDF's nested Attributes/
Elements sub-tables (verified directly -- see this plan's Task 7 Step
1); word-position clustering via extract_words() is the real,
verified-working alternative used here.
"""
from __future__ import annotations

import pdfplumber
from rdflib import Graph, Literal, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_ROW_Y_TOLERANCE = 1.0
_COLUMN_X_TOLERANCE = 5.0


def _cluster_rows(words: list[dict], y_tolerance: float = _ROW_Y_TOLERANCE) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: w["top"]):
        for row in rows:
            if abs(row[0]["top"] - word["top"]) <= y_tolerance:
                row.append(word)
                break
        else:
            rows.append([word])
    return rows


def _find_columns(words: list[dict]) -> tuple[float, float] | None:
    name_word = next((w for w in words if w["text"] == "Name"), None)
    doc_word = next((w for w in words if w["text"] == "Documentation"), None)
    if name_word is None or doc_word is None:
        return None
    return name_word["x0"], doc_word["x0"]


def _extract_name_to_documentation(pdf_path: str) -> dict[str, str]:
    results: dict[str, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            columns = _find_columns(words)
            if columns is None:
                continue
            name_x, doc_x = columns

            current_name = None
            for row in _cluster_rows(words):
                row_sorted = sorted(row, key=lambda w: w["x0"])
                name_word = next(
                    (
                        w for w in row_sorted
                        if abs(w["x0"] - name_x) < _COLUMN_X_TOLERANCE and w["text"] != "Name"
                    ),
                    None,
                )
                doc_words = [w for w in row_sorted if w["x0"] >= doc_x - _COLUMN_X_TOLERANCE]
                doc_text = " ".join(w["text"] for w in doc_words)

                if name_word is not None:
                    current_name = name_word["text"]
                    if doc_text:
                        results[current_name] = doc_text
                elif doc_text and current_name is not None:
                    results[current_name] = (results.get(current_name, "") + " " + doc_text).strip()

    return results


def attach_english_documentation(graph: Graph, pdf_path: str) -> None:
    name_to_documentation = _extract_name_to_documentation(pdf_path)
    for subject in set(graph.subjects(XSDO.name, None)):
        name = str(graph.value(subject, XSDO.name))
        english_text = name_to_documentation.get(name)
        if english_text:
            graph.add((subject, XSDO.documentation, Literal(english_text, lang="en")))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/extraction/test_annex_pdf.py -v`
Expected: PASS, 3/3

- [ ] **Step 7: Run the full extraction test suite**

Run: `pytest tests/extraction/ -v`
Expected: PASS, all tests across all 7 tasks

- [ ] **Step 8: Commit**

```bash
git add extraction/annex_pdf.py tests/extraction/test_annex_pdf.py pyproject.toml
git commit -m "feat: add English documentation extraction from the official Annex PDF"
```

---

## Definition of Done

- `extract(xsd_path)` runs against the real `MiKaDiv_FM_1.02.xsd` entry point and produces a complete `xsdo:` graph covering every construct kind the spec's census confirms is real: `xs:extension`/`abstract`, `xs:choice` (including nested), the full 12-facet set, `xs:union`, identity constraints (`xs:unique` real; `xs:key`/`xs:keyref` supported but synthetic-tested), attribute uses (`required`/`optional`, `default`/`fixed`), and both real documentation forms (FM's untagged German, and the tagged form via the shared `declarations.py` code path).
- `xs:all`, `substitutionGroup`, `mixed="true"`, `xs:assert`/`xs:assertion`/`xs:any`/`xs:anyAttribute` all either raise a named error (`xs:all`) or are simply never reached by any code path (the rest) — no silent mishandling.
- `attach_english_documentation` correctly matches and attaches real English text from the official Annex PDF for at least `MiKaDivFMRoot` and `NachrichtUUID`, verified against the real PDF's actual content, not assumed.
- No claim of full-schema content coverage — every *construct kind* is proven; not every one of the real family's ~123 elements/149 attributes/111 complex types/56 simple types has been individually reviewed.
