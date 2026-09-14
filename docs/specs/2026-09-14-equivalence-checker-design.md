# Equivalence Checker — Design

Sub-project 2 of `/work/openfaster-restructuring/STATUS.md`. Full context
and decision log live there — this document covers only this
sub-project's own architecture and scope.

## Context

The target pipeline direction (STATUS.md decision log) is: a knowledge
graph is the authored source of truth → it generates the real `.xsd` a
module needs → the generated XSD must be behaviorally equivalent to the
officially published one. This document is the design for the tool that
proves that equivalence — the mechanism that gives every later
module-content sub-project (3, 4, 5) its actual Definition of Done.

Two research passes this session shaped this design away from its first
draft:

1. **The theoretical grounding is sound but the naive implementation path
   isn't.** XSD content models (given the Unique Particle Attribution
   rule) are regular tree languages, and regular tree language
   equivalence is decidable — real, citable automata theory (e.g. 2025
   work on deterministic tree automaton equivalence, arXiv 2504.04206).
   But no mature, actively-maintained library exists for the specific
   translation from XSD content models to a checkable automaton
   representation — the closest real tool (`xsdiff`) is dormant (last
   real commit 2019, one release, 22 stars). Hand-building that
   translation from scratch would mean writing and validating a novel
   algorithm with no library to lean on — real implementation risk for a
   one-editor project.
2. **A lower-risk, equally well-grounded alternative exists: bounded
   exhaustive testing.** The "small-scope hypothesis" (Daniel Jackson's
   Alloy work) is decades-old, empirically validated formal-methods
   practice: the overwhelming majority of real defects show up within a
   small, exhaustively-enumerable input space. Combined with standard
   boundary-value/equivalence-class partitioning for leaf datatypes (a
   mainstream, decades-old QA discipline) and validated through
   `xmlschema` — a library already used elsewhere in this pipeline, not
   new/unvalidated code — this reaches very high practical confidence
   for finite, bounded schemas like these (small enums, capped
   cardinalities, no unbounded recursion) while reusing a trusted
   validator instead of requiring new automaton-equivalence code.

Confirmed directly against all three modules' real XSDs before finalizing
this approach: none of MiKaDiv-VIB's, MiKaDiv-FM's, or KaFE's real
schemas use `xs:assert`/`xs:assertion` or `xs:any`/`xs:anyAttribute` — the
constructs that would put correctness checking out of this method's
reach. KaFE has 16 and MiKaDiv-FM has 4 real `xs:key`/`xs:unique`/
`xs:keyref` constructs (MiKaDiv-VIB has none); small enough to check
directly rather than needing their own generation strategy.

## Scope

**In scope:** the equivalence-checking algorithm itself — structural
bounded-exhaustive/pairwise test-case generation, leaf boundary-value
generation, document assembly, cross-schema validation via `xmlschema`,
type correspondence, identity-constraint comparison, and the
`xs:assert`/`xs:any` guardrail. Tested against small, hand-crafted
synthetic `xsdo:`-shaped fixtures (not real government XSDs).

**Out of scope (separate, not-yet-scoped work):** the real XSD →
`xsdo:` extraction logic that would read an actual government XSD file
(this design assumes that graph already exists, however it's produced —
`generator/extraction/`'s own design is a future sub-project); wiring
this checker into any of the three real modules end-to-end (that
naturally happens once sub-projects 3/4/5 populate real `structure/`
content); the graph → XSD generator itself (also assumed to already
produce a graph, not built here).

## Architecture

### Package layout, inside `generator/equivalence/`

```
equivalence/
  __init__.py
  preconditions.py       # the xs:assert/xs:any guardrail
  type_correspondence.py # matches complex types across two xsdo: graphs
  leaf_values.py          # boundary-value generation for simple type facets
  structural_cases.py    # bounded-exhaustive / pairwise structural enumeration
  document_builder.py    # (structural case, leaf values) -> real XML document
  identity_constraints.py # xs:key/xs:unique/xs:keyref direct comparison
  checker.py              # orchestrator: ties the above together, produces a report
```

### 1. Preconditions (the guardrail)

Before anything else runs, `preconditions.check(graph)` scans an
`xsdo:`-shaped graph for any construct this method can't cover —
assertions, wildcards — and raises a specific, named exception
(`UnsupportedConstructError`) if found, rather than silently proceeding
with a weaker guarantee. This must run against **both** the
official-XSD-derived graph and the generated graph, every time, not just
once at setup — a future schema revision could introduce one of these
constructs, and this is exactly the loud, explicit failure that should
produce.

### 2. Type correspondence

`type_correspondence.match(official_graph, generated_graph)` returns
pairs of complex types that represent the same real-world structure,
matched by the element names they realize (not by type name, since the
two graphs are allowed to organize/name types differently — that's the
whole point of the graph being an independently-authored source, not a
mirror of the official schema's own naming choices). Any official type
with no match, or vice versa, is reported as an explicit, named failure
— never silently skipped.

### 3. Leaf boundary-value generation

For each `xsdo:SimpleTypeDefinition`, `leaf_values.generate(simple_type)`
returns a small representative set of values per standard boundary-value
analysis, not exhaustive enumeration of the underlying domain:

- **Enumeration:** every literal value, plus one value NOT in the
  enumeration (to test correct rejection).
- **Length facets** (`length`/`minLength`/`maxLength`): the exact
  boundary length(s), one value one unit below the minimum (rejection
  case) and one above the maximum (rejection case).
- **Pattern:** one value matching the regex, one clearly not matching.
- **Numeric facets** (`minInclusive`/`maxInclusive`/`totalDigits`/
  `fractionDigits`): the boundary values themselves, plus one value just
  outside each bound.

This deliberately does not attempt to enumerate "all possible strings"
or "all possible decimals" — that's an intractable, unbounded space and
also not what boundary-value analysis calls for; the boundary points are
where real schema-divergence bugs actually live.

### 4. Structural case enumeration

For a given complex type's content model (sequence/choice/all +
`minOccurs`/`maxOccurs`), `structural_cases.enumerate(content_model)`
produces every combination of:

- each independently-optional particle: present / absent
- each `xs:choice` branch: which branch is taken
- each repeating particle's occurrence count: at `minOccurs`,
  `minOccurs + 1`, an effective maximum (`maxOccurs` itself, or a fixed
  ceiling — 5 — standing in for `maxOccurs="unbounded"`, never attempting
  literal unboundedness), and one past that effective maximum (rejection
  case)

**Combinatorial control, decided empirically per type, not assumed
either way up front:** if a type's independent-choice-point count keeps
the full cross-product under a configurable ceiling (default 2^10 =
1024 combinations), enumerate it fully. Above that ceiling, fall back
to pairwise coverage (every pair of choice-point values covered by at
least one generated case, not every combination) — evaluate an existing,
maintained pairwise-generation library (e.g. `allpairspy`) before
hand-rolling one; if none is suitable, a hand-rolled pairwise generator
is a much smaller, better-understood algorithm than tree-automaton
equivalence would have been. The real independent-choice-point count for
each of the three modules' actual complex types is presently unknown —
measuring it is the first concrete step of implementing this component,
not an assumption this design makes.

### 5. Document assembly and validation

`document_builder.build(structural_case, leaf_value_choices)` produces a
real, well-formed, namespace-qualified XML document (via `lxml`) for one
combination. `checker.py` then validates that document against **both**
the official XSD and the generated XSD via `xmlschema` (already a
pipeline dependency), and compares the two accept/reject verdicts.

**On any divergence, the report includes the literal generated XML
document plus which schema accepted/rejected it and that schema's own
validation error** — a concrete, human-debuggable counterexample, not an
abstract state-divergence report.

### 6. Identity constraints

`identity_constraints.compare(official_graph, generated_graph)` compares
each matched type's `xs:key`/`xs:unique`/`xs:keyref` selector/field
declarations directly (XSD restricts these to a narrow, non-Turing-complete
XPath subset, so direct structural comparison is exact here, not
heuristic). Given the small real counts (16 in KaFE, 4 in MiKaDiv-FM, 0
in MiKaDiv-VIB), this does not need its own generation strategy.

### Honest confidence characterization

This tool proves **"no counterexample found across an exhaustively
enumerated (or rigorously pairwise-covered) structural scope, combined
with exact leaf-facet boundary checking and exact identity-constraint
comparison."** That is a different, and in the strict formal sense
weaker, claim than a completeness proof over all possible XML documents.
For finite, bounded schemas with no `xs:assert`/`xs:any` (confirmed for
all three modules), it is a very strong practical guarantee — but the
tool's own report output must say exactly this, not claim "proven
identical," so nobody downstream mistakes empirical confidence for a
mathematical proof.

### Secondary layer: real-document regression corpus

Once real submitted documents exist (from any module's future ingestion
work), validating them against both schemas is a useful secondary check
— it can catch a bug in the synthetic generator itself (an interaction
it didn't think to construct), not establish the primary equivalence
claim. This stays explicitly secondary, matching the earlier session
discussion of document-sampling's real limits.

## Non-Goals (explicit)

- No real XSD → `xsdo:` extraction logic (assumes the input graphs
  already exist).
- No wiring into any of the three real modules end-to-end.
- No graph → XSD generation logic (assumes the generated graph already
  exists).
- Full literal enumeration of `maxOccurs="unbounded"` — capped at a
  fixed ceiling, not attempted exhaustively.
- A hand-rolled pairwise-generation algorithm, unless evaluating
  existing libraries during implementation finds none suitable.

## Testing strategy for this sub-project

Since no real extraction/generation code exists yet, this sub-project's
own tests use small, hand-crafted synthetic `xsdo:`-shaped Turtle
fixtures representing tiny fake schemas — including at least one
fixture pair that's deliberately non-equivalent (to prove the checker
actually reports the divergence, not just passes trivially), one with a
type present in only one graph (to prove type-correspondence failures
are caught), and one containing `xs:assert`-equivalent flags to prove
the guardrail actually fires. Real end-to-end validation against actual
government XSDs happens naturally once sub-projects 3, 4, or 5 populate
real `structure/` content — not part of this sub-project's own
Definition of Done.

## Definition of Done for this sub-project

- All 7 modules in `equivalence/` implemented and unit-tested against
  synthetic fixtures (equivalent pair passes; non-equivalent pair is
  correctly flagged with a concrete counterexample; unmatched-type case
  is correctly flagged; guardrail fires on `xs:assert`/`xs:any`
  presence).
- The combinatorial-ceiling fallback (full enumeration vs. pairwise) is
  implemented and has its own test proving both code paths trigger
  correctly at the configured threshold.
- The tool's own report output states its confidence characterization
  explicitly (not "proven identical").
