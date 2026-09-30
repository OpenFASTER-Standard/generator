# Task ID: 3

**Title:** Shape-driven UI generation: render user interfaces as projections of SHACL shapes

**Status:** done

**Dependencies:** 1 ✓, 2 ✓

**Priority:** medium

**Description:** Add optional SHACL display hints (sh:name/sh:order/dash:editor) to already-cited property shapes, and render them as read-only UI (a table, a form, a single field) in a new @openfaster-standard/shapes package built entirely on @openfaster-standard/ui's real components -- the structural fix for the generator webapp's page shell bypassing the design system entirely, proven at the mechanism level, not yet wired into the webapp itself.

**Details:**

## Reconciliation note (2026-09-30)

This task's `description`/`details`/`testStrategy` originally came from
task-master's own AI auto-elaboration at task-creation time, before the
real design spec existed. That auto-elaboration described a much larger
and differently-shaped project than what the approved spec scoped and
what was actually built: a `shape-renderer` module living *inside*
`@openfaster-standard/ui` (`packages/ui/src/shape-renderer/`), a `jsonld`
dependency, a six-widget registry (`TextInput`/`NumberInput`/`DateInput`/
`Checkbox`/`Select`/`Textarea`), three renderers including `ShapeDetail`,
a runtime SHACL validator, Storybook+Chromatic stories, a full migration
of the generator webapp's `AddCitationView`/`ReviewView` onto shape
forms, a Playwright end-to-end suite including a "shape change propagates
to UI with zero code edits" scenario, and a `>90%` coverage gate.

None of that was built, and per this project's own review process
(`docs/plans/2026-09-30-shape-driven-ui-generation.md`'s final review,
finding M17), leaving it here as the recorded Definition of Done would
give a future reader a materially false picture of what exists. The
section below replaces it with what the approved spec
(`docs/specs/2026-09-30-shape-driven-ui-generation-design.md`) actually
scoped and what was actually shipped. See that spec for the full design
reasoning (in particular why hints are a separate module from
`annotate_xpath`/`annotate_svg`, and why shape *rendering* is a separate
package from `@openfaster-standard/ui` rather than a module inside it).

## What this task actually built

Two repositories, two additive changes, no changes to any existing
behavior:

### `annotation_model/hints.py` (this repo, Python)

`annotate_display_hint(graph, *, standard, shape_name, property_name,
label=None, order=None, editor=None) -> URIRef` -- looks up the
deterministic property-shape IRI `annotation_model.rdf` already mints,
and layers on `sh:name` (a `Literal`), `sh:order` (a `Literal` integer),
and/or `dash:editor` (a `URIRef`, e.g. `DASH.TextFieldEditor`), each
independently optional. Raises `PropertyShapeNotFoundError` if the named
property shape doesn't already exist -- this function only ever adds to
a citation task 1's `annotate_xpath`/`annotate_svg` already created, it
never creates one itself. `sh:order` is core SHACL (not a DASH
extension); `dash:editor` is a real DASH term -- both reused rather than
inventing `gen:`-namespaced equivalents.

### `@openfaster-standard/shapes` (new package, `/work/ui`, TypeScript)

A separate pnpm workspace package (not a module inside
`@openfaster-standard/ui`), specifically so consumers of the base
component kit don't have to carry an RDF parser they never use. Depends
on `@openfaster-standard/ui` (`workspace:*`) for its actual rendered
widgets and on `n3` (N3.js, the real RDF/JS-spec-compliant library used
by Comunica/the Solid ecosystem) for Turtle parsing -- not `jsonld`.

- `parseShapeGraph(turtle: string): ShapeGraph` -- parses Turtle into an
  N3.js `Store` wrapper.
- `getPropertyShapes(graph, nodeShapeIri): string[]` -- a node shape's
  property-shape IRIs, ordered by `sh:order` when every property shape
  in the node shape has one, else in graph order.
- `getPropertyShapeInfo(graph, propertyShapeIri): { name, hash }` --
  `sh:name` if present (percent-decoded IRI segment fallback otherwise),
  `gen:contentHash` if present (`null` otherwise).
- `<ShapeField propertyShapeIri graph />` -- one property shape as a
  labeled, read-only field, using `@openfaster-standard/ui`'s real
  `FormItem`/`FormLabel`/`FormControl` (correct `htmlFor`/`id`
  association) -- never a raw `<label>`/`<input>` pair.
- `<ShapeForm nodeShapeIri graph />` -- every property shape of one node
  shape, as a list of `<ShapeField>`s.
- `<ShapeTable nodeShapeIris graph />` -- one row per node shape, one
  column per distinct property name across all given node shapes, using
  `@openfaster-standard/ui`'s real `Table` primitives.
- Exported namespace constants (`SH_NS`, `GEN_NS`, `DASH_NS`, `PROV_NS`,
  `OA_NS`) and `subjectTermFor`/`pickDeterministic` helpers for a
  consumer that needs to query the underlying `ShapeGraph.store`
  directly.

Every fallback described in the spec's Error Handling section is real
and tested: no `sh:name` -> IRI segment (percent-decoded); no
`dash:editor` -> plain read-only text; an unrecognized `dash:editor` ->
same plain read-only text, never a crash; malformed Turtle ->
`ShapeGraphParseError`, never a bare N3.js internal exception; a
malformed graph with duplicate triples for a single-valued predicate
(`sh:name`/`sh:order`/`gen:contentHash`/`dash:editor`) -> resolved
deterministically (not by undocumented store-iteration order), per the
branch's final-review fix for finding M10.

## Non-Goals (unchanged from the approved spec, still true of what shipped)

- Full DASH vocabulary coverage (DASH defines ~30 editor classes) --
  only `TextFieldEditor` today; adding another editor kind is a small,
  additive dispatch change, not a redesign.
- Rendering arbitrary future business-object shapes (e.g. a later
  alignment-layer entity) -- proven against today's real citation shapes
  only.
- Data-entry (write-back) forms -- every rendered field is read-only;
  nothing here writes back to a `TargetStore`.
- The collaborative annotation platform's own UI (roadmap task 6).
- Migrating `generator/webapp/frontend`'s existing pages onto this
  mechanism -- proving the mechanism was this task's job; migrating the
  webapp is separate, later work, not started.
- A runtime SHACL validator, a widget registry beyond the one
  `TextFieldEditor`-vs-fallback dispatch, Storybook stories, and
  Playwright end-to-end coverage -- none of these were in the approved
  spec's scope; do not treat their absence as unfinished work from this
  task.

**Test Strategy:**

## Verification strategy (what was actually run, matching the approved spec's Testing Strategy)

- **`hints.py` (Python, `tests/annotation_model/test_hints.py`)**: attaches
  hints to a real property shape produced by task 1's real
  `annotate_xpath` (not a synthetic fixture), then confirms the hint
  triples are queryable via the exact IRI task 1 already mints. Covers:
  `sh:name`/`sh:order`/`dash:editor` each landing correctly; raising
  `PropertyShapeNotFoundError` instead of creating an orphan when the
  named property shape doesn't exist; a later call that omits one hint
  leaving an earlier call's other hints untouched (no accidental
  deletion of sibling data).
- **`@openfaster-standard/shapes` (TypeScript, `packages/shapes/src/*.test.ts(x)`,
  25 tests across parse/ShapeField/ShapeForm/ShapeTable/index)**: every
  test parses real Turtle fixtures (not a mocked graph) and asserts
  real rendered/returned values. Covers: `sh:order`-based sorting
  (including malformed non-numeric and empty-string order values
  degrading to graph order, not corrupting the sort); the no-hints
  fallback path; an unrecognized `dash:editor` degrading gracefully;
  blank-node (anonymous, `sh:property [ ... ]`) property shapes;
  percent-decoding (and malformed-percent-sequence fallback) of the IRI
  segment used as a label fallback; a `<ShapeTable>` with differing
  property sets across rows (union of columns, no silently dropped
  row); two same-named properties within one row (joined values, not
  one silently dropped); duplicate triples on a single-valued predicate
  resolving deterministically regardless of triple-write order;
  `<ShapeField>` using `@openfaster-standard/ui`'s real `FormItem`/
  `FormLabel`/`FormControl` (asserted via `getByLabelText`, which only
  passes with real `htmlFor`/`id` association -- proves the
  cross-package boundary the whole redesign exists to guarantee, rather
  than a reimplemented raw `<input>`).
- **Fresh-clone build/CI verification**: confirmed live, three times,
  against independent fresh clones of `/work/ui` -- `pnpm install
  --frozen-lockfile` followed by this package's build/test succeeds with
  no pre-existing local `dist/` artifact to hide a missing build step
  (this was the branch's Critical finding, C1, before the fix).
  `ci.yml`/`release.yml` both build/typecheck/test/publish this package
  after `@openfaster-standard/ui`, in that order, matching the real
  `workspace:*` dependency.

## Explicitly not run (out of scope, not a gap)

- No Storybook/Chromatic visual regression -- no stories exist for this
  package (Non-Goal).
- No Playwright end-to-end verification against the generator webapp --
  the webapp does not consume this package yet (Non-Goal: migration is
  separate, later work).
- No coverage-percentage gate -- this project does not use one anywhere
  else either; correctness here is judged by whether every described
  fallback/degradation path in the spec's Error Handling section has a
  real, passing test exercising it (it does, listed above), not by a
  coverage number.

## Definition of Done (replaces the original, met in full)

- `annotate_display_hint()` adds `sh:name`/`sh:order`/`dash:editor` to an
  existing property shape without disturbing its citation data
  (`sh:path`/`prov:wasDerivedFrom`/`gen:contentHash`), and refuses to
  create a hint on a property shape that doesn't exist.
- `parseShapeGraph`/`getPropertyShapes`/`getPropertyShapeInfo` correctly
  read real annotated Turtle, including every fallback/degradation case
  named in the spec's Error Handling section.
- `<ShapeField>`/`<ShapeForm>`/`<ShapeTable>` render exclusively through
  `@openfaster-standard/ui`'s real components.
- Full test suite green in both repos (`pytest` in `generator`; `pnpm -r
  test` in `ui`), confirmed after every final-review fix, not just once
  at task completion.
- The new package builds and tests cleanly from an independent fresh
  clone (not just the local machine's existing state) and is wired into
  both `ci.yml` and `release.yml`.
- Publishing metadata (`LICENSE`, `README.md`, a changeset) matches what
  `package.json` already declares, so a future release actually ships
  this package rather than silently excluding it.
