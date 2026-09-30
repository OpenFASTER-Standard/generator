# Task ID: 15

**Title:** Re-citation editing UI

**Status:** pending

**Dependencies:** 13

**Priority:** medium

**Description:** Once ShapeField resolves and displays the real cited value (task 13), let an admin pick a different source span to correct a citation -- the real meaning of "editing an annotation" in a system that stores citations, not literal values -- producing a structured pending-edit object, with no write mechanism of its own yet.

**Details:**

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
