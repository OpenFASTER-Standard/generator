# Shape-Driven UI Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach optional display hints to an existing citation shape
(Python, `/work/generator`) and render a shape as real React UI built
from `@openfaster-standard/ui`'s own components, via a new
`@openfaster-standard/shapes` package (TypeScript, `/work/ui`).

**Architecture:** Four bottom-up tasks, split across two repositories.
Task 1 (`/work/generator`) is purely additive: a new `hints.py` module
attaches `sh:name`/`sh:order`/`dash:editor` to an existing property
shape without touching the citation data `annotate_xpath`/`annotate_svg`
already put there. Tasks 2-4 (`/work/ui`) build a new package: Task 2
parses Turtle into a small queryable index, Task 3 renders one property
shape as a labeled field with graceful fallback for any missing or
unrecognized hint, Task 4 composes fields into a form and a table.

**Tech Stack:** Python 3.11, `rdflib>=7.6` (already a dependency) for
Task 1. TypeScript, React 19, `n3` (Turtle parsing, real npm package,
`2.7.12` current — verified live before writing this plan, has no
bundled types so `@types/n3` is a devDependency), Vitest +
`@testing-library/react` (matching `@openfaster-standard/ui`'s own
existing test setup) for Tasks 2-4.

**Spec:** `docs/specs/2026-09-30-shape-driven-ui-generation-design.md`

## Global Constraints

- **Cross-repo execution.** Tasks 2-4 modify `/work/ui`, a completely
  separate git repository from this one. The plan's own
  `task-start`/`task-done` ledger tooling assumes one repo — for Tasks
  2-4, track BASE with `git -C /work/ui rev-parse HEAD` before starting
  the task, and commit with `git -C /work/ui add ...` / `git -C /work/ui
  commit ...` (or by actually `cd`-ing into `/work/ui` for those steps)
  rather than relying on the scripts' cwd assumptions. The ledger file
  itself still lives under this repo's `.superpowers/sdd/` per the
  normal convention; only the git operations for Tasks 2-4 target the
  other repo.
- **`annotate_display_hint` (Task 1) does NOT call the existing
  `clear_property_shape()`.** Confirmed by reading its real
  implementation: it removes *every* triple with the property shape IRI
  as subject and its entire `prov:wasDerivedFrom` → annotation → target
  → selector chain — calling it from a hints function would destroy
  `sh:path`/`prov:wasDerivedFrom`/`gen:contentHash`, the citation data
  hints are supposed to layer onto, not replace. Task 1 instead removes
  only the three hint-specific predicates (`SH.name`, `SH.order`,
  `DASH.editor`) before re-adding whichever are given.
- **`sh:name` and `sh:order` are real, already-available terms on
  `rdflib.namespace.SH`** (`SH.name`, `SH.order`) — confirmed live, no
  new namespace needed for either. `DASH` (`http://datashapes.org/dash#`)
  is not in `rdflib.namespace` and is added as a new constant in
  `annotation_model/namespaces.py`.
- **This plan's only widget kind is `dash:TextFieldEditor`**, per the
  spec's own Non-Goals (full DASH coverage is out of scope). Any other
  `dash:editor` value, or none at all, renders the same plain read-only
  fallback.
- **`n3` has no bundled TypeScript types** (confirmed live:
  `package.json`'s `"types"` field is absent) — `@types/n3` (real,
  `1.26.4` current) is a required devDependency of the new package, not
  optional.
- **`@openfaster-standard/shapes` never reimplements a widget.** Every
  rendered field uses an existing `@openfaster-standard/ui` export
  (`Label`, `Input`) — there is no `Select` in that package yet, and
  this plan's single widget kind doesn't need one.
- This plan does not touch `generator/webapp/frontend` (a later,
  separate migration) or `annotation_model/rdf.py`'s existing
  `annotate_xpath`/`annotate_svg` (hints are purely additive).

## Review Focus

- **A hint update must never destroy citation data.** Calling
  `annotate_display_hint` on a property shape `annotate_xpath` already
  created must leave `sh:path`/`prov:wasDerivedFrom`/`gen:contentHash`
  completely unchanged — the one failure mode the spec's own reasoning
  exists to prevent.
- **Calling `annotate_display_hint` twice must replace, not
  accumulate** — mirroring the same upsert principle `clear_property_shape`
  established for citations, applied narrowly to the three hint
  predicates only.
- **A property shape with zero hints must still render** — the spec's
  explicit fallback path, not an error state.
- **An unrecognized `dash:editor` value must degrade one field, not
  crash the whole form/table** — a real, current DASH editor class this
  package doesn't implement yet (e.g. `dash:DatePickerEditor`) is a
  realistic future input, not a hypothetical one.
- **`getPropertyShapes`'s ordering must be well-defined in both cases
  the spec allows** — every property shape carrying `sh:order` (sort by
  it) and none of them carrying it (fall back to store-returned order)
  — a partially-ordered set (some with, some without) is not a case
  either the spec or this plan needs to handle; Task 2's tests cover
  only the two defined cases.

---

### Task 1: `annotation_model/hints.py`

**Repo:** `/work/generator`

**Files:**
- Modify: `annotation_model/namespaces.py` (add `DASH`)
- Create: `annotation_model/hints.py`
- Test: `tests/annotation_model/test_hints.py`

**Interfaces:**
- Consumes: `annotation_model.rdf._iri_segment` (the exact same
  percent-encoding `_annotate` already uses to mint a property-shape
  IRI); `annotation_model.namespaces.GEN`.
- Produces:
  - `annotation_model.namespaces.DASH: Namespace`
  - `annotate_display_hint(graph: Graph, *, standard: str, shape_name: str, property_name: str, label: str | None = None, order: int | None = None, editor: URIRef | None = None) -> URIRef`

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/test_hints.py
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.hints import annotate_display_hint
from annotation_model.namespaces import DASH, GEN
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotated_graph() -> tuple[Graph, URIRef]:
    outcome = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", xpath=AORDNR_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )
    return graph, property_shape_iri


@requires_real_corpus
def test_hint_does_not_destroy_the_citation_it_is_layered_onto():
    graph, property_shape_iri = _annotated_graph()
    original_path = set(graph.objects(property_shape_iri, SH.path))
    original_hash = set(graph.objects(property_shape_iri, GEN.contentHash))
    original_annotation = set(graph.objects(property_shape_iri, PROV.wasDerivedFrom))

    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="AOrdNr",
    )

    assert set(graph.objects(property_shape_iri, SH.path)) == original_path
    assert set(graph.objects(property_shape_iri, GEN.contentHash)) == original_hash
    assert set(graph.objects(property_shape_iri, PROV.wasDerivedFrom)) == original_annotation
    assert (property_shape_iri, RDF.type, SH.PropertyShape) in graph


@requires_real_corpus
def test_hint_adds_only_the_predicates_given():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", order=3,
    )
    assert list(graph.objects(property_shape_iri, SH.order)) == [Literal(3)]
    assert list(graph.objects(property_shape_iri, SH.name)) == []
    assert list(graph.objects(property_shape_iri, DASH.editor)) == []


@requires_real_corpus
def test_calling_annotate_display_hint_twice_replaces_the_label():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="A",
    )
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="B",
    )
    assert list(graph.objects(property_shape_iri, SH.name)) == [Literal("B")]


@requires_real_corpus
def test_all_three_hints_together():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="AOrdNr", order=1, editor=DASH.TextFieldEditor,
    )
    assert list(graph.objects(property_shape_iri, SH.name)) == [Literal("AOrdNr")]
    assert list(graph.objects(property_shape_iri, SH.order)) == [Literal(1)]
    assert list(graph.objects(property_shape_iri, DASH.editor)) == [DASH.TextFieldEditor]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/test_hints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.hints'`

- [ ] **Step 3: Add `DASH` to `annotation_model/namespaces.py`**

```python
DASH = Namespace("http://datashapes.org/dash#")
```

- [ ] **Step 4: Implement `annotation_model/hints.py`**

```python
from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SH

from annotation_model.namespaces import DASH, GEN
from annotation_model.rdf import _iri_segment


def annotate_display_hint(
    graph: Graph,
    *,
    standard: str,
    shape_name: str,
    property_name: str,
    label: str | None = None,
    order: int | None = None,
    editor: URIRef | None = None,
) -> URIRef:
    property_shape_iri = GEN[
        f"{_iri_segment(standard)}/{_iri_segment(shape_name)}/{_iri_segment(property_name)}"
    ]

    graph.remove((property_shape_iri, SH.name, None))
    graph.remove((property_shape_iri, SH.order, None))
    graph.remove((property_shape_iri, DASH.editor, None))

    if label is not None:
        graph.add((property_shape_iri, SH.name, Literal(label)))
    if order is not None:
        graph.add((property_shape_iri, SH.order, Literal(order)))
    if editor is not None:
        graph.add((property_shape_iri, DASH.editor, editor))

    return property_shape_iri
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/annotation_model/test_hints.py -v`
Expected: `4 passed`

- [ ] **Step 6: Run the full test suite**

Run: `pytest`
Expected: all tests pass (this task only added new files plus one
constant to `namespaces.py` — no existing behavior changed).

- [ ] **Step 7: Commit**

```bash
git add annotation_model/namespaces.py annotation_model/hints.py tests/annotation_model/test_hints.py
git commit -m "feat(annotation_model): add display hints, layered onto an existing citation"
```

---

### Task 2: `@openfaster-standard/shapes` scaffold + `parseShapeGraph`

**Repo:** `/work/ui`

**Files:**
- Create: `packages/shapes/package.json`
- Create: `packages/shapes/tsup.config.ts`
- Create: `packages/shapes/vitest.config.ts`
- Create: `packages/shapes/vitest.setup.ts`
- Create: `packages/shapes/tsconfig.json`
- Create: `packages/shapes/tsconfig.build.json`
- Create: `packages/shapes/src/parse.ts`
- Create: `packages/shapes/src/parse.test.ts`

**Interfaces:**
- Produces:
  - `SH_NS`, `GEN_NS`, `DASH_NS`, `PROV_NS`, `OA_NS`: `string` constants
    (base IRIs, e.g. `SH_NS = "http://www.w3.org/ns/shacl#"`)
  - `class ShapeGraph` wrapping an `n3.Store`
  - `parseShapeGraph(turtle: string): ShapeGraph`
  - `ShapeGraphParseError` (a named `Error` subclass)
  - `getPropertyShapes(graph: ShapeGraph, nodeShapeIri: string): string[]`
  - `getPropertyShapeInfo(graph: ShapeGraph, propertyShapeIri: string): { name: string; hash: string | null }`

- [ ] **Step 1: Scaffold the package**

`packages/shapes/package.json` — mirror `packages/ui/package.json`
exactly for `type`, `license`, `sideEffects` (omit, this package has no
CSS), `files`, `main`/`module`/`types`/`exports` (pointing at this
package's own `dist/`), and the `build`/`dev`/`test`/`lint` scripts
(drop the Tailwind/font-copy steps from `build`, this package has no
CSS). Real fields:
```json
{
  "name": "@openfaster-standard/shapes",
  "version": "0.1.0",
  "dependencies": {
    "@openfaster-standard/ui": "workspace:*",
    "n3": "^2.7.0"
  },
  "peerDependencies": {
    "react": ">=19",
    "react-dom": ">=19"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@types/n3": "^1.26.4",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.1",
    "jsdom": "^30.1.1",
    "react": "^19.3.0",
    "react-dom": "^19.3.0",
    "tsup": "^8.5.1",
    "typescript": "^7.0.2",
    "vitest": "^5.0.2"
  }
}
```
(version numbers copied from `packages/ui/package.json`'s own real
current `devDependencies`, verified this session — keep them in sync
with whatever `packages/ui/package.json` states at implementation time
if it has moved since.)

`tsup.config.ts`, `vitest.config.ts`, `vitest.setup.ts`, `tsconfig.json`,
`tsconfig.build.json` — copy `packages/ui`'s real files verbatim, with
paths adjusted for this package (no Tailwind alias needed in
`vitest.config.ts`'s `resolve.alias`, since this package has no CSS).

- [ ] **Step 2: Run `pnpm install` at the workspace root**

Run: `cd /work/ui && pnpm install`
Expected: exits 0; `packages/shapes` appears as a workspace member
(`pnpm-workspace.yaml` already globs `packages/*`, no change needed
there).

- [ ] **Step 3: Write the failing tests**

```typescript
// packages/shapes/src/parse.test.ts
import { describe, expect, it } from "vitest"
import { getPropertyShapeInfo, getPropertyShapes, parseShapeGraph, ShapeGraphParseError } from "./parse"

const VALID_SHAPE = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .

<https://openfaster.org/ns/generator#S/Sh> a sh:NodeShape ;
  sh:property <https://openfaster.org/ns/generator#S/Sh/AOrdNr> .

<https://openfaster.org/ns/generator#S/Sh/AOrdNr> a sh:PropertyShape ;
  sh:path <https://openfaster.org/ns/generator#S/Sh/AOrdNr/path> ;
  gen:contentHash "sha256:abc123" ;
  sh:name "AOrdNr" ;
  sh:order 1 .
`

describe("parseShapeGraph", () => {
  it("parses a real shape's Turtle", () => {
    const graph = parseShapeGraph(VALID_SHAPE)
    expect(graph).toBeDefined()
  })

  it("raises ShapeGraphParseError on malformed Turtle", () => {
    expect(() => parseShapeGraph("this is not @@@ valid turtle")).toThrow(ShapeGraphParseError)
  })
})

describe("getPropertyShapes", () => {
  it("returns the node shape's property shapes", () => {
    const graph = parseShapeGraph(VALID_SHAPE)
    const shapes = getPropertyShapes(graph, "https://openfaster.org/ns/generator#S/Sh")
    expect(shapes).toEqual(["https://openfaster.org/ns/generator#S/Sh/AOrdNr"])
  })

  it("orders by sh:order when every property shape has one", () => {
    const twoProps = `
${VALID_SHAPE}
<https://openfaster.org/ns/generator#S/Sh> sh:property <https://openfaster.org/ns/generator#S/Sh/Other> .
<https://openfaster.org/ns/generator#S/Sh/Other> a sh:PropertyShape ;
  sh:path <https://openfaster.org/ns/generator#S/Sh/Other/path> ;
  gen:contentHash "sha256:def456" ;
  sh:name "Other" ;
  sh:order 0 .
`
    const graph = parseShapeGraph(twoProps)
    const shapes = getPropertyShapes(graph, "https://openfaster.org/ns/generator#S/Sh")
    expect(shapes).toEqual([
      "https://openfaster.org/ns/generator#S/Sh/Other",
      "https://openfaster.org/ns/generator#S/Sh/AOrdNr",
    ])
  })

  it("falls back to store order when no property shape has sh:order", () => {
    const noOrder = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
<https://openfaster.org/ns/generator#S/Sh2> a sh:NodeShape ;
  sh:property <https://openfaster.org/ns/generator#S/Sh2/A> ;
  sh:property <https://openfaster.org/ns/generator#S/Sh2/B> .
<https://openfaster.org/ns/generator#S/Sh2/A> a sh:PropertyShape ; gen:contentHash "sha256:a" .
<https://openfaster.org/ns/generator#S/Sh2/B> a sh:PropertyShape ; gen:contentHash "sha256:b" .
`
    // No sh:order anywhere -- the fallback case. Only the *set* of
    // results is guaranteed (store-returned order is not a specific
    // sequence this test can pin), unlike the sh:order case above.
    const graph = parseShapeGraph(noOrder)
    const shapes = getPropertyShapes(graph, "https://openfaster.org/ns/generator#S/Sh2")
    expect(new Set(shapes)).toEqual(
      new Set([
        "https://openfaster.org/ns/generator#S/Sh2/A",
        "https://openfaster.org/ns/generator#S/Sh2/B",
      ]),
    )
  })
})

describe("getPropertyShapeInfo", () => {
  it("reads the real name and hash", () => {
    const graph = parseShapeGraph(VALID_SHAPE)
    const info = getPropertyShapeInfo(graph, "https://openfaster.org/ns/generator#S/Sh/AOrdNr")
    expect(info).toEqual({ name: "AOrdNr", hash: "sha256:abc123" })
  })

  it("falls back to the IRI's local segment when sh:name is absent", () => {
    const noName = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
<https://openfaster.org/ns/generator#S/Sh/NoLabel> a sh:PropertyShape ;
  gen:contentHash "sha256:xyz" .
`
    const graph = parseShapeGraph(noName)
    const info = getPropertyShapeInfo(graph, "https://openfaster.org/ns/generator#S/Sh/NoLabel")
    expect(info).toEqual({ name: "NoLabel", hash: "sha256:xyz" })
  })

  it("returns a null hash when gen:contentHash is absent", () => {
    const noHash = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
<https://openfaster.org/ns/generator#S/Sh/NoHash> a sh:PropertyShape ;
  sh:name "NoHash" .
`
    const graph = parseShapeGraph(noHash)
    const info = getPropertyShapeInfo(graph, "https://openfaster.org/ns/generator#S/Sh/NoHash")
    expect(info).toEqual({ name: "NoHash", hash: null })
  })
})
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: FAIL with `Cannot find module './parse'` (or equivalent — the
file doesn't exist yet)

- [ ] **Step 5: Implement `packages/shapes/src/parse.ts`**

```typescript
import { DataFactory, Parser, Store } from "n3"

const { namedNode } = DataFactory

export const SH_NS = "http://www.w3.org/ns/shacl#"
export const GEN_NS = "https://openfaster.org/ns/generator#"
export const DASH_NS = "http://datashapes.org/dash#"
export const PROV_NS = "http://www.w3.org/ns/prov#"
export const OA_NS = "http://www.w3.org/ns/oa#"

const RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

export class ShapeGraphParseError extends Error {}

export class ShapeGraph {
  constructor(readonly store: Store) {}
}

export function parseShapeGraph(turtle: string): ShapeGraph {
  let quads
  try {
    quads = new Parser().parse(turtle)
  } catch (cause) {
    throw new ShapeGraphParseError(`failed to parse shape Turtle: ${(cause as Error).message}`)
  }
  const store = new Store()
  store.addQuads(quads)
  return new ShapeGraph(store)
}

export function getPropertyShapes(graph: ShapeGraph, nodeShapeIri: string): string[] {
  const quads = graph.store.getQuads(namedNode(nodeShapeIri), namedNode(SH_NS + "property"), null, null)
  const iris = quads.map((q) => q.object.value)

  const orders = iris.map((iri) => {
    const orderQuads = graph.store.getQuads(namedNode(iri), namedNode(SH_NS + "order"), null, null)
    return orderQuads.length > 0 ? Number(orderQuads[0].object.value) : null
  })

  if (orders.every((o) => o !== null)) {
    return iris
      .map((iri, i) => [iri, orders[i] as number] as const)
      .sort((a, b) => a[1] - b[1])
      .map(([iri]) => iri)
  }
  return iris
}

export function getPropertyShapeInfo(
  graph: ShapeGraph,
  propertyShapeIri: string,
): { name: string; hash: string | null } {
  const nameQuads = graph.store.getQuads(namedNode(propertyShapeIri), namedNode(SH_NS + "name"), null, null)
  const name = nameQuads.length > 0 ? nameQuads[0].object.value : propertyShapeIri.split("/").at(-1)!

  const hashQuads = graph.store.getQuads(namedNode(propertyShapeIri), namedNode(GEN_NS + "contentHash"), null, null)
  const hash = hashQuads.length > 0 ? hashQuads[0].object.value : null

  return { name, hash }
}
```

(`RDF_TYPE` is unused by this task's three functions but kept as an
exported-ready constant since Task 3 needs it for the `dash:editor`
lookup — implementer's call whether to export it now or add it in
Task 3; either is fine.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: `8 passed`

- [ ] **Step 7: Commit**

```bash
cd /work/ui
git add packages/shapes/
git commit -m "feat(shapes): scaffold @openfaster-standard/shapes, parse Turtle into a queryable graph"
```

(Remember: this commit is in the `/work/ui` repo, not `/work/generator`
— see this plan's Global Constraints.)

---

### Task 3: `ShapeField`

**Repo:** `/work/ui`

**Files:**
- Create: `packages/shapes/src/ShapeField.tsx`
- Create: `packages/shapes/src/ShapeField.test.tsx`

**Interfaces:**
- Consumes: Task 2's `ShapeGraph`, `getPropertyShapeInfo`, `DASH_NS`.
- Produces: `<ShapeField propertyShapeIri={string} graph={ShapeGraph} />`
  (a React component)

- [ ] **Step 1: Write the failing tests**

```typescript
// packages/shapes/src/ShapeField.test.tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { parseShapeGraph } from "./parse"
import { ShapeField } from "./ShapeField"

const TEXT_FIELD_SHAPE = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
@prefix dash: <http://datashapes.org/dash#> .
<https://openfaster.org/ns/generator#S/Sh/AOrdNr> a sh:PropertyShape ;
  gen:contentHash "sha256:abc123" ;
  sh:name "AOrdNr" ;
  dash:editor dash:TextFieldEditor .
`

const NO_HINTS_SHAPE = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
<https://openfaster.org/ns/generator#S/Sh/Bare> a sh:PropertyShape ;
  gen:contentHash "sha256:def456" .
`

const UNRECOGNIZED_EDITOR_SHAPE = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
@prefix dash: <http://datashapes.org/dash#> .
<https://openfaster.org/ns/generator#S/Sh/Dated> a sh:PropertyShape ;
  gen:contentHash "sha256:ghi789" ;
  sh:name "Dated" ;
  dash:editor dash:DatePickerEditor .
`

describe("ShapeField", () => {
  it("renders the real label and hash for a TextFieldEditor shape", () => {
    const graph = parseShapeGraph(TEXT_FIELD_SHAPE)
    render(<ShapeField propertyShapeIri="https://openfaster.org/ns/generator#S/Sh/AOrdNr" graph={graph} />)
    expect(screen.getByText("AOrdNr")).toBeInTheDocument()
    expect(screen.getByDisplayValue("sha256:abc123")).toBeInTheDocument()
  })

  it("falls back to the IRI's local segment when sh:name is absent", () => {
    const graph = parseShapeGraph(NO_HINTS_SHAPE)
    render(<ShapeField propertyShapeIri="https://openfaster.org/ns/generator#S/Sh/Bare" graph={graph} />)
    expect(screen.getByText("Bare")).toBeInTheDocument()
    expect(screen.getByDisplayValue("sha256:def456")).toBeInTheDocument()
  })

  it("degrades to the plain fallback for an unrecognized dash:editor, without throwing", () => {
    const graph = parseShapeGraph(UNRECOGNIZED_EDITOR_SHAPE)
    expect(() =>
      render(<ShapeField propertyShapeIri="https://openfaster.org/ns/generator#S/Sh/Dated" graph={graph} />),
    ).not.toThrow()
    expect(screen.getByText("Dated")).toBeInTheDocument()
    expect(screen.getByDisplayValue("sha256:ghi789")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: FAIL with `Cannot find module './ShapeField'`

- [ ] **Step 3: Implement `packages/shapes/src/ShapeField.tsx`**

```tsx
import { Input, Label } from "@openfaster-standard/ui"
import { DataFactory } from "n3"
import { DASH_NS, getPropertyShapeInfo, type ShapeGraph } from "./parse"

const { namedNode } = DataFactory
const RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

function getEditorHint(graph: ShapeGraph, propertyShapeIri: string): string | null {
  const quads = graph.store.getQuads(namedNode(propertyShapeIri), namedNode(DASH_NS + "editor"), null, null)
  return quads.length > 0 ? quads[0].object.value : null
}

export function ShapeField({ propertyShapeIri, graph }: { propertyShapeIri: string; graph: ShapeGraph }) {
  const { name, hash } = getPropertyShapeInfo(graph, propertyShapeIri)
  const editor = getEditorHint(graph, propertyShapeIri)

  // Every recognized editor and the "no hint at all" case render the
  // same plain read-only text today (this plan's only widget kind is
  // TextFieldEditor) -- an unrecognized editor value falls through to
  // the exact same branch, which is what makes it a graceful
  // degradation rather than a special case to get wrong.
  const displayValue = hash ?? "no value"

  return (
    <div>
      <Label>{name}</Label>
      <Input readOnly value={displayValue} />
    </div>
  )
}
```

(`RDF_TYPE` unused here — remove it if Task 2 didn't already export it
and this task doesn't end up needing it; kept only if the implementer
chose to centralize it in Task 2's `parse.ts` instead, in which case
import it from there rather than redeclaring it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
cd /work/ui
git add packages/shapes/src/ShapeField.tsx packages/shapes/src/ShapeField.test.tsx
git commit -m "feat(shapes): render one property shape as a labeled field, with graceful fallback"
```

---

### Task 4: `ShapeForm` and `ShapeTable`

**Repo:** `/work/ui`

**Files:**
- Create: `packages/shapes/src/ShapeForm.tsx`
- Create: `packages/shapes/src/ShapeTable.tsx`
- Create: `packages/shapes/src/ShapeForm.test.tsx`
- Create: `packages/shapes/src/ShapeTable.test.tsx`
- Modify: `packages/shapes/src/index.ts` (create if Task 2 didn't already
  — export `parseShapeGraph`, `ShapeGraph`, `ShapeGraphParseError`,
  `getPropertyShapes`, `getPropertyShapeInfo`, `ShapeField`,
  `ShapeForm`, `ShapeTable`)

**Interfaces:**
- Consumes: Task 2's `getPropertyShapes`, `getPropertyShapeInfo`; Task
  3's `ShapeField`.
- Produces:
  - `<ShapeForm nodeShapeIri={string} graph={ShapeGraph} />`
  - `<ShapeTable nodeShapeIris={string[]} graph={ShapeGraph} />`

- [ ] **Step 1: Write the failing tests**

```typescript
// packages/shapes/src/ShapeForm.test.tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { parseShapeGraph } from "./parse"
import { ShapeForm } from "./ShapeForm"

const TWO_PROPERTY_SHAPE = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
<https://openfaster.org/ns/generator#S/Sh> a sh:NodeShape ;
  sh:property <https://openfaster.org/ns/generator#S/Sh/First> ;
  sh:property <https://openfaster.org/ns/generator#S/Sh/Second> .
<https://openfaster.org/ns/generator#S/Sh/First> a sh:PropertyShape ;
  gen:contentHash "sha256:first" ; sh:name "First" ; sh:order 0 .
<https://openfaster.org/ns/generator#S/Sh/Second> a sh:PropertyShape ;
  gen:contentHash "sha256:second" ; sh:name "Second" ; sh:order 1 .
`

describe("ShapeForm", () => {
  it("renders one field per property shape, in sh:order order", () => {
    const graph = parseShapeGraph(TWO_PROPERTY_SHAPE)
    render(<ShapeForm nodeShapeIri="https://openfaster.org/ns/generator#S/Sh" graph={graph} />)
    const labels = screen.getAllByText(/First|Second/).map((el) => el.textContent)
    expect(labels).toEqual(["First", "Second"])
  })
})
```

```typescript
// packages/shapes/src/ShapeTable.test.tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { parseShapeGraph } from "./parse"
import { ShapeTable } from "./ShapeTable"

const TWO_SHAPES_SAME_PROPERTIES = `
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix gen: <https://openfaster.org/ns/generator#> .
<https://openfaster.org/ns/generator#S/ShapeA> a sh:NodeShape ;
  sh:property <https://openfaster.org/ns/generator#S/ShapeA/value> .
<https://openfaster.org/ns/generator#S/ShapeA/value> a sh:PropertyShape ;
  gen:contentHash "sha256:aaa" ; sh:name "value" .
<https://openfaster.org/ns/generator#S/ShapeB> a sh:NodeShape ;
  sh:property <https://openfaster.org/ns/generator#S/ShapeB/value> .
<https://openfaster.org/ns/generator#S/ShapeB/value> a sh:PropertyShape ;
  gen:contentHash "sha256:bbb" ; sh:name "value" .
`

describe("ShapeTable", () => {
  it("renders one header column and one row per node shape", () => {
    const graph = parseShapeGraph(TWO_SHAPES_SAME_PROPERTIES)
    render(
      <ShapeTable
        nodeShapeIris={["https://openfaster.org/ns/generator#S/ShapeA", "https://openfaster.org/ns/generator#S/ShapeB"]}
        graph={graph}
      />,
    )
    expect(screen.getByText("value")).toBeInTheDocument() // one header column
    expect(screen.getByText("sha256:aaa")).toBeInTheDocument()
    expect(screen.getByText("sha256:bbb")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: FAIL with `Cannot find module './ShapeForm'` and `./ShapeTable`

- [ ] **Step 3: Implement `packages/shapes/src/ShapeForm.tsx`**

```tsx
import { getPropertyShapes, type ShapeGraph } from "./parse"
import { ShapeField } from "./ShapeField"

export function ShapeForm({ nodeShapeIri, graph }: { nodeShapeIri: string; graph: ShapeGraph }) {
  const propertyShapes = getPropertyShapes(graph, nodeShapeIri)
  return (
    <div>
      {propertyShapes.map((iri) => (
        <ShapeField key={iri} propertyShapeIri={iri} graph={graph} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Implement `packages/shapes/src/ShapeTable.tsx`**

Uses `@openfaster-standard/ui`'s real `Table`/`TableHeader`/`TableBody`/
`TableRow`/`TableHead`/`TableCell`. One column per distinct property
name found via `getPropertyShapeInfo` across all given node shapes'
`getPropertyShapes` results (per this plan's Global Constraints, assumes
— does not need to handle the deferred case of — every given node shape
sharing the same property names); one row per `nodeShapeIri`, one cell
per column showing that row's matching property shape's `hash` (via
`getPropertyShapeInfo`, matched by `name`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes test`
Expected: `13 passed`

- [ ] **Step 6: Export the package's public surface in `packages/shapes/src/index.ts`**

```typescript
export { parseShapeGraph, ShapeGraph, ShapeGraphParseError, getPropertyShapes, getPropertyShapeInfo } from "./parse"
export { ShapeField } from "./ShapeField"
export { ShapeForm } from "./ShapeForm"
export { ShapeTable } from "./ShapeTable"
```

- [ ] **Step 7: Build the package to confirm it compiles cleanly**

Run: `cd /work/ui && pnpm --filter @openfaster-standard/shapes build`
Expected: exits 0, `packages/shapes/dist/` contains `index.js`,
`index.cjs`, `index.d.ts`.

- [ ] **Step 8: Commit**

```bash
cd /work/ui
git add packages/shapes/src/
git commit -m "feat(shapes): compose ShapeField into ShapeForm and ShapeTable"
```

---

## Task-Master Bookkeeping

After Task 4's commit, mark roadmap task 3 done with real evidence:

```bash
cd /work/generator
npx -y --package=task-master-ai task-master set-status --id=3 --status=done
```

Then hand-edit `.taskmaster/tasks/tasks.json`'s task 3 to add an
`evidence.commits` array. Since this plan spans two repositories, that
array's SHAs come from two different `git log`s — record both the
`/work/generator` commit (Task 1) and the three `/work/ui` commits
(Tasks 2-4); note in a comment (or in the evidence structure, if
`scripts/validate-tasks` allows extra fields) which repo each SHA
belongs to, since `scripts/validate-tasks`'s ancestor check
(`git merge-base --is-ancestor`) only runs against
`/work/generator`'s own history and will not be able to verify the
`/work/ui` SHAs — run `scripts/validate-tasks` and confirm it at least
doesn't error on the `/work/generator` SHA; a failure to verify the
`/work/ui` SHAs specifically is expected and not a blocker, given the
tool's own single-repo design.
