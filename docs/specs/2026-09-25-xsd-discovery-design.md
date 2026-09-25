# XSD Discovery — Design

## Context

This is the first real slice of the reference-model spec's 4th and last
original Roadmap item, the extraction/discovery pipeline
(`docs/specs/2026-09-23-source-reference-model-design.md`, item 4):
deciding what actually needs citing from the real MiKaDiv-FM sources, so
far always done by hand (every citation in this project's own tests uses
a hardcoded XPath a human wrote by reading the schema directly).

Settled during brainstorming, corrected twice from an initially too-narrow
framing:

1. **Structure and content are not treated differently.** There is no
   "leaf element" vs. "structural element" distinction — a renamed
   wrapper or reordered children is just as real a drift event as a
   changed terminal value, and (checked against the real corpus) the
   distinction doesn't even correspond to a real category boundary in
   this schema's own authoring style: every `xs:element` declaration here
   is a flat `name`+`type` pair, with actual nesting living in separately
   defined `xs:complexType`s.
2. **This is format-agnostic in the same way selectors already are — a
   shared pattern, not one shared algorithm.** Discovery follows the same
   per-format extensibility this project already uses for resolvers: an
   XSD discoverer can mechanically walk a real tree structure. A PDF has
   no equivalent walk — there's no tree to enumerate, only visual regions
   a human has to identify — so a PDF discoverer is a fundamentally
   different (and not yet designed) problem, not a variant of this one.
3. **Complete coverage of the category, not a hand-picked subset.**
   Every named XML Schema construct is a candidate — elements,
   complexTypes, simpleTypes, attributes, groups, attributeGroups,
   anything bearing a `name` attribute in the XML Schema namespace — not
   an arbitrarily narrower list chosen because it looked smaller or
   matched what existing hand-written citations happened to use.

## Non-Goals

- **Not** a PDF discoverer. Genuinely a different problem; not designed
  here, and may never have a mechanical equivalent.
- **Not** any judgment about which candidates are worth citing. Every
  discovered candidate is equally valid; deciding what actually gets
  cited is entirely a human's job, using `cite()`/`save_reference()`,
  already built.
- **Not** a UI. This is a tested Python module — a function you call and
  inspect results from. Wiring discovered candidates into `webapp` (and
  deciding how a human picks from the list) is separate, later work.
- **Not** automatic writing to the catalog. Nothing here calls
  `save_reference()`. A human reviews the candidate list and manually
  cites whatever they choose.
- **Not** resolving `xs:element[@ref=...]` usage sites back to their
  referenced definitions. `ref` and `name` are mutually exclusive on
  `xs:element` in XSD itself, so a `ref` usage naturally has no `name`
  attribute and is correctly excluded from candidates by the same rule
  that includes everything else — no special-casing needed.
- **Not** cross-file deduplication. Each file is walked independently;
  the same conceptual field appearing in two different files/contexts
  produces two separate, independently real candidates, because they
  really are different XML tree locations.

## `discovery/xsd_discoverer.py`

New top-level package, `discovery/`, sibling to `reference_model/` and
the other already-merged packages — the natural home for format-specific
discoverers as more get built later (a PDF discoverer, if one is ever
designed, would live alongside this as `discovery/pdf_discoverer.py`).

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
    """`match_count` is the raw number of nodes the computed `xpath`
    evaluated to: 0 means the path didn't resolve at all (including a
    path that failed to even parse as valid XPath, e.g. an unescaped
    quote in a `name`, or one that resolved to zero or to the wrong node
    entirely due to a non-XSD-namespace ancestor along the way); 2+ means
    a genuine ambiguity (multiple real nodes share the same computed
    path). Both are folded into this one type rather than a raw exception
    or a silently-dropped candidate, per this module's own "recorded,
    never silently wrong" rule -- not because they're the same failure.
    """

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
        tag = etree.QName(node).localname
        name = node.get("name")
        try:
            matches = tree.xpath(xpath, namespaces={"xs": _XS_NS})
        except etree.XPathEvalError:
            # An unescaped quote in `name` (never valid per XSD's own
            # NCName rule, but this module doesn't validate that) breaks
            # the generated predicate's own quoting -- record it as
            # unresolvable rather than letting the whole file's discovery
            # crash on one malformed name.
            excluded.append(ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=0))
            continue
        if len(matches) == 1 and matches[0] is node:
            candidates.append(Candidate(tag=tag, name=name, xpath=xpath))
        else:
            excluded.append(
                ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=len(matches))
            )
    return DiscoveryResult(candidates=tuple(candidates), excluded=tuple(excluded))
```

**The candidate rule is one uniform test, not a list of allowed tags**:
any node whose tag is in the XML Schema namespace and carries a `name`
attribute. This covers every current XSD construct type uniformly and
any future one without code changes — the alternative (enumerating
`xs:element`, `xs:complexType`, `xs:attribute`, ... by name) would be
exactly the kind of arbitrary, easy-to-under-cover subset this design
explicitly rejects.

**The XPath is built root-to-node**, using a `[@name='...']` predicate at
every ancestor that has one and the bare tag name otherwise — this is
mechanically identical to how every hand-written XPath already used
throughout this project's tests was built by a human reading the schema.
It always emits the `xs:` prefix for the XML Schema namespace regardless
of whatever prefix the source document happens to bind that namespace to,
because the output must match what `XPathSelector`'s own resolver expects
(`{"xs": "http://www.w3.org/2001/XMLSchema"}`, hardcoded there already) —
not whatever the document's own authors chose.

**Every computed path is verified live**, not trusted — `discover_candidates()`
evaluates each one against the real parsed document and only returns it
as a `Candidate` if it resolves to exactly one node **and that node is
the very one that produced the path** (`matches[0] is node`, not just
`len(matches) == 1`) — a bare, prefix-less path step for a
non-XSD-namespace ancestor means "null namespace" in XPath 1.0, not
"whatever namespace this document's author actually used there", so two
unrelated nodes under differently-namespaced same-local-name ancestors
can otherwise compute to the identical string and silently confirm each
other. A path that doesn't resolve to itself uniquely (a genuine
ambiguity, like two structurally-identical siblings under an `xs:choice`;
a namespace mismatch like the one above; or a `name` value that breaks
the generated predicate's own XPath syntax, like an unescaped quote)
becomes an `ExcludedCandidate` instead — recorded, with the real match
count, never silently dropped and never silently wrong.

## Testing strategy

Dogfooded against the real MiKaDiv-FM corpus (`/work/ontologies/mikadiv-fm/sources/1.02/xsd/`,
13 real files):

- Running `discover_candidates()` on the real `MiKaDiv_FM_Meldeart23_1.02.xsd`
  produces a candidate whose `xpath` exactly equals `AORDNR_XPATH` (this
  session's own long-established ground-truth constant, hand-written by a
  human and depended on by dozens of tests across five already-merged
  sub-projects) and `name == "AOrdNr"`; likewise for `ABGEF_XPATH`/
  `"AbgefKapitalertragsteuer"`. This is the strongest correctness check
  available: the algorithm must reproduce, exactly, byte for byte, paths
  a human already wrote and this whole project already trusts.
- The same run's candidates include `xs:complexType` entries too (e.g.
  `"Meldeart23"` and `"AmtlicheOrdnungsnummerMa23ListeType"`) — proving
  structural constructs are discovered, not just elements.
- Every candidate's `xpath`, independently re-evaluated against the same
  parsed document, resolves to exactly one node — the "verified unique"
  guarantee checked as a real property of the whole real candidate list,
  not just the two ground-truth examples above.
- No two candidates in one file's result share the same `xpath` string —
  a global uniqueness invariant across the full candidate list.
- `len(candidates) + len(excluded)` equals an independently-computed count
  of every named XML Schema node in the document — a completeness
  invariant proving nothing is silently lost, regardless of whether any
  real ambiguous case exists in this particular corpus.
- Running `discover_candidates()` against **all 13 real XSD files** in
  the corpus, not just `Meldeart23`, completes without exception and
  returns at least one candidate per file — proving this is a genuinely
  robust mechanical walker, not something that happens to work on the one
  file this project's tests have leaned on most.
- A synthetic fixture (a small, hand-written XSD: an `xs:choice` with two
  sibling `xs:sequence` blocks, each containing an `xs:element` with the
  *same* `name` — so both elements compute to the identical path, since
  neither `xs:sequence` has a distinguishing predicate) proves the
  exclusion path itself actually triggers, with the correct `match_count`
  (2), since the real corpus (confirmed live: zero exclusions across all
  13 real files) doesn't happen to contain a naturally-occurring example.

## Roadmap: what this enables next

- **Wiring discovered candidates into `webapp`** — a page/endpoint
  listing candidates (cross-referenced against what's already in the
  references catalog, so a human sees "already cited" vs. "not yet") is
  the natural next slice, deliberately not built here.
- **A PDF discoverer** — a genuinely different, not-yet-designed problem;
  no mechanical tree-walk equivalent exists for a PDF's visual layout.
- **Discovering across the whole corpus in one call** — today a caller
  loops over files themselves; a thin wrapper walking every `.xsd` under
  a module root is a trivial, later convenience, not a new algorithm.
- **The interaction layer** connecting a discovered candidate to an
  actual `cite()` + `save_reference()` call, and to a real `fact_key` a
  human assigns — still entirely manual today, and still named as
  separate, later work in `review_recording`'s/`review_consultation`'s
  own Roadmaps.

## Definition of Done

- `discovery/xsd_discoverer.py` implements `Candidate`,
  `ExcludedCandidate`, `DiscoveryResult`, and `discover_candidates()` with
  the semantics above.
- All tests listed above pass, run against the real MiKaDiv-FM corpus
  (all 13 real XSD files) plus one synthetic fixture for the exclusion
  path.
- `discover_candidates()` on the real `Meldeart23` schema reproduces
  `AORDNR_XPATH`/`ABGEF_XPATH` exactly.
