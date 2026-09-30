# Task ID: 2

**Title:** Design and implement declarative transformation layer (RML/SPARQL CONSTRUCT/XSLT-inspired)

**Status:** done

**Dependencies:** 1 ✓

**Priority:** high

**Description:** Build a pure stateless graph-to-graph/graph-to-document transformation engine for annotated shapes, based on real prior art (RML for heterogeneous source mapping, SPARQL CONSTRUCT/SHACL-AF for RDF-to-RDF transformation, XSLT for XML-to-XML). Enables the openfaster-spec repo's hand-written Python Bikeshed/Excel generators to become genuine generated projections of the same annotated model.

**Details:**

## Overview

This task implements the declarative transformation layer that turns semantically-annotated shapes (from Task 1's RDF+SHACL model) into concrete output documents or other shapes. This is a **pure stateless mapping** system with no process state - only genuinely multi-step, stateful interactions belong in a separate stateful-process layer.

**Ground Truth Prior Art** (not invented here, built on proven patterns):
- **RML (RDF Mapping Language)**: Mapping heterogeneous sources (XML, XLSX, CSV, JSON) into RDF
- **SPARQL CONSTRUCT / SHACL-AF (SHACL Advanced Features rules)**: RDF-to-RDF transformations
- **XSLT**: Specifically for XML-to-XML transformation cases
- **Content-addressed build systems** (Nix, Bazel): Pure, deterministic transformations with caching

## Architecture

### Core Principles

1. **Stateless Graph Transformations**: Input graph + transformation rules → output graph/document, deterministically
2. **No Hidden Process State**: Every transformation is a pure function - same input always produces same output
3. **Declarative Rules**: Written as SPARQL CONSTRUCT queries, RML mappings, or XSLT templates (not imperative code)
4. **Composable Pipelines**: Chain transformations: RDF → RDF → XML → Excel, each step declarative
5. **Content-Addressed Caching**: Hash(inputs + rules) = cache key, like Nix/Bazel

### Three Transformation Categories

#### 1. RDF-to-RDF (SPARQL CONSTRUCT / SHACL-AF Rules)

**Use Case**: Derive new semantic facts from existing annotations
- Infer business rules from XSD constraints
- Cross-link related concepts across standards
- Normalize representations (e.g., date formats)

**Technology**: SPARQL CONSTRUCT queries + SHACL Advanced Features rules

**Example**: Derive "required field at submission" from XSD minOccurs=1
```sparql
CONSTRUCT {
    ?field a mikadiv:RequiredAtSubmission .
}
WHERE {
    ?field a layer1:XMLElement ;
           layer1:minOccurs ?min .
    FILTER(?min > 0)
}
```

#### 2. RDF-to-Document (RML-Inspired Mappings)

**Use Case**: Generate concrete output documents from semantic model
- XML instance documents from RDF facts
- Excel worksheets with data validation
- HTML specification documents (Bikeshed replacement)
- JSON API schemas

**Technology**: Custom mapping language inspired by RML's logical source + subject/predicate/object maps

**Example Mapping** (pseudo-syntax):
```yaml
mapping:
  source: 
    query: |
      SELECT ?name ?type ?required WHERE {
        ?field a mikadiv:DataField ;
               rdfs:label ?name ;
               layer1:datatype ?type ;
               mikadiv:required ?required .
      }
  target:
    format: excel
    sheet: "Field Definitions"
    columns:
      - name: "Field Name"
        value: "?name"
      - name: "Data Type"  
        value: "?type"
      - name: "Required"
        value: "?required"
```

#### 3. Document-to-Document (XSLT + Custom Engines)

**Use Case**: Transform concrete documents into other formats
- XML → HTML (specification rendering)
- XML → Excel (filled forms)
- Excel → JSON (API interchange)

**Technology**: 
- XSLT 3.0 for XML transformations
- Custom Python engines for XLSX/CSV/JSON (using openpyxl, pandas)
- Template-based generation (Jinja2 for complex HTML)

### Transformation Registry

A central registry (`transformations/registry.py`) catalogs all available transformations:

```python
@dataclass
class TransformationSpec:
    id: str                           # "mikadiv-fm-to-bikeshed"
    input_type: str                   # "rdf/turtle", "xml", "xlsx"
    output_type: str                  # "html", "xlsx", "json"
    engine: TransformationEngine      # SPARQL, RML, XSLT, Custom
    rules_path: Path                  # Path to SPARQL/XSLT/RML file
    dependencies: list[str]           # Other transformation IDs
    cache_key_inputs: list[str]       # What affects cache validity
```

Registry enables:
- Discovery: `list_transformations(input_type="rdf/turtle")`
- Execution: `apply_transformation(transform_id, input_graph)`
- Caching: `compute_cache_key(transform_id, input_hash)`
- Validation: `validate_transformation_chain([t1, t2, t3])`

## Implementation Steps

### Phase 1: Design & Research

**Design Spec** (`docs/specs/declarative-transformation-layer-design.md`):
1. Detailed comparison of RML, SPARQL CONSTRUCT, SHACL-AF, XSLT approaches
2. Syntax design for each transformation type (concrete examples)
3. Caching strategy: content-addressed, invalidation rules
4. Error handling: malformed rules, missing data, type mismatches
5. Integration with Task 1's RDF+SHACL model (input contracts)
6. Integration with existing `reference_model` (provenance tracking)
7. Openfaster-spec migration path: replacing hand-written Python generators

**Research Deliverables**:
- Survey of RML processors (RMLMapper, Morph-RDB) - can we use existing tools or need custom?
- SPARQL engine evaluation: rdflib vs. Oxigraph for CONSTRUCT queries
- XSLT processor: lxml vs. Saxon (if XPath 3.0 features needed)
- Performance benchmarks: transform 1000-element graph in <5s

### Phase 2: Core Transformation Engines

**2.1 SPARQL CONSTRUCT Engine** (`transformations/engines/sparql_construct.py`)
```python
class SparqlConstructEngine(TransformationEngine):
    def apply(self, input_graph: Graph, rules_path: Path) -> Graph:
        construct_query = load_sparql_query(rules_path)
        result_graph = input_graph.query(construct_query).graph
        return result_graph
        
    def validate_rules(self, rules_path: Path) -> list[ValidationError]:
        # Parse SPARQL, check syntax, verify referenced prefixes exist
        pass
```

**2.2 RML-Inspired Mapping Engine** (`transformations/engines/rml_mapper.py`)
```python
class RmlMappingEngine(TransformationEngine):
    def apply(self, input_graph: Graph, mapping_path: Path) -> Document:
        mapping = load_mapping_yaml(mapping_path)
        sparql_results = input_graph.query(mapping.source.query)
        
        if mapping.target.format == "excel":
            return generate_excel(sparql_results, mapping.target)
        elif mapping.target.format == "xml":
            return generate_xml(sparql_results, mapping.target)
        # ... other formats
```

**2.3 XSLT Engine** (`transformations/engines/xslt_engine.py`)
```python
class XsltEngine(TransformationEngine):
    def apply(self, input_doc: ET.Element, xslt_path: Path) -> ET.Element:
        xslt_tree = ET.parse(xslt_path)
        transform = ET.XSLT(xslt_tree)
        result = transform(input_doc)
        return result
```

**2.4 Custom Python Engines** (for XLSX, CSV, JSON-specific logic)
- Leverage existing libraries: openpyxl, pandas, Jinja2
- Well-defined input/output contracts (inherit from `TransformationEngine`)
- Unit tests with real examples from MiKaDiv-FM

### Phase 3: Transformation Registry & Pipeline

**Registry Implementation** (`transformations/registry.py`):
```python
class TransformationRegistry:
    def register(self, spec: TransformationSpec):
        # Validate spec, check for cycles in dependencies
        pass
        
    def get(self, transform_id: str) -> TransformationSpec:
        pass
        
    def list_by_input_type(self, input_type: str) -> list[TransformationSpec]:
        pass
        
    def build_pipeline(self, output_goal: str) -> list[TransformationSpec]:
        # Dependency resolution: find chain from available inputs to goal
        pass
```

**Pipeline Executor** (`transformations/pipeline.py`):
```python
class TransformationPipeline:
    def execute(self, 
                steps: list[TransformationSpec],
                initial_input: Any) -> Any:
        result = initial_input
        for step in steps:
            engine = get_engine(step.engine)
            result = engine.apply(result, step.rules_path)
        return result
        
    def execute_cached(self, 
                       steps: list[TransformationSpec],
                       initial_input: Any,
                       cache_dir: Path) -> Any:
        # Content-addressed caching: hash each step's inputs
        for step in steps:
            cache_key = compute_cache_key(step, hash(result))
            if cache_exists(cache_dir, cache_key):
                result = load_from_cache(cache_dir, cache_key)
            else:
                result = apply_and_cache(step, result, cache_dir, cache_key)
        return result
```

### Phase 4: Real Transformation Examples

**4.1 MiKaDiv-FM to Bikeshed HTML**
Replace `openfaster-spec` repo's hand-written `mikadiv_fm_spec_generator.py`:

Transformation chain:
1. **RDF → Enriched RDF**: SPARQL CONSTRUCT to infer field categories, required/optional status
2. **Enriched RDF → Bikeshed Markdown**: RML-style mapping to `.bs` template
3. **Bikeshed Markdown → HTML**: External Bikeshed processor (existing tool)

File: `transformations/examples/mikadiv_fm_to_bikesbed.yaml`

**4.2 XSD Constraints → Excel Validation Rules**
Transformation chain:
1. **XSD RDF → Constraint RDF**: Extract xs:pattern, xs:minLength, xs:maxInclusive as SHACL constraints
2. **Constraint RDF → Excel Workbook**: Map SHACL shapes to Excel data validation rules

File: `transformations/examples/xsd_constraints_to_excel.yaml`

**4.3 Annotated Model → JSON Schema**
For API generation:
1. **RDF → JSON Schema RDF**: Map SHACL shapes to JSON Schema vocabulary
2. **JSON Schema RDF → JSON Schema Document**: RML mapping to actual .json

File: `transformations/examples/shacl_to_json_schema.yaml`

### Phase 5: Integration with Existing Codebase

**Integration Points**:

1. **With `reference_model.Reference`**: 
   - Every transformation step records provenance: which input References produced which output triples/elements
   - Output documents include citation metadata (what XSD element, what PDF section)

2. **With `discovery/xsd_discoverer.py`**:
   - Discovery identifies citable elements → Reference objects
   - Transformation layer consumes those References as semantic RDF input
   - Pipeline: XSD discovery → RDF annotation → SPARQL enrichment → output generation

3. **With `references_catalog/`**:
   - Catalog stores versioned References (already implemented)
   - Transformations operate on specific catalog versions: "generate spec from v1.02"
   - Transformation outputs are also versioned, content-addressed

4. **With `webapp/` API**:
   - New endpoint: `POST /transform` with `{transform_id, input_reference_id}`
   - Frontend triggers transformations on-demand (e.g., "generate Excel template")
   - Stream transformation progress via WebSocket for long-running pipelines

### Phase 6: Caching & Performance

**Content-Addressed Cache**:
```python
def compute_cache_key(transform_spec: TransformationSpec, 
                      input_hash: str) -> str:
    # Hash of: transformation rules file + input content hash
    rules_content = transform_spec.rules_path.read_bytes()
    combined = input_hash.encode() + rules_content
    return hashlib.sha256(combined).hexdigest()
```

**Cache Invalidation**:
- Transformation rules change → different hash → cache miss (correct)
- Input data changes → different input_hash → cache miss (correct)
- Explicit cache clear: `clear_cache(before_date=...)`

**Performance Targets**:
- Small transformation (10-element RDF graph → 1-page HTML): <1s
- Medium transformation (1000-element graph → 10-page Excel): <5s
- Large transformation (full MiKaDiv-FM spec → 50-page Bikeshed): <30s

## Technology Stack

- **SPARQL Engine**: rdflib (Python, built-in SPARQL 1.1 support)
- **RDF Library**: rdflib for graph operations, serialization
- **XSLT Processor**: lxml (libxslt bindings, XSLT 1.0; upgrade to Saxon if 3.0 needed)
- **Excel Generation**: openpyxl (write XLSX with data validation, formulas)
- **Template Engine**: Jinja2 for HTML/Markdown generation
- **Caching**: Filesystem-based (like Bazel's cache), stored under `/work/generator/.cache/transformations/`
- **Configuration Format**: YAML for mapping definitions (human-readable, version-controlled)

## Testing Strategy

### Unit Tests

**Engine Tests** (`tests/transformations/engines/`):
- `test_sparql_construct.py`: CONSTRUCT query produces expected triples
- `test_rml_mapper.py`: RDF query results correctly mapped to Excel columns
- `test_xslt_engine.py`: XML → XML transformation matches expected output

**Registry Tests** (`tests/transformations/test_registry.py`):
- Register transformation, retrieve by ID
- List by input/output type
- Dependency resolution (A → B → C builds correct pipeline)
- Cycle detection (A → B → A raises error)

### Integration Tests

**End-to-End Pipelines** (`tests/transformations/integration/`):
- Load real MiKaDiv-FM RDF graph
- Apply `mikadiv_fm_to_bikeshed` transformation chain
- Validate output HTML has expected structure (headings, field tables)

**Cache Tests**:
- First run: transformation executes, result cached
- Second run: cache hit, no re-execution (measure time difference)
- Rule change: cache miss, re-executes correctly
- Input change: cache miss, re-executes correctly

**Real-World Validation**:
- Compare generated Bikeshed HTML to existing hand-written spec (visual diff)
- Verify Excel workbook has correct data validation (open in LibreOffice, test constraints)
- JSON Schema validates sample data that should pass/fail

## Migration Path for Openfaster-Spec Repo

**Current State** (hand-written Python):
- `scripts/mikadiv_fm_spec_generator.py`: 500+ lines of imperative code
- Mixes data extraction, business logic, formatting, output generation
- Hard to test, hard to extend to other standards

**Target State** (declarative transformations):
- `transformations/examples/mikadiv_fm_to_bikeshed.yaml`: 100 lines of SPARQL + mapping rules
- Separate concerns: data (RDF graph), rules (SPARQL), formatting (templates)
- Same transformations work for any standard (just change input RDF)

**Migration Steps**:
1. Extract data extraction logic → RDF graph (already in Task 1)
2. Write SPARQL CONSTRUCT for business logic (field categorization, etc.)
3. Write RML mapping for Bikeshed template generation
4. Run both old and new generators, compare outputs (should be identical)
5. Once validated, delete old Python generator, keep only declarative rules

## Dependencies

**Depends On**:
- **Task 1** (RDF+SHACL semantic annotation model): This transformation layer consumes the RDF graphs Task 1 produces. Cannot start implementation until Task 1's layer 1/layer 2 ontologies and SHACL shapes exist.

**Depended On By** (future tasks):
- Stateful process layer: Uses transformations as individual steps in workflows
- UI generation: Uses RDF-to-HTML/RDF-to-React transformations
- SSSOM alignment: Uses RDF-to-RDF transformations for cross-standard mapping
- Multi-standard generators: Generic pipelines parameterized by standard-specific RDF

## Non-Goals (Explicit Exclusions)

- **NOT** a general-purpose ETL system (not moving data between databases)
- **NOT** a workflow orchestrator (stateful processes are a separate task)
- **NOT** real-time streaming transformations (batch-oriented, file-based)
- **NOT** a visual transformation designer (rules written as SPARQL/YAML, not drag-drop)
- **NOT** automatic transformation inference (ML-based, too complex)
- **NOT** bidirectional transformations (one-way only: input → output)

## Definition of Done

1. ✅ Design spec written to `docs/specs/declarative-transformation-layer-design.md` and approved
2. ✅ Three transformation engines implemented: SPARQL CONSTRUCT, RML Mapper, XSLT
3. ✅ Transformation registry with dependency resolution
4. ✅ Content-addressed caching with invalidation
5. ✅ At least 3 real transformation examples:
   - MiKaDiv-FM RDF → Bikeshed HTML (replacing openfaster-spec hand-written generator)
   - XSD constraints RDF → Excel workbook with data validation
   - SHACL shapes → JSON Schema document
6. ✅ Integration with `reference_model.Reference` for provenance tracking
7. ✅ Test suite: unit tests for each engine, integration tests for full pipelines
8. ✅ Performance: 1000-element graph transforms in <5s, with caching speedup >10x
9. ✅ Documentation: design spec, transformation authoring guide, API reference
10. ✅ Migration validation: new Bikeshed generator output matches old hand-written output

**Test Strategy:**

## Verification Strategy

### 1. Design Approval Gate

**Pre-Implementation Checkpoint**:
- [ ] Design spec in `docs/specs/declarative-transformation-layer-design.md` reviewed and approved
- [ ] Stakeholder confirmation: transformation scope covers openfaster-spec generator replacement
- [ ] Technology choices justified: rdflib vs. Oxigraph, XSLT 1.0 vs. 3.0, caching strategy
- [ ] Prior art integration verified: RML, SPARQL CONSTRUCT, XSLT patterns researched and documented

### 2. Engine Validation

**SPARQL CONSTRUCT Engine** (`tests/transformations/engines/test_sparql_construct.py`):
```python
def test_construct_basic_inference():
    input_graph = Graph()
    input_graph.parse(data="""
        @prefix ex: <http://example.org/> .
        ex:field1 a ex:XMLElement ; ex:minOccurs 1 .
    """, format="turtle")
    
    rules = """
        CONSTRUCT { ?f a ex:RequiredField . }
        WHERE { ?f ex:minOccurs ?min . FILTER(?min > 0) }
    """
    
    engine = SparqlConstructEngine()
    output_graph = engine.apply(input_graph, rules)
    
    assert (ex.field1, RDF.type, ex.RequiredField) in output_graph
```

**RML Mapping Engine** (`tests/transformations/engines/test_rml_mapper.py`):
- Positive test: Valid mapping produces expected Excel/XML/JSON output
- Schema validation: Generated Excel has correct column headers, data types
- Data validation: SHACL constraints map to Excel validation rules (dropdown, regex, range)
- Edge cases: Empty results, null values, special characters in data

**XSLT Engine** (`tests/transformations/engines/test_xslt_engine.py`):
- Simple transformation: Identity transform preserves input XML exactly
- Complex transformation: Multi-template XSLT produces expected restructured XML
- Error handling: Malformed XSLT raises clear error with line number

### 3. Registry & Pipeline Validation

**Transformation Registry** (`tests/transformations/test_registry.py`):
```python
def test_dependency_resolution():
    registry = TransformationRegistry()
    registry.register(TransformationSpec(
        id="step1", input_type="rdf", output_type="rdf", ...
    ))
    registry.register(TransformationSpec(
        id="step2", input_type="rdf", output_type="html", 
        dependencies=["step1"]
    ))
    
    pipeline = registry.build_pipeline(output_goal="html")
    assert len(pipeline) == 2
    assert pipeline[0].id == "step1"
    assert pipeline[1].id == "step2"

def test_cycle_detection():
    # A → B → A should raise CyclicDependencyError
    with pytest.raises(CyclicDependencyError):
        registry.register(TransformationSpec(...))
```

**Pipeline Executor** (`tests/transformations/test_pipeline.py`):
- Sequential execution: 3-step pipeline (RDF → RDF → XML → HTML) produces expected output
- Error propagation: Failure in step 2 of 3 raises clear error with context
- Partial results: Failed pipeline doesn't corrupt cache

### 4. Caching Validation

**Cache Key Computation** (`tests/transformations/test_caching.py`):
```python
def test_cache_key_deterministic():
    spec = load_transformation("mikadiv-to-bikeshed")
    input_graph = load_test_graph()
    
    key1 = compute_cache_key(spec, hash(input_graph))
    key2 = compute_cache_key(spec, hash(input_graph))
    
    assert key1 == key2  # Same inputs → same key

def test_cache_invalidation_on_rule_change():
    key_before = compute_cache_key(spec, input_hash)
    
    # Modify transformation rules file
    spec.rules_path.write_text(modified_rules)
    
    key_after = compute_cache_key(spec, input_hash)
    
    assert key_before != key_after  # Rules changed → different key
```

**Cache Performance**:
- First run: Measure execution time (baseline)
- Second run with cache hit: <10% of baseline time
- Cache size: <100MB for 50 transformations over 10 input versions

### 5. Real-World Integration Tests

**MiKaDiv-FM to Bikeshed** (`tests/transformations/integration/test_mikadiv_to_bikeshed.py`):
```python
def test_full_bikeshed_generation():
    # 1. Load real MiKaDiv-FM RDF graph (from Task 1's semantic model)
    rdf_graph = load_semantic_model("MiKaDiv_FM_Meldeart23", version="1.02")
    assert len(rdf_graph) > 100  # Non-trivial graph
    
    # 2. Execute transformation pipeline
    pipeline = registry.build_pipeline("bikeshed-html")
    output_html = execute_pipeline(pipeline, rdf_graph)
    
    # 3. Validate output structure
    assert "<h1>MiKaDiv-FM Meldeart 23</h1>" in output_html
    assert "AOrdNr" in output_html  # Known field name
    assert len(output_html) > 10000  # Substantial content
    
    # 4. Compare to existing hand-written generator output
    old_output = run_legacy_generator("mikadiv_fm_spec_generator.py")
    similarity = compare_html_structure(output_html, old_output)
    assert similarity > 0.95  # >95% structural match
```

**XSD Constraints to Excel** (`tests/transformations/integration/test_xsd_to_excel.py`):
- Load XSD-derived RDF graph with xs:pattern, xs:maxLength constraints
- Transform to Excel workbook
- Open workbook programmatically, verify data validation rules exist
- Test validation: Valid data accepted, invalid data rejected (via openpyxl validation)

**SHACL to JSON Schema** (`tests/transformations/integration/test_shacl_to_json_schema.py`):
- Load SHACL shape for MiKaDiv-FM field
- Transform to JSON Schema
- Validate generated schema is valid JSON Schema (via jsonschema.Draft7Validator)
- Test schema: Validate sample JSON data that should pass/fail

### 6. Provenance Tracking

**Reference Integration** (`tests/transformations/test_provenance.py`):
```python
def test_output_includes_citation_metadata():
    # Input: RDF graph with Reference provenance
    ref = Leaf(
        reference_id="abc123",
        subject_document=SubjectDocument("MiKaDiv_FM", "1.02", "..."),
        selector=XPathSelector("/xs:schema/xs:element[@name='AOrdNr']"),
        content_hash=ContentHash("sha256", "def456"),
        captured_at="2026-09-30T12:00:00Z"
    )
    rdf_graph = annotate(ref, mikadiv.AOrdNrField)
    
    # Transform to HTML
    output_html = transform(rdf_graph, "rdf-to-html")
    
    # Verify provenance preserved
    assert "data-source-ref=\"abc123\"" in output_html
    assert "MiKaDiv_FM_1.02.xsd" in output_html  # Human-readable citation
```

### 7. Performance Benchmarks

**Transformation Speed** (`tests/transformations/benchmarks/`):
- Small (10-triple RDF graph → HTML): <1s
- Medium (1000-triple graph → Excel): <5s
- Large (10,000-triple graph → Bikeshed): <30s

**Cache Speedup**:
- Measure: uncached time / cached time ratio
- Target: >10x speedup for repeated transformations
- Verify: Cache hit rate >90% in typical usage (re-generate with minor input changes)

**Memory Usage**:
- Transform 10,000-triple graph: <500MB RAM
- No memory leaks: RSS stable across 100 consecutive transformations

### 8. Migration Validation

**Openfaster-Spec Generator Replacement**:
```bash
# 1. Run old hand-written generator
cd /work/openfaster-spec
python scripts/mikadiv_fm_spec_generator.py > old_output.html

# 2. Run new declarative transformation
cd /work/generator
python -m transformations.cli apply mikadiv-to-bikeshed > new_output.html

# 3. Compare outputs
diff -u old_output.html new_output.html > diff.txt

# 4. Validate differences
# Expected: Minor whitespace, comment differences only
# Unacceptable: Missing content, broken links, incorrect field data
```

**Acceptance Criteria**:
- 100% of field names present in old output also in new output
- 100% of requirement descriptions match (modulo whitespace)
- Visual rendering: Side-by-side browser view shows no user-visible differences

### 9. Error Handling & Edge Cases

**Malformed Inputs**:
- Invalid SPARQL query: Clear syntax error with line number
- Malformed RDF graph: Parsing error with helpful message
- Missing template variable: Jinja2 UndefinedError caught, context provided

**Data Edge Cases**:
- Empty RDF graph: Transformation produces valid but empty output (not crash)
- Null values in mapping: Handled gracefully (empty cell, not "null" string)
- Unicode/special characters: Preserved correctly in XML/HTML/Excel output

**Dependency Failures**:
- Missing dependency transformation: Error lists missing ID before execution starts
- Incompatible types: Step expects "xml" but previous step outputs "rdf" → clear error

### 10. Documentation Verification

**Design Spec Completeness**:
- [ ] All RML, SPARQL CONSTRUCT, XSLT patterns documented with examples
- [ ] Caching strategy explained: cache key computation, invalidation rules
- [ ] Integration points with Task 1, reference_model, catalog all described
- [ ] Migration path for openfaster-spec repo step-by-step

**Transformation Authoring Guide** (`docs/guides/writing-transformations.md`):
- [ ] Tutorial: Write first SPARQL CONSTRUCT transformation (5 minutes)
- [ ] Tutorial: Write RML mapping to Excel (10 minutes)
- [ ] Reference: All available mapping functions, filters, formatters
- [ ] Examples: 10+ real transformation files with inline comments

**API Reference**:
- [ ] Every public function/class has docstring with example
- [ ] Type hints for all parameters and return values
- [ ] Error types documented: what they mean, how to fix

### 11. Final Acceptance Test

**Complete Workflow** (run as single script, must pass end-to-end):
```python
# Load semantic model from Task 1
rdf_graph = load_ontologies() + load_shapes("MiKaDiv_FM_Meldeart23", "1.02")

# Apply transformation pipeline
bikeshed_html = apply_transformation("mikadiv-to-bikeshed", rdf_graph)
excel_workbook = apply_transformation("shacl-to-excel", rdf_graph)
json_schema = apply_transformation("shacl-to-json-schema", rdf_graph)

# Validate all outputs
assert_valid_html(bikeshed_html)
assert_valid_excel(excel_workbook)
assert_valid_json_schema(json_schema)

# Verify provenance
assert_has_citations(bikeshed_html, rdf_graph)
assert_has_citations(excel_workbook, rdf_graph)

# Performance check
assert execution_time < 30  # seconds

# Cache verification
second_run_time = measure_time(apply_transformation("mikadiv-to-bikeshed", rdf_graph))
assert second_run_time < execution_time / 10  # >10x speedup

print("✅ All acceptance tests passed")
```

### 12. Regression Prevention

**Continuous Tests** (run on every commit):
- All unit tests (engines, registry, pipeline)
- Fast integration test (small graph → HTML, <5s runtime)
- Cache correctness test (deterministic keys, valid invalidation)

**Nightly Tests**:
- Full integration tests (all 3 real-world examples)
- Performance benchmarks (track over time, alert on >20% regression)
- Migration validation (compare to old generator, ensure parity)
