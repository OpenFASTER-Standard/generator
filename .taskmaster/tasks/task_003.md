# Task ID: 3

**Title:** Shape-driven UI generation: render user interfaces as projections of SHACL shapes

**Status:** pending

**Dependencies:** 1, 2

**Priority:** medium

**Description:** Transform @openfaster-standard/ui from a generic hand-assembled component kit into a shape-rendering engine that auto-generates forms, tables, and review screens directly from SHACL shapes with DASH UI hints, establishing shapes as the single source of truth for UI structure.

**Details:**

## Overview

This task fundamentally redefines what `@openfaster-standard/ui` is: not a generic Tailwind component library manually assembled per app, but a **shape-rendering engine** that generates user interfaces (forms, tables, review screens) as projections of the same SHACL shapes from Task 1, based on proven prior art from the Solid/Linked-Data ecosystem.

**Ground Truth Prior Art** (not invented here):
- **SHACL + DASH (Data Shapes vocabulary)**: W3C-recommended extension to SHACL that adds UI-specific hints (`dash:editor`, `dash:viewer`, `sh:order`, `sh:group`) to drive rendering, not just validation.
- **shacl-form web component pattern**: Already used in Solid/Linked-Data ecosystem (e.g. Inrupt's form generators, Comunica UI) for auto-rendering HTML forms directly from a SHACL shape - widget choice, field order, grouping all declared in the shape, not hardcoded in React components.
- **Existing generator webapp as counter-example**: Current `/work/generator/webapp/frontend/src/views/*.tsx` manually builds every form/table/field with hardcoded component imports - the page shell and empty states bypass the design system entirely because there is no enforced single source of truth driving the UI.

## Why This Solves the Real Problem

The generator webapp currently looks unstyled/unprofessional (confirmed in `/work/generator/docs/specs/2026-09-29-webapp-react-rebuild-design.md`) **not because Tailwind components are missing, but because there's no architectural forcing function making UI structure follow a declarative model**. Layout, field order, widget choice, validation - all scattered across React components with no guarantee of consistency.

Shape-driven rendering makes the shape the **single source of truth**:
- **Add a field to the shape → UI gets it automatically**, right widget, right position, right validation.
- **Change field order in the shape → UI re-orders itself**, no manual JSX refactoring.
- **UI can't drift from model** - there is no separate place to hardcode different structure.

## Architecture

### Core Shape-Rendering Engine (`packages/ui/src/shape-renderer/`)

New module structure in `@openfaster-standard/ui`:

```
packages/ui/src/
  shape-renderer/
    core/
      parser.ts          # Parses SHACL+DASH shapes from RDF/JSON-LD
      schema.ts          # Internal schema representation (widget, constraints, order)
    widgets/
      TextInput.tsx      # dash:TextFieldEditor → Input component
      NumberInput.tsx    # dash:NumberEditor → Input[type=number]
      DateInput.tsx      # dash:DatePickerEditor → Input[type=date]
      Checkbox.tsx       # dash:BooleanSelectEditor → Checkbox
      Select.tsx         # sh:in enumeration → Select dropdown
      Textarea.tsx       # dash:TextAreaEditor → Textarea
      index.ts           # Widget registry mapping DASH editor URIs → components
    renderers/
      FormRenderer.tsx   # Renders sh:NodeShape as a form (respects sh:order, sh:group)
      TableRenderer.tsx  # Renders sh:NodeShape as a table (columns from sh:property)
      DetailRenderer.tsx # Renders sh:NodeShape as a detail view (read-only variant)
    validation/
      validator.ts       # Runtime validation against sh:minCount, sh:datatype, sh:pattern, etc.
    index.ts             # Public API: <ShapeForm>, <ShapeTable>, <ShapeDetail>
  components/ui/         # Existing base components (Button, Input, etc.) - unchanged
  index.ts               # Re-exports both shape renderers and base components
```

### Shape Schema Format (Internal Representation)

Parser output, derived from SHACL+DASH:

```typescript
interface PropertySchema {
  path: string;                    // sh:path
  name: string;                    // sh:name or rdfs:label
  description?: string;            // sh:description
  datatype: string;                // sh:datatype (xsd:string, xsd:integer, etc.)
  minCount?: number;               // sh:minCount
  maxCount?: number;               // sh:maxCount
  pattern?: string;                // sh:pattern
  in?: string[];                   // sh:in (enumeration)
  editor: string;                  // dash:editor URI
  viewer?: string;                 // dash:viewer URI (for read-only mode)
  order: number;                   // sh:order (default 0)
  group?: string;                  // sh:group URI
}

interface NodeShapeSchema {
  targetClass: string;             // sh:targetClass
  label: string;                   // rdfs:label
  description?: string;            // sh:description
  properties: PropertySchema[];    // sh:property, sorted by sh:order
  groups?: GroupSchema[];          // sh:group definitions
}

interface GroupSchema {
  uri: string;
  label: string;
  order: number;
}
```

### Public Components API

```typescript
import { ShapeForm, ShapeTable, ShapeDetail } from '@openfaster-standard/ui';

// Form rendering
<ShapeForm
  shape={citationNodeShape}           // NodeShapeSchema
  initialData={existingCitation}      // Optional pre-fill
  onSubmit={(data) => submitCitation(data)}
  onValidationError={(errors) => console.error(errors)}
/>

// Table rendering (list view)
<ShapeTable
  shape={citationNodeShape}
  data={citations}                    // Array of objects matching shape
  onRowClick={(row) => navigate(`/pages/${row.fact_key}`)}
/>

// Detail/review rendering (read-only)
<ShapeDetail
  shape={citationNodeShape}
  data={citation}
/>
```

### Widget Selection Logic

Maps DASH editor URIs to React components:

```typescript
const WIDGET_REGISTRY: Record<string, React.ComponentType<WidgetProps>> = {
  'http://datashapes.org/dash#TextFieldEditor': TextInput,
  'http://datashapes.org/dash#TextAreaEditor': Textarea,
  'http://datashapes.org/dash#NumberEditor': NumberInput,
  'http://datashapes.org/dash#DatePickerEditor': DateInput,
  'http://datashapes.org/dash#BooleanSelectEditor': Checkbox,
  // Fallback: if sh:in exists, use Select; else default to TextInput
};
```

Widget props interface:

```typescript
interface WidgetProps {
  value: any;
  onChange: (value: any) => void;
  property: PropertySchema;
  errors?: string[];
  readOnly?: boolean;
}
```

## Integration with Generator Webapp

Replace existing manual forms in `/work/generator/webapp/frontend/src/views/*.tsx`:

**Before (AddCitationView.tsx, lines 172-193):**
```tsx
<form onSubmit={handleSubmit}>
  <Label htmlFor="fact-key-input">Fact key</Label>
  <Input id="fact-key-input" required value={factKey} onChange={(e) => setFactKey(e.target.value)} />
  
  <Label htmlFor="author-input">Author</Label>
  <Input id="author-input" required value={author} onChange={(e) => setAuthor(e.target.value)} />
  
  <Label htmlFor="comment-input">Comment</Label>
  <Input id="comment-input" value={comment} onChange={(e) => setComment(e.target.value)} />
  
  <Label htmlFor="is-correction-input">Is correction</Label>
  <Checkbox id="is-correction-input" checked={isCorrection} onCheckedChange={(checked) => setIsCorrection(checked === true)} />
  
  <Button type="submit" disabled={submitting}>Submit citation</Button>
</form>
```

**After (shape-driven):**
```tsx
<ShapeForm
  shape={citationShape}  // Loaded from SHACL definition, not hardcoded
  onSubmit={handleSubmit}
  submitLabel="Submit citation"
/>
```

The citation shape (SHACL+DASH definition, stored as RDF/Turtle or JSON-LD):

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix dash: <http://datashapes.org/dash#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix : <http://openfaster.org/shapes/> .

:CitationShape
  a sh:NodeShape ;
  sh:targetClass :Citation ;
  rdfs:label "Citation" ;
  sh:property [
    sh:path :factKey ;
    sh:name "Fact key" ;
    sh:datatype xsd:string ;
    sh:minCount 1 ;
    sh:order 1 ;
    dash:editor dash:TextFieldEditor ;
  ] ;
  sh:property [
    sh:path :author ;
    sh:name "Author" ;
    sh:datatype xsd:string ;
    sh:minCount 1 ;
    sh:order 2 ;
    dash:editor dash:TextFieldEditor ;
  ] ;
  sh:property [
    sh:path :comment ;
    sh:name "Comment" ;
    sh:datatype xsd:string ;
    sh:order 3 ;
    dash:editor dash:TextAreaEditor ;
  ] ;
  sh:property [
    sh:path :isCorrection ;
    sh:name "Is correction" ;
    sh:datatype xsd:boolean ;
    sh:order 4 ;
    dash:editor dash:BooleanSelectEditor ;
  ] .
```

## Migration Strategy

**Phase 1: Core Engine (ui package only, generator unchanged)**
1. Build shape-renderer module in `@openfaster-standard/ui`
2. Ship as minor version bump (e.g. 0.3.0 → 0.4.0), fully backward-compatible
3. Existing base components (`Button`, `Input`, etc.) unchanged - still exported, still usable manually
4. New exports: `ShapeForm`, `ShapeTable`, `ShapeDetail`

**Phase 2: Generator Integration (replace manual forms)**
1. Define SHACL+DASH shapes for Citation, Review, PageDetail (stored in `generator/shapes/`)
2. Replace `AddCitationView`'s manual form with `<ShapeForm shape={citationShape} />`
3. Replace `ReviewView`'s manual review form with `<ShapeForm shape={reviewShape} />`
4. Replace `IndexView`/`PageDetailView` tables with `<ShapeTable>` or manual composition (implementation's call per view)

**Phase 3: Complete Shape Coverage**
1. Every generator view uses shape-driven rendering for all data entry/display
2. Page shell, empty states, navigation still manual (not data-driven, so shapes don't apply)
3. Future: any new OpenFASTER app (beyond generator) starts from shapes, not manual component assembly

## Non-Goals (Explicit Boundaries)

- **Not a full RDF triplestore UI**: This isn't a generic Solid/LDP browser. Shapes live as static definitions loaded at build/runtime, not queried from a live SPARQL endpoint.
- **Not replacing all manual UI**: Navigation, layouts, error boundaries, empty states - still manual React. Only data-driven forms/tables/details become shape projections.
- **Not backward-incompatible**: Existing `@openfaster-standard/ui` consumers (if any beyond generator) keep working - base components still exported, shape renderer is additive.
- **No visual redesign**: Shapes describe structure (fields, order, constraints), not visual theme. Tailwind tokens, shadcn variants - unchanged. The "looks unprofessional" fix is structural consistency, not color changes.

## File Structure After Implementation

```
packages/ui/
  src/
    shape-renderer/
      core/
        parser.ts                   # ~200 lines: JSON-LD → NodeShapeSchema
        parser.test.ts
        schema.ts                   # ~100 lines: TypeScript interfaces
      widgets/
        TextInput.tsx               # ~50 lines each: WidgetProps → base component
        NumberInput.tsx
        DateInput.tsx
        Checkbox.tsx
        Select.tsx
        Textarea.tsx
        WidgetProps.ts              # Shared interface
        index.ts                    # Widget registry
      renderers/
        FormRenderer.tsx            # ~300 lines: NodeShapeSchema → form JSX
        FormRenderer.test.tsx
        TableRenderer.tsx           # ~200 lines: NodeShapeSchema → table JSX
        TableRenderer.test.tsx
        DetailRenderer.tsx          # ~150 lines: read-only variant
        DetailRenderer.test.tsx
      validation/
        validator.ts                # ~150 lines: runtime SHACL validation
        validator.test.ts
      index.ts                      # Public exports
    components/ui/                  # Unchanged (existing base components)
    index.ts                        # Re-exports both
  package.json                      # New dep: jsonld (for RDF parsing)
  README.md                         # Updated: shape-driven usage examples

generator/
  shapes/
    citation.ttl                    # SHACL+DASH definition
    review.ttl
    page-detail.ttl
  webapp/frontend/src/
    shapes.ts                       # Imports/parses .ttl files (via Vite raw loader)
    views/
      AddCitationView.tsx           # Now <ShapeForm shape={citationShape} />
      ReviewView.tsx                # Now <ShapeForm shape={reviewShape} />
      IndexView.tsx                 # Hybrid: shape table + manual nav/filters
      PageDetailView.tsx            # Hybrid: shape detail + manual history table
```

## Relationship to Tasks 1 & 2

- **Task 1 (RDF+SHACL semantic model)** defines layer 1 (format ontologies) and layer 2 (standard-specific shapes) for **ground-truth sources** (XSD, PDF). This task (3) uses SHACL+DASH shapes for **application data models** (citations, reviews) - same technology, different domain.
- **Task 2 (declarative transformation)** turns annotated shapes into documents (Bikeshed, Excel). This task (3) turns annotated shapes into **UI** (forms, tables). Parallel applications of the same "shapes as projections" principle.
- **Shared foundation**: All three tasks prove SHACL isn't just validation - it's a general-purpose semantic modeling layer that drives generators (task 2), UI (task 3), and ground-truth annotation (task 1).

## Dependencies Justification

**Task 1 (RDF+SHACL model)**: This task adopts SHACL+DASH as the UI schema language, building on Task 1's establishment of RDF+SHACL as the project's semantic foundation. Without Task 1's ontology/shape infrastructure, there's no precedent for "shapes drive projections."

**Task 2 (transformation layer)**: This task is a parallel application of the same "shapes → projections" pattern Task 2 establishes for documents. Both prove the generality of declarative transformation from a single semantic model. Conceptually coupled, though implementation-independent (Task 2 outputs Bikeshed/Excel; Task 3 outputs React JSX).

**Test Strategy:**

## Verification Strategy

### 1. Shape Parser Tests (`packages/ui/src/shape-renderer/core/parser.test.ts`)

**Test shape definitions** (fixtures in Turtle/JSON-LD):
- Minimal shape: one property, no DASH hints → defaults to TextInput
- Full shape: all property types (string, number, date, boolean, enumeration), all DASH editors, sh:order, sh:group, sh:minCount/maxCount, sh:pattern
- Malformed shapes: missing sh:path, unknown dash:editor, invalid datatype → parser errors clearly, doesn't silently drop fields

**Assertions**:
```typescript
test('parses minimal shape with defaults', () => {
  const parsed = parseShape(minimalShapeTurtle);
  expect(parsed.properties).toHaveLength(1);
  expect(parsed.properties[0].editor).toBe('http://datashapes.org/dash#TextFieldEditor'); // default
  expect(parsed.properties[0].order).toBe(0); // default
});

test('parses full shape with all DASH hints', () => {
  const parsed = parseShape(fullShapeTurtle);
  expect(parsed.properties).toHaveLength(5);
  expect(parsed.properties[0].order).toBe(1); // explicit sh:order
  expect(parsed.properties[1].editor).toBe('http://datashapes.org/dash#NumberEditor');
  expect(parsed.properties[2].in).toEqual(['approved', 'rejected']); // sh:in enumeration
});

test('errors on malformed shape', () => {
  expect(() => parseShape(noPathShape)).toThrow('missing required sh:path');
});
```

### 2. Widget Rendering Tests (`packages/ui/src/shape-renderer/widgets/*.test.tsx`)

**Per widget** (Vitest + React Testing Library):
- Renders with value, fires onChange on user interaction
- Shows validation errors passed via props
- Read-only mode disables interaction
- Widget-specific behavior (e.g. NumberInput rejects non-numeric input)

**Example (TextInput.test.tsx)**:
```typescript
test('renders value and fires onChange', async () => {
  const onChange = vi.fn();
  const { getByRole } = render(
    <TextInput value="initial" onChange={onChange} property={mockProperty} />
  );
  const input = getByRole('textbox');
  expect(input).toHaveValue('initial');
  await userEvent.type(input, ' updated');
  expect(onChange).toHaveBeenLastCalledWith('initial updated');
});

test('shows validation errors', () => {
  const { getByText } = render(
    <TextInput value="" onChange={vi.fn()} property={mockProperty} errors={['Required field']} />
  );
  expect(getByText('Required field')).toBeInTheDocument();
});
```

### 3. Form Renderer Tests (`packages/ui/src/shape-renderer/renderers/FormRenderer.test.tsx`)

**Test scenarios**:
- Renders all properties in sh:order
- Groups fields by sh:group (if present), ungrouped fields first
- Validates on submit (sh:minCount, sh:pattern, sh:datatype)
- Fires onSubmit with structured data matching shape
- Fires onValidationError with field-level errors
- Pre-fills from initialData prop

**Assertions**:
```typescript
test('renders fields in sh:order', () => {
  const { getAllByRole } = render(<ShapeForm shape={orderedShape} onSubmit={vi.fn()} />);
  const inputs = getAllByRole('textbox');
  expect(inputs[0]).toHaveAttribute('name', 'factKey'); // order 1
  expect(inputs[1]).toHaveAttribute('name', 'author');  // order 2
});

test('validates required fields on submit', async () => {
  const onSubmit = vi.fn();
  const onError = vi.fn();
  const { getByRole } = render(
    <ShapeForm shape={citationShape} onSubmit={onSubmit} onValidationError={onError} />
  );
  await userEvent.click(getByRole('button', { name: 'Submit' }));
  expect(onSubmit).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalledWith(expect.objectContaining({
    factKey: ['Required field (sh:minCount 1)'],
    author: ['Required field (sh:minCount 1)'],
  }));
});

test('submits valid data', async () => {
  const onSubmit = vi.fn();
  const { getByRole, getByLabelText } = render(
    <ShapeForm shape={citationShape} onSubmit={onSubmit} />
  );
  await userEvent.type(getByLabelText('Fact key'), 'test-key');
  await userEvent.type(getByLabelText('Author'), 'test-author');
  await userEvent.click(getByRole('button', { name: 'Submit' }));
  expect(onSubmit).toHaveBeenCalledWith({
    factKey: 'test-key',
    author: 'test-author',
    comment: '',
    isCorrection: false,
  });
});
```

### 4. Table Renderer Tests (`packages/ui/src/shape-renderer/renderers/TableRenderer.test.tsx`)

**Test scenarios**:
- Renders column headers from sh:name
- Renders row data matching property paths
- Fires onRowClick when row clicked
- Empty state when data array empty

### 5. Validation Logic Tests (`packages/ui/src/shape-renderer/validation/validator.test.ts`)

**Test SHACL constraint enforcement**:
- sh:minCount: empty value fails if minCount > 0
- sh:maxCount: array/multi-value exceeds limit
- sh:datatype: "abc" fails for xsd:integer
- sh:pattern: "123" fails pattern "^[A-Z]"
- sh:in: "other" fails enumeration ["approved", "rejected"]

**Returns structured errors**:
```typescript
test('validates sh:minCount', () => {
  const errors = validate({ factKey: '' }, citationShape);
  expect(errors.factKey).toEqual(['Required field (sh:minCount 1)']);
});

test('validates sh:pattern', () => {
  const errors = validate({ code: 'abc' }, codeShape);
  expect(errors.code).toEqual(['Must match pattern: ^[A-Z0-9]+$']);
});
```

### 6. Generator Integration Tests (webapp/frontend/src/views/*.test.tsx)

**Replace existing manual-form tests with shape-driven equivalents**:

**AddCitationView.test.tsx** (after migration):
```typescript
test('submits citation via shape form', async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ fact_key: 'test' }) });
  const { getByLabelText, getByRole } = render(<AddCitationView />);
  
  // Fields now come from citationShape, not hardcoded JSX
  await userEvent.type(getByLabelText('Fact key'), 'test-key');
  await userEvent.type(getByLabelText('Author'), 'test-author');
  await userEvent.click(getByRole('button', { name: 'Submit citation' }));
  
  expect(global.fetch).toHaveBeenCalledWith('/api/citations', expect.objectContaining({
    body: JSON.stringify({ fact_key: 'test-key', author: 'test-author', ... }),
  }));
});
```

### 7. Storybook Stories (`packages/ui/src/shape-renderer/*.stories.tsx`)

**Each renderer gets real stories**:
- `ShapeForm`: citation shape, review shape, contact form shape (variety of widgets)
- `ShapeTable`: list of citations (realistic data)
- `ShapeDetail`: single citation (read-only)

**Visual regression via Chromatic** (already configured in ui package):
- Baseline screenshots for each story
- Catches unintended style drift when widgets/renderers change

### 8. Manual End-to-End Verification (Playwright)

**Against running generator webapp** (port 8012, per existing convention):

1. **Add citation flow**:
   - Navigate to `/add`, open a family accordion
   - Click "Cite this" on a candidate → dialog opens
   - **Verify fields match citationShape** (fact key, author, comment, is_correction - in that order, right widgets)
   - Fill valid data → submit succeeds, navigates to `/pages/:factKey`
   - Fill invalid data (empty required fields) → inline validation errors appear, submit blocked

2. **Review flow**:
   - Navigate to `/review`, open a flagged fact_key accordion
   - Click "Review" on a flagged leaf → dialog opens
   - **Verify fields match reviewShape** (reviewer, verdict radio/buttons, reasoning textarea)
   - Submit review → POST succeeds, flagged item disappears from list

3. **Table rendering**:
   - Navigate to `/` → verify index table columns match pageListShape (if table is shape-driven)
   - Navigate to `/pages/:factKey` → verify history table columns match revisionShape (if table is shape-driven)

4. **Shape changes propagate to UI**:
   - Edit `generator/shapes/citation.ttl`: add new optional field `sh:property [ sh:path :source ; sh:name "Source" ; sh:order 2.5 ]`
   - Rebuild ui package + webapp
   - Refresh `/add`, open cite dialog → **new "Source" field appears between "Author" and "Comment"**, no JSX changed

**Acceptance criteria**: Every manual form/table in generator webapp that *was* hardcoded JSX is now driven by a SHACL shape, and changing the shape changes the UI with zero React code edits.

### 9. Backward Compatibility Check

**Ensure existing ui consumers (if any) don't break**:
- Install new `@openfaster-standard/ui` version in a blank Vite+React project
- Import and use base components manually: `import { Button, Input } from '@openfaster-standard/ui'`
- Verify they still work (no breaking API changes)
- Shape renderer is opt-in: apps not using `<ShapeForm>` aren't affected

### 10. Documentation Validation

**README examples actually run**:
- Copy-paste every code snippet from `packages/ui/README.md` (shape definitions, `<ShapeForm>` usage, widget registry extension)
- Run in a real project → no errors, renders as described

## Definition of Done

- All unit tests pass (parser, widgets, renderers, validator) with >90% coverage
- All integration tests pass (generator views using shape forms)
- Storybook stories render for all three renderers (`ShapeForm`, `ShapeTable`, `ShapeDetail`)
- Manual Playwright verification complete, including shape-change propagation test
- Generator webapp's `AddCitationView` and `ReviewView` use `<ShapeForm>`, verified via code review
- `@openfaster-standard/ui` published as new minor version (e.g. 0.4.0)
- Generator webapp rebuilt against new ui version, deployed to reserved port 8012
- README updated with shape-driven usage examples, not just base component examples
