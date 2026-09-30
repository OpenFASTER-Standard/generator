# Shape-Driven UI Generation — Design

## Summary

Turns a SHACL shape produced by `annotation_model` (roadmap task 1) into
a real, rendered UI — a table of citations, a detail view of one
citation's provenance — by attaching optional display hints to a shape
and rendering it with a new package in the `@openfaster-standard/ui`
workspace. This is the direct, structural fix for the incident that
opened this whole vision brainstorm: the generator webapp looked
unstyled because its own page shell bypassed the shared UI package
entirely, with nothing enforcing that shapes are the single source of
truth for what gets rendered.

This spans two repositories:
- **`generator`** (this repo): a new, additive Python module,
  `annotation_model/hints.py`.
- **`ui`** (`/work/ui`, a separate pnpm workspace): a new package,
  `@openfaster-standard/shapes`.

## Context

Depends on roadmap tasks 1 and 2 (`annotation_model`, already merged).
Per this project's standing rule, nothing here treats existing code —
including this session's own already-shipped `annotation_model` — as
untouchable; a later need is free to extend it, which is exactly what
`hints.py` does.

**What a property shape looks like today, exactly** (from
`annotation_model/rdf.py`, verified against the real shipped code, not
assumed): a `sh:PropertyShape` carries `sh:path` (a placeholder IRI with
no real-world semantics), `prov:wasDerivedFrom` (pointing at a
`oa:Annotation`), and `gen:contentHash`. **It carries no `sh:name`, no
ordering, and no rendering hint of any kind.** This spec's first job is
closing that gap — not assuming it's already closed.

**Two things named as prior art at the start of this brainstorm turned
out to already be real, standard vocabulary, not invented needs**:
`sh:order` is **core SHACL** (not a DASH extension) — the standard term
for declaring a property shape's display order. `dash:editor` (pointing
at a real DASH editor class, e.g. `dash:TextFieldEditor`) is the real
DASH term for a widget hint. Reusing both rather than inventing
`gen:`-namespaced equivalents.

**Why hints are a separate module, not a change to `annotate_xpath`/
`annotate_svg`**: citing a source (task 1) and deciding how to display
it are different concerns with different rates of change — a citation
changes when the underlying regulation changes; a display hint changes
when someone wants a nicer label, independent of citation validity.
Because task 1's property shapes already have stable, deterministic IRIs
(`clear_property_shape`'s upsert mechanism proves this), a hint can be
attached to an *existing* shape IRI without touching the citation call
that created it.

**Why a new `@openfaster-standard/shapes` package, not code added
directly to `@openfaster-standard/ui`**: shape rendering needs a
Turtle/RDF parser (real, established choice: **N3.js**, the RDF/JS-spec-
compliant library used by Comunica and most of the Solid ecosystem,
confirmed live on the npm registry, current version `2.7.12`) — a
dependency every consumer of the base component kit would otherwise be
forced to carry even if they never touch a shape. Real component
ecosystems already separate this way (MUI's `@mui/material` core vs.
its heavier `@mui/x-data-grid`). `@openfaster-standard/shapes` depends
on `@openfaster-standard/ui` for its actual rendered widgets (`Input`,
`Select`, `Badge`, `Table`) and never reimplements them — this is the
whole point of the redesign: no more hand-rolled markup bypassing the
shared components.

## Core Concepts

### `annotation_model/hints.py` (Python, this repo)

`annotate_display_hint(graph, *, standard, shape_name, property_name,
label=None, order=None, editor=None) -> URIRef` — resolves the same
deterministic property-shape IRI `annotation_model.rdf`'s IRI-minting
scheme already produces, and adds:
- `sh:name` (a `Literal`, if `label` given)
- `sh:order` (a `Literal` integer, if `order` given)
- `dash:editor` (a `URIRef` naming a real DASH editor class, if `editor`
  given — e.g. `DASH.TextFieldEditor`)

All three are optional and independent — a shape with none of them still
renders (see fallback behavior below); this function only ever adds to
an *existing* property shape (looked up the same way
`check_xpath_drift`/`check_svg_drift` already look up a shape's
provenance chain) and never creates one — creating a shape is task 1's
`annotate_xpath`/`annotate_svg`'s job alone.

### `@openfaster-standard/shapes` (TypeScript, `ui` repo)

- `parseShapeGraph(turtle: string): ShapeGraph` — parses Turtle via
  N3.js into a small in-memory index keyed by `sh:NodeShape`/
  `sh:PropertyShape` IRI, so a component doesn't re-parse or re-scan the
  whole graph per render.
- `<ShapeTable shapes={nodeShapeIris} graph={shapeGraph} />` — one row
  per node shape, one column per distinct property shape name across
  those rows (the "Pages" list use case).
- `<ShapeForm shape={nodeShapeIri} graph={shapeGraph} />` — one field per
  property shape belonging to that node shape.
- `<ShapeField property={propertyShapeIri} graph={shapeGraph} />` — the
  actual per-field renderer: picks a widget from `dash:editor` if
  present (initially: `TextFieldEditor` → `@openfaster-standard/ui`'s
  `Input`, read-only), and falls back to a plain read-only text display
  (the property's `gen:contentHash`, or its value if present) when no
  editor hint exists. Field order: `sh:order` if present on every
  property shape in the node shape, else the order they appear in the
  graph.

## Data Flow

1. A Turtle file (from task 1's `TargetStore`) is parsed into a
   `ShapeGraph` via `parseShapeGraph`.
2. A `<ShapeTable>`/`<ShapeForm>` is given that graph plus the node
   shape IRI(s) to render.
3. For each property shape, `<ShapeField>` reads `sh:name`/`sh:order`/
   `dash:editor` if present, and renders through
   `@openfaster-standard/ui`'s real components — never a raw `<div>`/
   `<input>`.

## Error Handling

- A property shape with no `sh:name` displays its property-shape IRI's
  local segment (matching the pattern already used in this session's
  own transformation-layer tests, `row.property.split('/')[-1]`) rather
  than failing or rendering blank.
- A property shape with no `dash:editor` renders as plain read-only
  text, never as an empty or broken field.
- An unrecognized `dash:editor` value (a real DASH editor class this
  package hasn't implemented yet) falls back to the same plain
  read-only text — an unimplemented widget must never crash the whole
  table/form, only degrade that one field.
- Malformed Turtle passed to `parseShapeGraph` raises a clear, named
  error identifying it as a parse failure — never a bare N3.js internal
  exception.

## Testing Strategy

- **Real shapes, not synthetic ones**: `hints.py`'s tests attach hints to
  a shape produced by task 1's real `annotate_xpath` against the real
  MiKaDiv-FM corpus (matching this project's established discipline),
  then confirm the hint triples are queryable via the exact IRI task 1
  already mints.
- **Rendering, real data**: a `<ShapeTable>`/`<ShapeForm>` test parses a
  real Turtle fixture (exported from a real annotated graph) and asserts
  the rendered output contains the real expected values — not a mocked
  graph.
- **Graceful degradation**: a shape with zero hints still renders
  (fallback path); a shape with an unrecognized `dash:editor` value
  still renders every *other* field correctly.
- **Cross-package boundary**: `@openfaster-standard/shapes`'s rendered
  output is asserted to use `@openfaster-standard/ui`'s real exported
  components (not reimplemented markup) — this is the property the
  entire redesign exists to guarantee.

## Non-Goals

- Full DASH vocabulary coverage (DASH defines on the order of 30 editor
  classes) — only the widget kinds today's real shapes actually need,
  starting with `TextFieldEditor`. Adding another is a small, additive
  change to `<ShapeField>`'s dispatch, not a redesign.
- Rendering arbitrary future business-object shapes (e.g. a "beneficial
  owner" entity from the later alignment layer, roadmap task 4) — this
  spec proves the mechanism against today's real citation shapes only.
- Data-entry (write-back) forms — today's shapes are read-only citation
  records; nothing in this spec produces a form that writes back to a
  `TargetStore`.
- The Wikipedia-like collaborative annotation platform's own UI
  (roadmap task 6) — a separate, later concern.
- Migrating `generator/webapp/frontend`'s existing pages onto this new
  rendering mechanism — proving the mechanism is this spec's job; a
  follow-up migration is separate, later work.

## Open Questions

- Whether `annotate_display_hint` needs its own `TargetStore` write path
  (mirroring task 1's `write_shape`) or is meant to be called against an
  in-memory graph before a single combined write — an implementation-
  planning detail, not resolved here.
- Exact `<ShapeTable>` column-naming/grouping behavior when two node
  shapes in the same table have genuinely different property sets — not
  a concern for today's single-shape-type rendering need, deferred until
  a real second shape type exists.
