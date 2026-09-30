# Task ID: 8

**Title:** MiKaDiv-VIB ontology and annotation

**Status:** pending

**Dependencies:** 1 ✓, 2 ✓, 4 ✓

**Priority:** medium

**Description:** Annotate the real MiKaDiv-VIB XSDs (Clearstream's own upstream, non-government-facing interface for foreign custodians reporting into German reclaims) as their own separate ontology, using the same annotation_model/alignment machinery built for MiKaDiv-FM.

**Details:**

## Why this exists as its own task

Explicit, original scope (session start, 2026-09-14): "there should be one
ontology per whatever term you would use as the superior term for both
MiKaDiv VIB and KaFE... the MiKaDiv ontology, and the KaFE ontology."
MiKaDiv-FM was built in full; VIB was not, despite being named in the same
breath from the very first message of this whole effort.

## Real source material

Only the XSDs exist for VIB -- "we really only have the XSDs. no other
official docs exist for mikadiv-vib" -- unlike MiKaDiv-FM, which also has
the BZSt Annex PDF for English documentation. VIB has no independent legal
grounding of its own: "every field in it exists solely to satisfy
something FM actually requires" (Clearstream, the domestic paying agent,
uses VIB to collect from foreign custodians like SIX/Euroclear exactly
what it needs to file its own real FM submission).

## Real relationship to MiKaDiv-FM (task 1)

Per the project's own standing rule against premature cross-standard
unification, VIB gets its own separate ontology first -- not derived or
inferred from FM's shapes. Once VIB's own annotation exists, the
alignment layer (task 4's own machinery, `alignment/sssom.py`) is the
real mechanism for connecting VIB fields to the FM concepts they exist to
satisfy, exactly the pattern task 4 already proved for a different pair
of standards.

## Scope

Brainstorm from scratch against the real VIB XSDs (no existing-codebase
framing) using exactly the annotation_model (task 1) + transformation
(task 2) + alignment (task 4) machinery already built and proven --
this task is squarely a matter of applying already-validated tooling to
a second real regulatory standard, not inventing new mechanism.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
