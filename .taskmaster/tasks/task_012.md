# Task ID: 12

**Title:** Interconnected, lineage-visible provenance UI

**Status:** pending

**Dependencies:** 1 ✓, 3 ✓, 4 ✓

**Priority:** medium

**Description:** Rebuild -- against the current annotation_model/alignment/shape-driven-UI stack, not the deleted React/local-first implementation -- the multi-view, hover-linked navigation between a source document and everything derived from it, with a completeness guarantee against the underlying RDF store.

**Details:**

## Why this exists as its own task, and why it isn't a resurrection

A full implementation of this idea (React app, local-first sync engine,
triples-treemap, transclusion-based multi-view navigation) was built
earlier in this same overall effort and deleted wholesale during the
2026-09-23 full-project reset -- not because the *requirement* was wrong,
but because the architecture it was built against (a hand-rolled
Oxigraph/PROV-O graph store, predating annotation_model/alignment/
`@openfaster-standard/ui`) was itself superseded. The requirement was
never withdrawn and was restated forcefully throughout: "EVERYTHING
should have a lineage... I really want all this to *feel* amazingly
interconnected, interlinked"; "there should be many different views to
see the same data... see what has been derived from them directly simply
by hovering... the other way around... go back to the sources with a
click"; "how can I be sure that this actually covers all stored triples?"

## Real prior art already named for this

Web Annotation (already the real foundation of `annotation_model` itself,
task 1), PROV-O, and the explicit concept of transclusion (Xanadu/
TiddlyWiki/Roam) -- "I also learned the word 'transclusion' today which I
like a lot."

## Scope

A from-scratch brainstorm against the CURRENT stack only: `annotation_model`'s
real stored RDF (task 1), `alignment`'s real SSSOM mappings (task 4), and
`@openfaster-standard/ui`'s real component library (task 3) as the
rendering substrate -- not a port of the deleted React implementation.
Must include a real, provable completeness check against the underlying
triple store (the original ask: "how can I be sure that this actually
covers all stored triples?"), not merely a plausible-looking UI.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
