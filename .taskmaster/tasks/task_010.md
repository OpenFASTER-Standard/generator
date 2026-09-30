# Task ID: 10

**Title:** Prove ontology-to-XSD round-trip equivalence

**Status:** pending

**Dependencies:** 1 ✓

**Priority:** medium

**Description:** Generate an XSD back out of the annotation_model's own stored shapes for a real regulatory standard, and prove it is equivalent to the official government-issued XSD -- the original, stated definition of "done" for the ontology-as-single-point-of-truth architecture, never completed.

**Details:**

## Why this exists as its own task

Stated explicitly and precisely at the very start of this whole effort
(2026-09-14): "my idea was that the XSD is not the single point of truth,
but instead we basically... reconstruct the XSD in the way that we then
have the respective... ontology. That would be the single point of
truth, and then the XSD would just be generated based on that, and we
know that we're done when the generated XSD is basically identical to
the officially provided XSD." Restated again on 2026-09-18: "aren't we
simply rebuilding the XSD in a better, more complete form... it's like a
puzzle which is reassembled into a more high-quality XSD?" and "I want to
get to a point where decomposition and composition are two expressions
of the same logic, not two separately maintained logics."

An earlier attempt at an equivalence checker existed in a since-deleted
implementation (predating the current annotation_model/alignment stack)
and was never carried forward. Task 1 ("done") did not include this
proof in its own final scope -- this task closes that real, named gap
against the current, real architecture rather than reopening an
already-shipped, already-reviewed task.

## The actual test of "done" here

Not a plausibility check or an LLM's own judgment -- the project's own
standing rule, stated explicitly during the original XSD-vs-KoSIT
equivalence-checker work: "we need a way to really prove that it's
equivalent, not an LLM saying 'yeah looks plausible.'" Whatever this
task's own brainstorm lands on for a real, mechanical equivalence
definition (e.g. canonical XSD diffing, semantic equivalence under the
W3C XML Schema data model rather than textual identity) must be provably
correct, not asserted.

## Scope

Brainstorm from scratch against the current annotation_model's real
stored shapes for MiKaDiv-FM (task 1) as the first real target -- prove
composition (ontology -> generated XSD) round-trips against the real,
official BZSt-issued XSD it was originally decomposed from.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
