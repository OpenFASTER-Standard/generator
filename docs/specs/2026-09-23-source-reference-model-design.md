# Source Reference Model — Design

## Context

This is a from-scratch design. Nothing in this document builds on, migrates
from, or assumes any existing code in this repository — a prior long research
arc converged on extending this repo's existing `provenance/`/`review/`
modules, and was explicitly discarded (see commit `706562e`) in favor of
starting over from only two things: the real source materials this project
ingests, and real, primary-sourced external prior art. This spec is the first
output of that restart.

The question this document answers: given a fact extracted or derived from a
real source document (today: the MiKaDiv-FM XSD schema files under
`ontologies/mikadiv-fm/sources/xsd/`, and the KHB/regulatory PDF documents
under `ontologies/mikadiv-fm/sources/khb/`), how does the system record
*exactly what it pointed at*, in a way that:

1. is precise enough to re-locate later,
2. lets a future consumer soundly detect "the thing I cited may have
   changed" without pretending to understand *why* it changed, and
3. costs nothing to extend to a source format nobody has thought of yet.

Point 2 is not incidental — it is the direct conclusion of a research pass
into how real, deployed systems (Germany's XÖV/KoSIT e-government standard,
the ECB's BIRD banking-data standard, XBRL Formula/EBA's DPM, Nix/Bazel's
content-addressed builds, and proof assistants' dependency tracking) handle
the same problem. All five hit the same wall: a system either buys soundness
("never silently miss a change") by giving up on meaning, or buys meaning
back at a real, documented cost (the IFRS Foundation's own 2024 internal
review contemplated abandoning XBRL Formula Linkbase because "no formula
linkbase [was] published for the annual IFRS Accounting Taxonomy 2023...
dropped due to time constraints"). Nobody gets both cheaply. This design
picks a side deliberately: it optimizes for sound, coarse staleness
*detection* — not for verifying that meaning is preserved — and leaves
meaning-judgment to a human reviewer, every time.

This document specs only the **reference model**: the shape that records
"this fact is backed by this exact span of this exact source, and here is
how to tell later whether that span changed." It does not spec what happens
when a change is detected, how corrections are reviewed, or how any of this
renders in a UI — those are separate, later sub-projects.

## Non-Goals

- **Not** solving semantic drift detection (renamed-but-same-thing vs.
  genuinely-different). Confirmed by this session's research to be an open
  problem in every real system examined, not something to invent here. See
  "Coarse flagging" below.
- **Not** a staleness-detection *policy* (when to re-check, what to do with a
  flagged reference, how it surfaces to a reviewer). This spec defines what a
  `resolve()` call against a reference can return; a later sub-project
  consumes those return values.
- **Not** a correction/revision workflow.
- **Not** review UI or rendering. A `Reference` intentionally carries no
  human-readable snippet or excerpt — just a machine-addressable locator and
  a content hash. Presenting a citation to a reviewer is a separate concern.
- **Not** multi-format support beyond the two source kinds this project
  actually has today (XSD, PDF) — but the architecture must make adding a
  third trivial, per the Context above. "Trivial" is validated in this spec
  by describing exactly what a new format implementor would have to write
  (see "Extensibility").

## Coarse flagging, not identity tracking

When a cited span changes between document versions — a field renamed, a
paragraph reworded — this design does not attempt to determine whether it's
"the same thing, renamed" versus "a genuinely different thing." It only
guarantees the change is never silently missed. This mirrors the one pattern
that turned out to be real and load-bearing across the systems researched
(Nix, Bazel, dbt's state comparison) rather than the one that turned out to
be aspirational or abandoned in practice almost everywhere it was tried
(XBRL Formula's own maintainer reconsidering it; BIRD's transformation rules
being un-parsed free text with only a manually curated release-to-release
delta report as its real answer).

## Core concept: `Reference`

A `Reference` is either a `Leaf` (points at one span of one document) or a
`Union` (a set of other `Reference`s, combined):

```
Reference = Leaf  { subject_document, selector, content_hash, captured_at }
          | Union { parts: [Reference, ...] }
```

This single recursive shape covers two needs that turned out to be the same
thing:

- **A fact backed by more than one source** (e.g. a value assembled from
  several source fields) — a `Union` whose parts point at different
  documents.
- **One citation occupying more than one region** — most concretely, a PDF
  citation spanning a page break, or a paragraph that wraps irregularly
  around a figure, needing more than one shape to describe — a `Union` whose
  parts are same-document, different-page selectors.

Both a fact's own "how many sources back this" question and a single
citation's "how many disjoint regions does this span" question are answered
by the same mechanism, recursively. `Union` nesting is unrestricted (a
`Union` may contain another `Union`) because the recursive definition
supports it for free; nothing in this design requires flattening it.

### `Leaf` fields

```
Leaf {
  reference_id:    sha256(subject_document.family + selector.canonical_form)
  subject_document: {
    family:        string   // stable across versions, e.g. "MiKaDiv_FM_Meldeart23"
    version:       string   // exact version cited, e.g. "1.02" or "v9"
    retrieval_uri: string   // where to fetch that exact version's bytes
  }
  selector:        Selector  // polymorphic, tagged by `type` — see below
  content_hash:    { algorithm: "sha256", digest: hex }
  captured_at:     timestamp
}
```

`reference_id` is deterministic (a hash of the reference's own canonical
content, not a random ID), so citing the same span twice never creates a
duplicate. `family`/`version` split follows the real naming convention these
source files already use — `MiKaDiv_FM_Meldeart23_1.02.xsd`,
`khb_mikadiv_fm_de_v9.pdf` — where the version is already a distinct,
parseable suffix.

`content_hash.algorithm` is a field, not a hardcoded assumption, purely so
the hash function could change later without changing the schema — that costs
nothing to include now and isn't a real decision to defer further.

### `Union` fields

```
Union { parts: [Reference, ...] }
```

A `Union`'s `content_hash` is the hash of its parts' hashes, in a fixed
(page-order, then reading-order) sequence, so recomputing it later is
deterministic given the same parts in the same order. Its `reference_id`
derives the same way, from the ordered list of its parts' `reference_id`s.

## Selector types

A `Selector` is any shape that declares its own kind via a `type` field —
following the real W3C Web Annotation Data Model's own `Selector` pattern,
which is explicitly designed as an open family (`XPathSelector`,
`FragmentSelector`, `CssSelector`, `DataPositionSelector`/
`TextPositionSelector`, `SvgSelector` are all real, already-standardized
members; the spec explicitly treats custom selector types as first-class,
not a workaround). Two selector types are needed for this project's two real
source formats today.

### `XPathSelector` — for XSD elements

```json
{
  "type": "XPathSelector",
  "value": "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']/xs:sequence/xs:element[@name='AOrdNr']"
}
```

Real target, from `MiKaDiv_FM_Meldeart23_1.02.xsd`:

```xml
<xs:complexType name="AmtlicheOrdnungsnummerMa23ListeType">
  <xs:sequence>
    <xs:element name="AOrdNr" type="std:UUIDType" minOccurs="1" maxOccurs="3000">
      <xs:annotation><xs:documentation>Amtliche Ordnungsnummer</xs:documentation></xs:annotation>
    </xs:element>
  </xs:sequence>
</xs:complexType>
```

`resolve()` parses the XSD as XML and evaluates the XPath. Exactly one match
is required — zero or multiple is a structural outcome (`NOT_FOUND` /
`AMBIGUOUS`, see below), never a silent pick of "the first one."

`canonicalize_and_hash()` applies Canonical XML 1.1 (a real W3C standard —
deterministic attribute ordering, normalized namespace declarations,
normalized whitespace) to the matched subtree's serialization, then SHA-256s
the result. This means a future version renaming `AOrdNr` makes the XPath
stop matching anything at all (`NOT_FOUND` — a structural break), while a
future version changing `maxOccurs` without renaming leaves the XPath
resolving but changes the hash (a content change) — these are kept
distinguishable on purpose, since a reviewer benefits from knowing which
happened.

### `SvgSelector` — for PDF regions

```json
{
  "type": "SvgSelector",
  "page": 12,
  "value": "<svg:polygon points='88,140 488,140 488,160 88,160' xmlns:svg='http://www.w3.org/2000/svg'/>"
}
```

Real target, from `khb_mikadiv_fm_de_v9.pdf`, page 12 (verified live via
`pdfplumber` against the actual file): *"2.2 Nachrichteninhalte /
MiKaDiv-FM-Nachrichten enthalten nur Meldungen der gleichen Meldeart..."*

This borrows the real Web Annotation `SvgSelector` shape (an embedded SVG
`<polygon>`/`<path>` describing an arbitrary, non-rectangular region), with
one deliberate, honest deviation: Web Annotation itself has no native concept
of "page N of a multi-page document" — real deployments model that via a
separate per-page resource (an IIIF Canvas). Introducing a full per-page
sub-resource layer here would be real overengineering for what this needs, so
`page` is added as a plain field on the selector instead. This is noted
explicitly as a simplification, not silently passed off as full spec
compliance.

A citation spanning a page break becomes a `Union` of two `Leaf`s, each with
an `SvgSelector` on its own page:

```
Union {
  parts: [
    Leaf { ..., selector: { type: "SvgSelector", page: 12, value: "<svg:polygon points='88,140 488,140 488,160 88,160'/>" } },
    Leaf { ..., selector: { type: "SvgSelector", page: 13, value: "<svg:polygon points='88,40 300,40 300,55 88,55'/>" } }
  ]
}
```

`resolve()` finds which extracted characters on the given page fall inside
the polygon — real, buildable today with `pdfplumber`'s per-character
bounding boxes and `shapely` for the point-in-polygon test.

`canonicalize_and_hash()` collapses whitespace runs in the extracted text and
SHA-256s the result. Deliberately not a pixel-region hash: font-rendering and
anti-aliasing differences between tool versions would otherwise cause false
positives on genuinely unchanged content.

## Resolution & error semantics

`resolve()` returns one of four structural outcomes, as data — not an
exception — because at check time (re-running a selector against a newer
document version) "this doesn't resolve anymore" is an expected, meaningful
result, not a bug:

- **`RESOLVED(hash)`** — the normal case.
- **`NOT_FOUND`** — the selector matches nothing (an `XPathSelector`
  predicate stops matching after a rename; an `SvgSelector` region has zero
  overlapping characters — e.g. the page no longer exists).
- **`AMBIGUOUS`** — matches more than one node where exactly one was
  expected (`XPathSelector` only).
- **`UNCITABLE`** — geometrically/structurally present but not
  machine-checkable content (a scanned PDF page with no text layer under the
  polygon).

At **citation time**, a `cite()` wrapper calls `resolve()` and raises unless
the result is a clean, single `RESOLVED` — a `Reference` should never be
creatable against something that doesn't unambiguously resolve. `UNCITABLE`
existing as a distinct outcome (rather than silently hashing an empty
string) matters specifically here: two different blank/scanned regions would
otherwise hash identically and look indistinguishable, and any such region
would look permanently "unchanged" forever.

At **check time**, the same `resolve()` returns whichever of the four
outcomes applies — this is the contract a later staleness-detection
sub-project consumes; this spec does not define what happens with that
result beyond making all four cases distinguishable.

For a `Union`, each part's outcome is surfaced independently rather than
collapsed into one pass/fail signal — a reviewer needs to know *which* part
of a multi-region citation broke, not just that something in it might have.

## Extensibility: adding a new source format

Everything format-specific lives behind exactly two functions per selector
`type`, registered in a lookup table keyed by that `type` string:

- `resolve(selector, document) -> ResolutionOutcome`
- `canonicalize_and_hash(raw_content) -> hash`

`Reference`'s schema never branches on format — it only ever calls
`registry[selector.type].resolve(...)`. Adding a new source format later
means: pick an existing Web Annotation selector type if one fits (e.g.
`CssSelector` for an HTML source, `DataPositionSelector` for a raw
byte-addressable format), or define a new `type` if none does; implement
those two functions; register them. Nothing about `Reference`, `Union`,
storage, or any future consumer (staleness detection, review UI) needs to
change or even be aware a new format was added.

## Testing strategy

Every test targets the real files already used above — `AOrdNr` in
`MiKaDiv_FM_Meldeart23_1.02.xsd`, the real extracted text from
`khb_mikadiv_fm_de_v9.pdf` page 12 — not synthetic fixtures, consistent with
how every claim in this document was verified.

- `resolve()` + `canonicalize_and_hash()` for each selector type against the
  real file, confirming the exact hash is reproducible.
- Mutate a temp copy of each real file (rename the XSD attribute; blank the
  PDF region) and confirm `NOT_FOUND` vs. a changed hash come back correctly
  and distinguishably.
- A `Union` combining one `XPathSelector` leaf and one `SvgSelector` leaf;
  break only one part and confirm the other's status is unaffected and both
  are reported individually.
- Idempotency: citing the exact same span twice yields the same
  `reference_id`.
- The three citation-time error paths — zero XPath matches, multiple XPath
  matches, an `UNCITABLE` region — each raising via `cite()`.

## Definition of Done

- `Reference` (`Leaf`/`Union`), `XPathSelector`, and `SvgSelector` are
  implemented with the fields and semantics above.
- A selector-type registry exists, keyed by `type`, with `resolve`/
  `canonicalize_and_hash` implementations for both selector types.
- All tests listed above pass against the real source files in
  `ontologies/mikadiv-fm/sources/`.
- Citing the real `AOrdNr` element and the real page-12 KHB paragraph both
  produce a working `Reference`; re-resolving each against an intentionally
  mutated copy of its source produces the expected, distinguishable outcome
  (`NOT_FOUND` or changed hash, never a silent false match).
