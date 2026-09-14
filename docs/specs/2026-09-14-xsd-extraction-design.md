# XSD Extraction Logic — Design

Sub-project 3a of `/work/openfaster-restructuring/STATUS.md` (split off
from the originally-scoped "sub-project 3: mikadiv-fm" — see that
file's roadmap and decision log for full context). This document covers
the extraction logic's own architecture and scope: turning a real,
official XSD family into `xsdo:`-shaped RDF facts. It does not curate
any MiKaDiv-FM concepts, and it does not teach the equivalence checker
(sub-project 2, already complete) to consume every construct this
extractor can produce — that split is deliberate (see "What's
genuinely separate work" below), but it is **not** a license to leave
extraction itself incomplete for what the real XSDs actually contain.

**Governing principle, stated explicitly after getting this wrong twice
during brainstorming:** if a construct is genuinely *present* in the
real, official target XSDs, extraction supports it — full stop, not "a
representative subset," not "defer for scope." The only constructs
that stay unsupported are ones **confirmed absent** from the real
files by direct inspection (documented below, each with its own
verification), never ones that are merely inconvenient or would have
matched a scope cut made for a different piece of software (the
equivalence checker) for a different reason (test-case enumeration
complexity, which doesn't apply to extraction at all).

## Context

The equivalence checker (`generator/equivalence/`) proves a
graph-generated XSD is behaviorally equivalent to an official one, but
was built and tested entirely against small, hand-crafted synthetic
`xsdo:` fixtures. This document is the missing half: given a real,
official XSD family, produce the `xsdo:`-shaped RDF graph describing
it — completely, for whatever that family actually contains.

A full, direct construct census against all 13 real MiKaDiv-FM files
(the official BZSt package — `xsd_mikadiv_fm.zip` v8, fetched and
committed to `ontologies/mikadiv-fm/sources/` this session) found:

| Construct | Count | Status |
|---|---|---|
| `xs:element` | 123 | in scope |
| `xs:attribute` | 149 | in scope — **more common than elements** |
| `xs:complexType` / `xs:simpleType` | 111 / 56 | in scope |
| `xs:sequence` | 60 | in scope |
| `xs:choice` | 10 (affecting 6/36 real types in `Personentypen.xsd` alone, including `PersonType` itself) | in scope |
| `xs:extension` / `xs:complexContent` | 53 / 53 | in scope — pervasive, not an edge case |
| `abstract="true"` | 13, all on `xs:complexType` | in scope — tightly coupled with the extension pattern (concrete types extend abstract base types) |
| facets: `enumeration`(29) `pattern`(21) `maxLength`(19) `length`(12) `minLength`(11) `maxInclusive`(8) `minInclusive`(7) `totalDigits`(4) `fractionDigits`(4) `whiteSpace`(1) `minExclusive`(1) | — | in scope, plus `maxExclusive` even though unobserved (see below) |
| `xs:union` | 1 (a date type unioning full-date/year-only/unknown-date variants — a real business rule) | in scope |
| identity constraints: `xs:unique`(7) `xs:field`(9) `xs:selector`(7) | — | in scope. `xs:key`/`xs:keyref` don't appear in FM specifically, but do in KaFE (16 real occurrences, confirmed earlier this session) — the extractor is generic across modules, so all three stay in scope |
| `default`/`fixed` (elements or attributes) | 8 | in scope |
| `xs:documentation` | 410 | in scope — real EN/DE dual-language field descriptions; a real, direct input to future concept curation, not just structural metadata |
| `xs:appinfo` | 2, both in `din-norm-91379-datatypes.xsd` only | **checked, not extracted, with reason**: holds XÖV (German public-sector XML standardization) governance display-name metadata (`nameLang`/`nameKurz`) for the shared datatype library, not semantic field documentation, and doesn't appear in any MiKaDiv-FM-specific file — different kind of metadata than `xs:documentation`, not a smaller version of the same thing |
| `xs:all` | 0 | **confirmed absent** — not implemented, but the walk raises a named error if ever encountered, not silent mishandling |
| `substitutionGroup` | 0 | **confirmed absent** — not implemented |
| `mixed="true"` | 0 | **confirmed absent** — not implemented |
| `xs:assert`/`xs:assertion`/`xs:any`/`xs:anyAttribute` | 0 | **confirmed absent** (checked earlier this session) |

`maxExclusive` wasn't observed in this specific census but is part of
the same small, closed, standard set of 12 XSD constraining facets as
`minExclusive` (which was observed) — supporting the whole closed set
is the complete, principled choice, not "support only what's been
spotted by grep so far," which is exactly the mistake this census
exists to stop repeating.

## What's genuinely separate work (not a scope cut on extraction)

Two things are deliberately not part of this sub-project, and neither
is "extraction is incomplete" — they're different software with a
different job:

1. **Teaching the equivalence checker to consume `xsdo:Choice`,
   `xsdo:extends`, `xsdo:AttributeUse`, etc.** The checker's own
   Sequence-only cut exists because *enumerating bounded-exhaustive/
   pairwise test cases across branches* is genuinely harder — that
   complexity is real, but it's a property of **testing**, not of
   **representing structure as facts**. Extraction recording "this is
   a Choice with these branches" is no harder than recording a
   Sequence's particles; the extractor doesn't enumerate or validate
   anything. Conflating these two was the actual mistake in this
   design's first draft — treating "the checker doesn't support X yet"
   as if it meant "extraction shouldn't produce X either."
2. **Curating real MiKaDiv-FM concepts** (semantic meaning, business
   rules) — a later, separate sub-project. Extraction produces
   structural facts (including now `xs:documentation` text as raw
   material), not curated concept definitions.

## Architecture

### Package layout, inside `generator/extraction/`

Given the now-confirmed real scope (recursive content models, two
parallel particle/attribute-use mechanisms, a 12-facet closed set plus
unions, identity constraints, documentation), a single file is no
longer the right call the way it might have been for a Sequence-only
extractor. Exact file boundaries are an implementation-plan decision,
but the natural seams are: top-level orchestration and global
type/element walking; recursive content-model + particle/attribute-use
extraction; simple-type facet and union extraction; identity-constraint
extraction — mirroring the equivalence checker's own precedent of one
file per real concern.

### Step 0: verify `xmlschema`'s real object-model API before writing extraction logic

Confirmed empirically, not assumed, before any extraction code depends
on the answer (matching this project's established norm — a prior test
elsewhere in this codebase shipped against a guessed, wrong library API
and had to be fixed after the fact):

1. What `XsdComplexType.content` returns for a type using
   `xs:extension` — the type's own additional particles only, or a
   pre-merged view including the base type's.
2. How `xmlschema` exposes a type's base type (`.base_type` or
   otherwise) and its `abstract` flag.
3. How `xmlschema` exposes an attribute's `use` (required/optional),
   `default`, and `fixed` — confirmed this is a distinct concept from
   an element particle's `minOccurs`/`maxOccurs` (XSD's own Schema
   Component Model calls this "Attribute Use", not a particle).
4. How `xmlschema` exposes `xs:union`'s member types.
5. How `xmlschema` exposes `xs:documentation` content and its
   `xml:lang` attribute (for the real EN/DE dual-language pattern
   already seen elsewhere in this project).

### Core extraction function

```
extract(xsd_path: str) -> rdflib.Graph
```

Given the real family's entry point (`xmlschema` resolves the rest via
its own real `xs:import` handling), returns one `rdflib.Graph`
containing `xsdo:`-shaped facts for every global complex type, simple
type, element declaration, and attribute declaration `xmlschema`
resolves.

### Complex type extraction

For each `xsdo:ComplexTypeDefinition`:
- `xsdo:targetNamespace`.
- `xsdo:extends` → the base type's own minted URI, if the type uses
  `xs:extension`. The extracted content model captures only the type's
  *own* additional particles — never a flattened duplicate of the base
  type's, per Step 0's confirmed API.
- `xsdo:abstract` (boolean) — real, present, tightly coupled with
  `xsdo:extends`: a document can never actually instantiate an
  abstract type directly, only a concrete type that (transitively)
  extends it. A future consumer needs this to know not to try.
- `xsdo:contentModel` → a `xsdo:Sequence` or `xsdo:Choice` node
  (`xsdo:All` is not implemented — confirmed absent from the real
  files; the walk raises a named error if one is ever encountered, not
  silent mishandling) with `xsdo:hasParticle` entries, each with
  `xsdo:particlePosition`, `xsdo:minOccurs`, `xsdo:maxOccurs` (or
  `xsdo:maxOccursUnbounded`), and `xsdo:term`. **This walk is
  recursive**: a particle's own term can itself be a nested `Sequence`
  or `Choice` group (confirmed real in `Personentypen.xsd`), not only
  an `ElementDeclaration` — the same extraction logic applies at every
  depth, not just a type's own outermost model.
- `xsdo:hasAttributeUse` → one entry per `xs:attribute` on this type,
  each with `xsdo:required` (boolean, from the real `use="required"`/
  `"optional"` — confirmed both values are real and common: 102
  required, 37 optional) and `xsdo:term` pointing at the referenced
  `xsdo:AttributeDeclaration`. Kept as its own linking construct
  (mirroring `xsdo:hasParticle` for elements) rather than folded into
  particles, matching XSD's own Schema Component Model distinction
  between an Attribute Declaration (the reusable definition) and an
  Attribute Use (how one specific type uses it — required here, maybe
  optional elsewhere for the same declaration).

### Element and attribute declaration extraction

For each `xsdo:ElementDeclaration`/`xsdo:AttributeDeclaration`:
- `xsdo:name`, `xsdo:type` (as before).
- `xsdo:defaultValue`/`xsdo:fixedValue`, if the real declaration has
  one (confirmed real, if uncommon: 8 occurrences total).
- `xsdo:documentation` — the real `xs:documentation` text, with a
  language tag (`@en`/`@de`) matching the real EN/DE dual-language
  pattern already used elsewhere in this project's XSDs. Real,
  valuable input to future concept curation, not optional polish.

### Simple type and facet extraction

For each `xsdo:SimpleTypeDefinition`, extract the full closed set of
12 standard XSD constraining facets: `xsdo:hasEnumerationValue`/
`xsdo:literalValue`, `xsdo:length`/`xsdo:minLength`/`xsdo:maxLength`,
`xsdo:pattern`, `xsdo:whiteSpace`, `xsdo:minInclusive`/
`xsdo:maxInclusive`/`xsdo:minExclusive`/`xsdo:maxExclusive`,
`xsdo:totalDigits`/`xsdo:fractionDigits` — the complete set, not just
the subset already observed by this session's own census, since it's
small, closed, and standard (no reason a future file wouldn't use
`maxExclusive` just because this one census didn't happen to hit it).

**`xs:union`**: a simple type can be defined as the union of several
member simple types (real, confirmed: a date type unioning full-date/
year-only/fully-unknown variants — an actual business rule expressed
in the type system, not incidental). Extract as `xsdo:hasUnionMember`
→ each member type's own minted URI, rather than facets directly on
the union type itself.

### Identity constraints

For each `xs:key`/`xs:unique`/`xs:keyref` on a complex type:
`xsdo:hasIdentityConstraint` → a node typed `xsdo:Key`/`xsdo:Unique`/
`xsdo:KeyRef`, with `xsdo:selector`, one or more `xsdo:field` values,
and (for `KeyRef`) `xsdo:refer`. FM itself only exercises `xs:unique`
(7 real occurrences) — `xs:key`/`xs:keyref` are confirmed real in
KaFE instead (16 occurrences, established earlier this session), and
this extractor is generic across modules, so all three stay fully
supported, not narrowed to only what FM itself happens to use.

### URI minting

Every extracted construct needs a stable, real URI — a future consumer
needs to reference "the real `Vorname` element in `Personentypen.xsd`"
reliably. Exact minting scheme (namespace + local name composition) is
an implementation-plan decision, as long as it's stable and
collision-free within one extracted graph.

## Testing strategy

Tested against the real, official MiKaDiv-FM package
(`ontologies/mikadiv-fm/sources/xsd/`), each case hand-verified against
the actual XSD file content:

- A plain Sequence type with no extension (a real baseline).
- A real type using `xs:extension` from an `abstract="true"` base —
  assert `xsdo:extends` points at the real base type, `xsdo:abstract`
  is correctly `false` on the concrete type and `true` on the base,
  and the extracted content model contains only the concrete type's
  own additional particles.
- `PersonType` (or another real type from the 6 confirmed
  Choice-affected types in `Personentypen.xsd`) — assert the Choice
  branches are extracted correctly, including if the Choice is nested
  inside an outer Sequence rather than being the type's own top-level
  model.
- A real type with a representative facet set spanning multiple facet
  kinds (at minimum enumeration + length) — assert exact match against
  the real XSD's declared values.
- The real date type using `xs:union` — assert `xsdo:hasUnionMember`
  correctly lists its three real member types.
- A real type with a real identity constraint (`Meldeart13.xsd`'s
  `xs:unique` on `Verwahrkette`) — assert selector/field(s) match.
- A real attribute with `use="required"` and one with
  `use="optional"` — assert both are extracted as
  `xsdo:AttributeDeclaration` with correct `xsdo:hasAttributeUse`/
  `xsdo:required` values, not silently dropped or conflated with
  elements.
- A real element or attribute with a `default`/`fixed` value — assert
  it's captured.
- A real `xs:documentation` block — assert both EN and DE text are
  extracted with correct language tags.
- A negative test: `xs:all`, confirmed absent from the real family —
  hand-construct a tiny synthetic XSD using it, assert a named error is
  raised rather than silent mishandling (this one stays synthetic since
  there's no real occurrence to test against).

## Definition of Done for this sub-project

- `extract(xsd_path)` implemented and tested against every case above,
  all passing, all verified against real file content (or, for the one
  genuinely-absent construct, a clearly-labeled synthetic negative
  test).
- No known real construct from the census table above is unsupported.
  Every "confirmed absent" entry is backed by an actual grep/inspection
  result recorded in this document, not an assumption.
- No claim of full-schema *content* coverage (extracting all ~123 real
  elements is real content-curation work for a later sub-project) —
  but full construct-*kind* coverage, meaning nothing in the real files
  causes an unexpected crash or silent wrong output when that later
  sub-project actually points this extractor at the whole family.
