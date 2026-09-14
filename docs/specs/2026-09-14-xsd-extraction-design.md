# XSD Extraction Logic — Design

Sub-project 3a of `/work/openfaster-restructuring/STATUS.md` (split off
from the originally-scoped "sub-project 3: mikadiv-fm", per the
brainstorming scope-assessment — see that file's roadmap and decision
log for full context). This document covers only the extraction
logic's own architecture and scope: turning a real, official XSD into
`xsdo:`-shaped RDF facts. It does not curate any MiKaDiv-FM concepts,
and it does not teach the equivalence checker (sub-project 2, already
complete) to consume its output — both are explicitly separate,
later work.

## Context

The equivalence checker (`generator/equivalence/`) proves a
graph-generated XSD is behaviorally equivalent to an official one — but
it was built and tested entirely against small, hand-crafted synthetic
`xsdo:` fixtures, per its own Non-Goals: "No real XSD → `xsdo:`
extraction logic (assumes the input graphs already exist)." This
document is that missing half: given a real, official XSD, produce the
`xsdo:`-shaped RDF graph describing it.

Investigating the actual target material (MiKaDiv-FM's official BZSt
package, fetched and committed to `ontologies/mikadiv-fm/sources/` this
session) surfaced two things that materially change this design from a
naive "walk the object model" first draft:

1. **The real schema family is larger and more cross-referenced than
   any single file suggests**: 12 real XSD files plus a DIN SPEC 91379
   datatype dependency, tied together by a real entry-point schema
   (`MiKaDiv_FM_1.02.xsd`), with 5 distinct Meldearten (report types)
   and several shared type libraries imported across all of them.
2. **`xs:complexContent`/`xs:extension` (type inheritance) is
   pervasive** — the majority shape in `Personentypen.xsd`, not an edge
   case. Neither the existing `xsdo:` vocabulary (as used by the
   equivalence checker) nor any prior design in this project represents
   type inheritance at all.

Both are addressed explicitly below, rather than discovered mid-
implementation the way earlier sub-projects' real bugs were found
during their own TDD cycles.

## Scope

**In scope:**
- Loading a real, multi-file XSD family via `xmlschema` (already a
  pipeline dependency, already proven against MiKaDiv-FM's real package
  — confirmed it resolves the whole 12-file family cleanly from the
  entry point).
- Extracting: complex type definitions, simple type definitions,
  element declarations, **attribute declarations** (real target schemas
  use both — e.g. KaFE's `AccountNumber` is an attribute, not an
  element), `xsdo:Sequence` content models and their particles
  (position, `minOccurs`/`maxOccurs`/unbounded), the real facet set
  already established by the equivalence checker (enumeration, length/
  minLength/maxLength, pattern, minInclusive/maxInclusive, totalDigits/
  fractionDigits), and `xs:key`/`xs:unique`/`xs:keyref` identity
  constraints.
- **New: `xsdo:extends`.** A complex type using `xs:complexContent`/
  `xs:extension` gets a triple pointing at its base type. The extracted
  content model captures only that type's *own* additional particles —
  never a flattened duplicate of the base type's particles copied into
  every derived type. Resolving the full effective content model (base
  + all its own additions) means walking the `xsdo:extends` chain,
  which is a consumer's job (a future sub-project's), not something
  this extractor flattens away.

**Out of scope (explicit, separate, later work):**
- `xsdo:Choice`/`xsdo:All` content models — matches the equivalence
  checker's own existing Sequence-only scope cut; extraction raises a
  named, loud error for these rather than silently mis-extracting them,
  same discipline as `structural_cases.enumerate_cases`.
- Teaching the equivalence checker to understand `xsdo:extends` (walk
  the inheritance chain when enumerating structural cases or building
  documents) — real, separate work; this sub-project only needs to
  produce a *correct* graph, not make today's checker consume it.
- Curating any real MiKaDiv-FM concepts (semantic meaning, business
  rules) — this sub-project produces structural facts only.
- `xs:assert`/`xs:any`/`xs:anyAttribute` — confirmed absent from the
  real MiKaDiv-FM package (verified directly against all 13 files this
  session), so this is a non-issue for the actual target, not a gap
  being silently ignored. The extractor should still raise loudly if it
  ever encounters one, matching the equivalence checker's own guardrail
  philosophy, rather than silently mis-extracting.
- Extracting every one of the real family's ~123 elements — this
  sub-project proves the extraction logic is correct via a
  deliberately small, representative set of real types (see Testing
  strategy), not full content coverage. Full coverage is real
  content-curation work for whichever later sub-project actually
  curates MiKaDiv-FM.

## Architecture

### Package layout, inside `generator/extraction/`

```
extraction/
  __init__.py
  xsd_extractor.py   # the whole module -- see below for why this
                      # isn't split further yet
```

Unlike the equivalence checker (seven single-responsibility modules),
this starts as one module. Reasoning: the equivalence checker's seven
concerns (guardrail, leaf values, structural cases, document building,
type correspondence, identity constraints, orchestration) are each
independently meaningful and independently testable against synthetic
data with no shared walk of a single object model. Extraction is
fundamentally one walk over `xmlschema`'s object model, emitting
triples as it goes — splitting it prematurely into separate files
before real usage reveals natural seams would be speculative
structure, not genuine separation of concerns. Revisit if it grows
unwieldy once real content-curation work (a later sub-project) puts
real load on it.

### Step 0: verify `xmlschema`'s real object-model API before writing extraction logic

Two specific behaviors need direct verification, not assumption,
matching this project's own established norm (a prior test elsewhere
in this codebase shipped against a guessed, wrong library API and had
to be fixed after the fact):

1. **What does `XsdComplexType.content` return for a type using
   `xs:extension`?** Does it give the type's own additional particles
   only, or does `xmlschema` pre-merge the base type's particles in?
   This determines whether extraction can read `.content` directly for
   the "own particles" `xsdo:extends` needs, or whether it needs to
   diff against the base type's own `.content` first.
2. **How does `xmlschema` expose a type's base type when using
   extension** — a `.base_type` attribute, or something else?

Both get confirmed empirically (a small script against
`Personentypen.xsd`'s own real extension-using types) as the first
concrete implementation step, before any extraction code is written
that depends on the answer.

### Core extraction function

```
extract(xsd_path: str) -> rdflib.Graph
```

Given the path to a real XSD file (the family entry point, e.g.
`MiKaDiv_FM_1.02.xsd` — `xmlschema` resolves the rest of the family via
its own real `xs:import` handling), returns one `rdflib.Graph`
containing `xsdo:`-shaped facts for every global complex type, simple
type, and element/attribute declaration `xmlschema` resolves, walking
each complex type's content model recursively.

### Complex type extraction

For each `xsdo:ComplexTypeDefinition`:
- `xsdo:targetNamespace` (from the schema's own target namespace).
- `xsdo:extends` → the base type's own minted URI, if the type uses
  `xs:extension` (per Step 0's confirmed API).
- `xsdo:contentModel` → a `xsdo:Sequence` node with `xsdo:hasParticle`
  entries for the type's own particles only (not inherited ones),
  each with `xsdo:particlePosition` (1-based, real document order),
  `xsdo:minOccurs`, `xsdo:maxOccurs` (or `xsdo:maxOccursUnbounded` for
  real unbounded particles), and `xsdo:term` pointing at the
  referenced element/attribute declaration's own minted URI.
- If the content model is a `Choice`/`All` (not `Sequence`), raise a
  named `UnsupportedContentModelError` identifying the type and the
  actual model kind found — loud and explicit, matching
  `structural_cases.enumerate_cases`'s own discipline for the same
  scope cut. **This check applies recursively, not just to a type's own
  outermost model**: confirmed directly against the real MiKaDiv-FM
  package that while only 1 of 14 real global complex types
  (`AntwortListeType`) is Choice-shaped at its own top level, nested
  inline `xs:choice` groups appear as particles *within* otherwise-
  Sequence types too (e.g. inside `Personentypen.xsd`) — the walk must
  raise the moment it encounters a Choice/All group at any depth, not
  only when a type's own top-level model is one.

### Element and attribute declaration extraction

For each `xsdo:ElementDeclaration`/new `xsdo:AttributeDeclaration`
(a new class — real XSDs in this project's actual target schemas use
both element- and attribute-typed fields, e.g. KaFE's `AccountNumber`
is a real attribute):
- `xsdo:name` (the real local name).
- `xsdo:type` → the referenced type's own minted URI (complex or
  simple).

### Simple type extraction

For each `xsdo:SimpleTypeDefinition`, extract exactly the facet set
`equivalence/leaf_values.py` already knows how to consume — no more,
no less, since that's the concrete, real consumer this data needs to
serve: `xsdo:hasEnumerationValue`/`xsdo:literalValue`,
`xsdo:minLength`/`xsdo:maxLength`/`xsdo:length`, `xsdo:pattern`,
`xsdo:minInclusive`/`xsdo:maxInclusive`, `xsdo:totalDigits`/
`xsdo:fractionDigits`.

### Identity constraints

For each `xs:key`/`xs:unique`/`xs:keyref` on a complex type, extract
exactly the shape `equivalence/identity_constraints.py` already
consumes: `xsdo:hasIdentityConstraint` → a constraint node typed
`xsdo:Key`/`xsdo:Unique`/`xsdo:KeyRef`, with `xsdo:selector`, one or
more `xsdo:field` values, and (for `KeyRef`) `xsdo:refer`.

### URI minting

Every extracted type/element/attribute needs a stable, real URI, not
an opaque blank node — a future consumer (a later sub-project curating
real content) needs to be able to reference "the real `Vorname`
element in `Personentypen.xsd`" reliably. Mint URIs from the real
schema's own target namespace plus the real local name (e.g.
`<namespace>#Vorname` or similar — the exact scheme is an
implementation detail to settle during the plan, not a design-level
concern, as long as it's stable and collision-free within one extracted
graph).

## Testing strategy

Tested against the real, official MiKaDiv-FM package now committed at
`ontologies/mikadiv-fm/sources/xsd/` — not synthetic fixtures this
time, since the whole point is proving this works against real,
messy, official data, not a clean hand-crafted example. A deliberately
small, representative set of real types, each hand-verified against
the actual XSD file content (the same discipline the original
`kafe.ttl` curation used, per its own commit history, just automated):

- One plain type with no extension, no interesting facets (a real,
  simple baseline).
- One real type using `xs:extension` — assert `xsdo:extends` points at
  the correct real base type, and that the extracted content model
  contains only that type's own additional particles, not the base
  type's.
- One real type with a representative facet set (at minimum: an
  enumeration and a length constraint) — assert the extracted facets
  exactly match the real XSD's own declared values.
- One real type with a real identity constraint (`Meldeart13.xsd` has
  a real `xs:unique` on its `Verwahrkette` element, per this session's
  own investigation) — assert the extracted selector/field(s) match.
- One real attribute declaration (not just elements) — assert it's
  extracted as `xsdo:AttributeDeclaration`, not silently dropped or
  mis-typed as an element.
- One negative test using a **real** type from the actual MiKaDiv-FM
  package, not a synthetic one: `AntwortListeType` (`MiKaDiv_FM_1.02.xsd`),
  the one real global complex type confirmed to be Choice-shaped at its
  own top level — assert `UnsupportedContentModelError` is raised
  naming it. A second real case worth covering if time allows: a type
  in `Personentypen.xsd` whose Sequence contains a *nested* inline
  `xs:choice` particle, proving the recursive check above actually
  fires at depth, not just at a type's own outermost model.

## Definition of Done for this sub-project

- `extract(xsd_path)` implemented, tested against the six cases above,
  all passing.
- `UnsupportedContentModelError` raised (not silently mishandled) for
  `xs:choice`/`xs:all` content models.
- The `xsdo:extends` design is proven correct specifically for a real
  extension-using type from the actual target schema, not just a
  synthetic one.
- No claim of full-schema coverage — the Definition of Done is "the
  extraction mechanism is correct," not "MiKaDiv-FM is fully
  extracted."
