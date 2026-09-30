# Task ID: 1

**Title:** Design and implement core RDF+SHACL semantic annotation model

**Status:** pending

**Dependencies:** None

**Priority:** high

**Description:** Create a foundational RDF+SHACL representation for annotated ground-truth sources (XSD, PDF, statutes) with layer 1 (format-language ontologies) and layer 2 (standard-specific SHACL shapes), generalizing and replacing the existing reference_model.Reference concept.

**Details:**

## Overview

This task establishes the foundational semantic layer for the entire OpenFASTER generator ecosystem. It replaces the current `reference_model.Reference` (which is format-agnostic citation tracking) with a true RDF+SHACL-based semantic annotation model that captures both structural (layer 1) and regulatory (layer 2) semantics.

## Architecture

### Layer 1: Format-Language Ontologies
Define base ontologies describing what XML, XLSX, PDF, and other formats structurally ARE:
- **XML Ontology**: Elements, attributes, namespaces, schema structures (xs:element, xs:complexType, etc.)
- **PDF Ontology**: Pages, regions, text blocks, structural elements
- **General Document Ontology**: Common concepts across formats (document, section, field, constraint)

These are technology ontologies, NOT domain ontologies - they describe the mechanics of the formats themselves.

### Layer 2: Standard-Specific SHACL Shapes
For each individual standard/regulation/process (e.g., MiKaDiv-FM, other future standards):
- One SHACL shape per requirement, deliberately isolated
- NO cross-standard interpretation or unification at this layer
- Even when two standards use identical field names, treat them as separate shapes
- Each shape describes only what that specific standard requires

### Integration with Existing Code

The current `reference_model/` package (in `/work/generator/reference_model/`) provides:
- `Reference` (Leaf/Union): Format-agnostic citation tracking
- `XPathSelector`, `SvgSelector`: Concrete selectors for XSD and PDF
- `resolve()`, `cite()`: Resolution and verification functions
- Content hashing and staleness detection

The NEW semantic annotation model will:
1. **Build on top of** the existing Reference concept (not replace citation tracking)
2. Add RDF representation of the cited content's semantic meaning
3. Use SHACL to validate and describe regulatory requirements
4. Enable projections: declarative transformations, UI generation, SSSOM alignments, stateful processes

## Implementation Steps

### 1. Research & Design Phase (REQUIRED BEFORE IMPLEMENTATION)

**Brainstorm and write a comprehensive design spec to `docs/specs/` covering:**

a) **Ontology Architecture**:
   - Namespace strategy (use w3id.org or similar for persistent URIs)
   - Layer 1 format ontologies: XML, PDF, XLSX structural vocabularies
   - Relationship to existing W3C standards (XSD ontology, PDF/A, etc.)
   - How layer 1 connects to layer 2 shapes

b) **SHACL Shape Strategy**:
   - One shape per standard requirement (e.g., `MiKaDivFM_Meldeart23_AOrdNr_Shape`)
   - Shape organization: by standard, by module, by concept?
   - Property shapes, node shapes, and their relationship to layer 1
   - Validation strategy: when/how shapes are applied

c) **Integration with reference_model**:
   - How RDF graphs relate to Reference objects
   - Citation provenance: linking SHACL shapes to their source XSD/PDF regions
   - Versioning: how shapes evolve when standards change
   - Storage model: embedded RDF store (Oxigraph?) vs. file-based Turtle

d) **Projection Targets** (design for future extensibility):
   - Declarative transformations: how shapes drive data mapping
   - UI generation: deriving forms from SHACL shapes
   - SSSOM alignments: cross-standard semantic mappings
   - Stateful processes: workflow/validation driven by shapes

e) **Comparison to Prior Work**:
   - Why this replaces `docs/specs/2026-09-15-provenance-and-review-platform-design.md` (superseded)
   - What's kept vs. discarded from the old RDF/SPARQL approach
   - Lessons from XÖV/KoSIT, BIRD, XBRL, other real systems

### 2. Core Ontology Development

**Layer 1 Format Ontologies** (`ontologies/layer1/`):
- `xml-ontology.ttl`: xs:element, xs:complexType, xs:attribute, xs:sequence, etc.
- `pdf-ontology.ttl`: Page, TextBlock, Region, Structure
- `common-ontology.ttl`: Document, Field, Constraint, DataType

**Tooling**:
- Use rdflib (Python) for RDF manipulation
- Consider SHACL validation library (pySHACL)
- Canonical Turtle serialization for version control

### 3. Standard-Specific Shapes

**Layer 2 SHACL Shapes** (`shapes/mikadiv-fm/`):
- One .ttl file per XSD module (e.g., `meldeart23-shapes.ttl`)
- Derive shapes semi-automatically from XSD discovery pipeline
- Each shape cites its source using the existing `reference_model.Reference`

**Shape Generation Pipeline**:
- Leverage existing `discovery/xsd_discoverer.py` to enumerate XSD constructs
- Generate initial SHACL shapes from XSD constraints (minOccurs, maxOccurs, type restrictions)
- Augment with regulatory semantics from PDF citations
- Human review/refinement via the existing review workflow

### 4. Storage & Serialization

**Persistent RDF Store**:
- Evaluate embedded options: Oxigraph (Rust-based), rdflib in-memory + file persistence
- Schema: graphs per standard version (e.g., `<urn:openfaster:mikadiv-fm:v1.02>`)
- Integration with existing `references_catalog/` for versioned storage

**Serialization Format**:
- Turtle (.ttl) for human readability and git-friendliness
- JSON-LD for API interchange (webapp endpoints)
- Named graphs for provenance (which citation produced which triples)

### 5. API & Integration Layer

**Python API** (`semantic_model/`):
- `load_ontologies()`: Load layer 1 ontologies into RDF graph
- `load_shapes(standard, version)`: Load SHACL shapes for a specific standard
- `annotate(reference, semantic_type)`: Create RDF triples for a cited element
- `validate(data_graph, shapes_graph)`: SHACL validation
- `query(sparql)`: Query the semantic model (limited, specific use cases)

**Integration with Existing Modules**:
- `reference_model/`: Add `to_rdf()` method on Reference for semantic serialization
- `discovery/`: Enhance to suggest SHACL shapes during XSD discovery
- `citation_workflow/`: Augment citation creation with semantic annotation
- `review_workflow/`: Include SHACL validation in review pipeline

### 6. Testing Strategy

**Ontology Tests**:
- Validate all .ttl files parse correctly (rdflib)
- Check namespace consistency and URI dereferenceability
- Verify layer 1 ontologies don't contain domain-specific concepts

**Shape Tests**:
- Each SHACL shape validates against known-good examples from real XSDs
- Negative tests: shapes correctly reject invalid data
- Cross-version compatibility: v1.02 shapes don't accidentally validate v1.01 data

**Integration Tests**:
- End-to-end: XSD element → Reference → RDF annotation → SHACL validation
- Round-trip: serialize to Turtle, reload, verify identity
- Performance: validate large graphs (thousands of shapes) in reasonable time

**Real-World Validation**:
- Test against actual MiKaDiv-FM XSD files in `/work/generator/tests/corpus_fixtures.py`
- Verify shapes match real regulatory requirements from PDF sources
- Compare generated shapes to hand-written examples for quality

### 7. Documentation

**Design Documentation**:
- Comprehensive spec in `docs/specs/` covering all design decisions
- Ontology documentation: each class/property with rdfs:label, rdfs:comment
- Shape catalog: browsable listing of all SHACL shapes with examples

**Developer Documentation**:
- README in `semantic_model/` with quick-start examples
- Migration guide from old Reference to new semantic annotations
- Extension guide: how to add layer 1 support for a new format (e.g., JSON Schema)

## Technology Stack

- **RDF Library**: rdflib (Python, mature, well-documented)
- **SHACL Validation**: pySHACL (Python, implements SHACL spec)
- **Storage**: Start with file-based Turtle, evaluate Oxigraph if performance demands
- **Namespaces**: Define persistent URIs (w3id.org or openfaster.org domain)
- **Formats**: Turtle for storage, JSON-LD for API, N-Triples for diffs

## Dependencies

This is the foundational layer - it has NO dependencies on other sub-projects and must be completed first. All future sub-projects depend on this:
- Declarative transformation engine needs shapes to drive mappings
- UI generation needs shapes to derive forms
- SSSOM alignment needs semantic types to map across standards
- Stateful process layer needs shapes to define validation rules

## Non-Goals (Explicit Exclusions)

- **NOT** a general RDF/SPARQL query interface for operators
- **NOT** automatic semantic alignment (cross-standard unification happens in a separate SSSOM layer)
- **NOT** ML/NLP-based annotation (all semantic tags are human-verified or XSD-derived)
- **NOT** a replacement for citation tracking (Reference model remains, this builds on top)
- **NOT** retroactive annotation of existing citations (start fresh with new model)

## Definition of Done

1. Design spec written to `docs/specs/semantic-annotation-model-design.md` and approved
2. Layer 1 ontologies defined for XML, PDF, and common document concepts
3. Layer 2 SHACL shapes generated for at least one complete MiKaDiv-FM XSD module
4. Python API implemented with load, annotate, validate, and query functions
5. Integration with existing `reference_model.Reference` (add RDF serialization)
6. Test suite covering ontology validity, shape validation, and real XSD examples
7. Documentation: design rationale, developer guide, ontology reference
8. At least one end-to-end example: XSD element → Reference → RDF → SHACL validation → success

**Test Strategy:**

## Verification Strategy

### 1. Design Approval
- **Spec Review**: Design spec in `docs/specs/` reviewed and approved before any implementation
- **Stakeholder Validation**: Confirm layer 1/layer 2 separation aligns with operator's vision
- **Architecture Decision Records**: Document key choices (RDF library, storage, namespace strategy)

### 2. Ontology Validation
- **Syntax Tests**: All .ttl files parse without errors using rdflib
  ```python
  g = Graph()
  g.parse('ontologies/layer1/xml-ontology.ttl', format='turtle')
  assert len(g) > 0  # Non-empty graph
  ```
- **Consistency Tests**: No contradictory axioms (e.g., class also declared as property)
- **Namespace Tests**: All URIs use declared prefixes, no broken namespace references
- **Documentation Tests**: Every class has rdfs:label and rdfs:comment
- **Layer Purity**: Layer 1 ontologies contain ZERO domain-specific MiKaDiv-FM concepts

### 3. SHACL Shape Validation
- **Shape Syntax**: All shape files validate as conformant SHACL
  ```python
  from pyshacl import validate
  conforms, _, _ = validate(shapes_graph, shacl_graph=meta_shacl)
  assert conforms
  ```
- **Positive Examples**: Each shape validates known-good XSD examples
  - Real `AOrdNr` element from MiKaDiv_FM_Meldeart23_1.02.xsd
  - Real field from actual regulatory submission
- **Negative Examples**: Shapes correctly reject invalid data
  - Missing required field → sh:minCount violation
  - Wrong type → sh:datatype violation
  - Out-of-range value → sh:pattern or sh:minInclusive violation
- **Isolation Test**: Two different standards with identically-named fields have separate, non-conflicting shapes

### 4. Integration Tests
- **Reference-to-RDF Round-trip**:
  ```python
  ref = cite(xsd_doc, xpath_selector)  # Existing reference_model
  rdf_graph = ref.to_rdf()              # New semantic annotation
  assert len(rdf_graph) > 0
  assert (subject, RDF.type, layer1:XMLElement) in rdf_graph
  ```
- **Citation Provenance**: RDF annotation includes prov:wasDerivedFrom pointing to Reference
- **Version Isolation**: v1.02 shapes in separate named graph from v1.01 shapes
- **Staleness Detection**: When XSD changes, shape validation catches semantic drift

### 5. Real-World Examples
- **Complete Module**: MiKaDiv-FM Meldeart23 fully annotated
  - All xs:element constructs have corresponding SHACL shapes
  - All xs:complexType constraints captured in shape properties
  - PDF regulatory requirements linked to relevant shapes
- **End-to-End Workflow**:
  1. XSD discovery finds citable elements → 50+ candidates
  2. Citation workflow creates References → all resolve successfully
  3. Semantic annotation adds RDF triples → graph has 500+ triples
  4. SHACL validation against test data → all constraints enforced
  5. Query for "all required fields" → correct results returned

### 6. Performance Benchmarks
- **Load Time**: Load layer 1 ontologies + full MiKaDiv-FM shapes in <5 seconds
- **Validation Time**: Validate 1000-element dataset against shapes in <10 seconds
- **Query Performance**: SPARQL query for element type returns in <1 second
- **Storage Size**: Turtle serialization is human-readable, <10MB for full standard

### 7. Documentation Verification
- **Design Spec Completeness**: Covers all architectural decisions, no "TBD" sections
- **API Examples**: Every public function has working code example in docstring
- **Ontology Browser**: Generate RDF documentation (rdfs:label, rdfs:comment) as browsable HTML
- **Migration Guide**: Step-by-step instructions to annotate an existing Reference

### 8. Projection Readiness (Forward Compatibility)
- **Transformation Hooks**: Shapes include hints for declarative transformations (sh:description with mapping intent)
- **UI Generation**: Shapes have sh:order, sh:group for form layout
- **SSSOM Preparation**: Each shape has skos:prefLabel for alignment matching
- **Process Validation**: Shapes distinguish required-at-submission vs. required-at-approval

### 9. Acceptance Criteria
Run this complete test scenario and verify every step succeeds:

```python
# 1. Load ontologies
onto_graph = load_ontologies()
assert (layer1.XMLElement, RDF.type, OWL.Class) in onto_graph

# 2. Load shapes for MiKaDiv-FM v1.02
shapes = load_shapes("MiKaDiv_FM_Meldeart23", "1.02")
assert len(shapes) > 50  # Has shapes for all elements

# 3. Cite a real XSD element
ref = cite(
    SubjectDocument("MiKaDiv_FM_Meldeart23", "1.02", "..."),
    XPathSelector("/xs:schema/xs:complexType[@name='...']")
)

# 4. Annotate with semantics
semantic_graph = annotate(ref, mikadiv.AOrdNrField)
assert len(semantic_graph) > 0

# 5. Validate test data against shape
test_data = load_test_submission()  # Real MiKaDiv-FM XML
conforms, _, violations = validate(test_data, shapes_graph=shapes)
assert conforms or len(violations) == expected_violations

# 6. Query the semantic model
results = query(semantic_graph, """
    SELECT ?field WHERE {
        ?field a mikadiv:RequiredField ;
               layer1:elementName ?name .
    }
""")
assert len(results) > 0

# 7. Verify projection readiness
shape = get_shape(mikadiv.AOrdNrField)
assert shape.has_ui_hints()  # sh:order, sh:group present
assert shape.has_transformation_hints()  # Mapping metadata
```

### 10. Final Checklist
- [ ] Design spec approved and committed to `docs/specs/`
- [ ] All layer 1 ontology tests pass (XML, PDF, common)
- [ ] At least one complete layer 2 shape set (MiKaDiv-FM module)
- [ ] Integration with existing `reference_model` working
- [ ] Real XSD examples validate successfully
- [ ] Documentation complete (design, API, ontology reference)
- [ ] Performance benchmarks met (load, validate, query times)
- [ ] Projection hooks in place for future sub-projects
- [ ] Operator approval of semantic model scope and structure
