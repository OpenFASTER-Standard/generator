# Task ID: 15

**Title:** Re-citation editing UI

**Status:** done

**Dependencies:** 13 ✓

**Priority:** medium

**Description:** Once ShapeField resolves and displays the real cited value (task 13), let an admin pick a different source span to correct a citation -- the real meaning of "editing an annotation" in a system that stores citations, not literal values -- producing a structured pending-edit object, with no write mechanism of its own yet.

**Details:**

## What actually shipped (2026-10-01)

The real implementation lives entirely in the separate `OpenFASTER-Standard/ui` repo (`/work/ui`, package `packages/shapes`) -- `generator`'s own `scripts/validate-tasks` can only verify commit ancestry within this repository, so this task's `evidence.commits` points to the task-master rescoping commit made here (the only generator-repo commit substantively about this task), not the implementation itself. The real commits, in `ui`, in order:

- `ab93486` -- refactored `resolve.ts` into three composable, independently-exported, independently-tested pieces (`findCitation`, `fetchSourceDocument`, `evaluateXPathAgainstDocument`), verified behavior-preserving by running task 13's own full pre-existing test suite unchanged.
- `cc63f16` -- `computeXPathForElement`, the click-to-XPath algorithm (walks an element to the document root, preferring a unique `name` attribute, falling back to 1-indexed sibling position), verified live to round-trip through `document.evaluate()`.
- `957a841` -- `SourceDocumentTree`, a presentational, clickable element-tree browser for a fetched source document.
- `9ec6848` -- `ReCitationPicker`, composing the three pieces above: browse the current citation's real source document, click a span, see its live-resolved preview, and confirm to emit a structured pending-edit object (`{ propertyShapeIri, newXPath, previewValue }`) via a callback prop -- no write mechanism of its own, exactly as scoped (task 16).
- `95281a9` -- final-review fix pass: 1 Critical, 6 Important, 6 Minor, all fixed in the same pass per this project's standing rule. The Critical finding was real and genuinely dangerous: `computeXPathForElement` grouped siblings by a tagName/prefix string instead of namespace URI + local name, so two different prefixes legally bound to the same namespace could compute a unique-but-WRONG XPath -- confirmed live in real Chromium. The review also found that jsdom's own XPath engine is not namespace-aware at all (it matches by literal qualified-name string, and ignores the namespace resolver's return value entirely), meaning the task's existing jsdom-based test suite could not have caught either this bug or the related hardcoded-namespace-map bug in `evaluateXPathAgainstDocument` (Important) -- both fixes were verified live in real Chromium before being written, and their regression tests assert on computed values/strings directly rather than round-tripping through jsdom's own non-namespace-aware `evaluate()`. See that repo's own commit messages and `.changeset/fix-re-citation-picker-final-review.md` for the full list.

---

## Why this exists as its own task

Discovered during task 13's own investigation: `annotation_model` stores
only citations (source + selector), never a decoded literal value (see
task 13's own details for the live-verified evidence). "Editing" here
therefore means re-pointing a property shape's citation at a different
source span -- e.g. correcting `/xs:schema/.../xs:documentation` to a
different, actually-correct element -- not editing free text.

## Real building block

Task 3's own click-dummy exploration (predating the current stack, but
the underlying interaction idea survives): "sources on the left, output
on the right... click the source to see what it produced" -- the natural
UI for re-citation is showing the live source document alongside the
current citation and letting an admin click a different span.

## Scope

Pure UI-library work (`/work/ui`), zero git/GitHub dependency -- produces
a structured "pending edit" (property shape IRI + new selector) via a
callback prop, exactly mirroring how a controlled React form emits
`onChange`/`onSubmit` without owning persistence itself. What consumes
that pending edit is task 16 (the write client) and task 17 (the real
app), not this task.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
