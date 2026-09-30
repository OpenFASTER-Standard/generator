# Task ID: 13

**Title:** Resolve and display the real cited value in ShapeField

**Status:** pending

**Dependencies:** 1 ✓, 3 ✓

**Priority:** medium

**Description:** Fix ShapeField/ShapeTable (task 3) to resolve and display the actual cited content (e.g. the real German field description) by re-evaluating the citation's selector against its live source, instead of showing a raw gen:contentHash -- the read-only display gap task 3's own spec explicitly deferred, and the real prerequisite for any editing UI.

**Details:**

## Why this exists as its own task, and why it's narrower than originally scoped

Investigating this task's original framing ("write client and annotation-editing UI")
surfaced two things that change its real scope:

1. **`ShapeField`/`ShapeTable` (task 3, `/work/ui`) are read-only today by
   explicit, documented design** -- that spec's own Non-Goals: "Data-entry
   (write-back) forms -- today's shapes are read-only citation records...
   The Wikipedia-like collaborative annotation platform's own UI (roadmap
   task 6) -- a separate, later concern." This is a deliberate, correctly
   sequenced deferral, not a bug -- and this task is exactly the one meant
   to close it.
2. **But even *reading* is currently broken for a real end user**:
   `ShapeField` shows `gen:contentHash` (a hex digest used only for drift
   detection, per `annotation_model/drift.py`) as if it were the field's
   real value -- verified live in `packages/shapes/src/ShapeField.tsx`
   and its own test file, which asserts `toHaveValue("sha256:abc123")`.
   A non-technical bank employee -- the project's own explicitly named
   real end user -- would see a hex hash, not "Meldung nach § 45c Absatz
   2 Satz 3 EStG." This is the actual, more urgent, more foundational gap:
   editing a value nobody can even read yet is premature.

Also discovered live: **`annotation_model` never stores a decoded literal
value at all** -- only a citation (source URI + XPath/SVG selector +
content hash), per `annotation_model/rdf.py`'s `_annotate()`. The real
value only ever exists by re-resolving the selector against the live
source document. This means "editing an annotation" in this architecture
does not mean filling in a text box -- it means re-citing a different
source span. That's real, larger, separate work (see task 15).

## Real, live-verified feasibility for this task's actual scope

Browser-native `document.evaluate()` (DOM Level 3 XPath, no library
needed) was verified live against a real corpus XSD
(`MiKaDiv_FM_Meldeart23_1.02.xsd`) with the exact namespace mapping
Python's `lxml`-based `resolve_xpath` uses, and produced a byte-identical
result including a non-ASCII character (§): `"Meldung nach § 45c Absatz 2
Satz 3 EStG."` -- confirmed equivalent to Python's own resolver, not
assumed.

## Scope

XPath-sourced citations only (the MiKaDiv-FM/XSD case, today's only real
data) -- resolve client-side via `fetch()` + `DOMParser` +
`document.evaluate()`, matching Python's `_NSMAP` (`xs` ->
`http://www.w3.org/2001/XMLSchema`). SVG/PDF-sourced citation resolution
(needs a PDF-rendering capability client-side) is real future work, not
this task -- see Non-Goals.

## Non-Goals

- SVG/PDF-sourced citation value resolution (a materially different,
  harder client-side problem -- needs PDF rendering, not just XML
  parsing).
- Any editing/re-citation capability (task 15).
- Any write client / GitHub commit (task 16).
- Any real consuming application (task 17) -- this task's own
  deliverable is testable entirely within `/work/ui`'s existing
  Storybook/Vitest setup, against a mocked `fetch`.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
