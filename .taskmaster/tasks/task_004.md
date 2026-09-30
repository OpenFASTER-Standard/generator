# Task ID: 4

**Title:** Design and implement alignment layer (SSSOM-based real-world concept mapping)

**Status:** pending

**Dependencies:** 1 ✓, 2 ✓

**Priority:** medium

**Description:** Build a semantic alignment layer that connects per-standard SHACL shapes from Task 1 to shared real-world concepts, enabling one stored fact (e.g., beneficial owner name) to populate multiple outputs without duplication. Based on SSSOM (Simple Standard for Sharing Ontology Mappings), BIRD's Input/Reporting Layer separation, and mediator-wrapper architecture.

**Details:**

## Overview

This task implements the alignment layer that connects Task 1's deliberately-isolated per-standard SHACL shapes to a shared representation of underlying real-world facts. Without this layer, the same data point (e.g., a person's given name) would need to be stored separately for each standard that requires it, with manual copying and no guarantee of consistency.

**Ground Truth Prior Art** (not invented here):
- **SSSOM (Simple Standard for Sharing Ontology Mappings)**: W3C Community Group standard for declarative semantic mappings between ontologies - already a dependency of the institutional-ontology repo (confirmed in `/work/generator` grep results showing SSSOM references)
- **BIRD (Banks' Integrated Reporting Dictionary)**: EBA's architecture separating source-facing Input Layer from report-facing Reporting Layer, connected by explicit transformation/mapping rules
- **Mediator-Wrapper Architecture (Wiederhold)**: Classical integration pattern - wrappers adapt heterogeneous sources to mediator's common schema, mediator serves unified queries

**Why This is Separate from Tasks 1 & 2**:
- **Task 1** creates per-standard shapes in deliberate isolation (two same-named fields in different standards are never assumed equivalent)
- **Task 2** transforms shapes into outputs (Bikeshed, Excel) but operates within one standard's namespace at a time
- **This task** is where cross-standard semantic equivalence is explicitly declared and enforced

## Architecture

### Three-Layer Model (Input → Alignment → Output)

Following BIRD and mediator-wrapper patterns:

**Layer 1: Input Layer (Wrappers)**
- Per-standard SHACL shapes from Task 1 (already implemented)
- Each standard's shapes in their own namespace (e.g., `mikadiv:GivenName`, `bzst-reclaim:Vorname`)
- Deliberately isolated - no cross-standard interpretation at this layer

**Layer 2: Alignment Layer (Mediator) - THIS TASK**
- SSSOM mappings connect input shapes to shared real-world concepts
- Common ontology of real-world entities (Person, Organization, FinancialAccount, etc.)
- Explicit mapping predicates: `skos:exactMatch`, `skos:closeMatch`, `sssom:subjectId`, `sssom:predicateId`, `sssom:objectId`, `sssom:mappingJustification`

**Layer 3: Output Layer (Projections)**
- Task 2's transformation layer consumes aligned data
- One query against the alignment layer retrieves data for all standards requiring it
- Output generators (Bikeshed, Excel, XML) pull from shared concepts, not duplicated per-standard storage

### SSSOM Mapping Format

Canonical TSV format (SSSOM spec):

```tsv
subject_id	subject_label	predicate_id	object_id	object_label	mapping_justification	confidence	author_id	subject_source	object_source
mikadiv:GivenName	Given name (MiKaDiv-FM)	skos:exactMatch	core:PersonGivenName	Person given name	semapv:ManualMappingCuration	0.95	urn:uuid:generator-system	https://openfaster.org/standards/mikadiv-fm	https://openfaster.org/ontologies/core
bzst-reclaim:Vorname	Vorname (BZSt Reclaim)	skos:exactMatch	core:PersonGivenName	Person given name	semapv:ManualMappingCuration	0.95	urn:uuid:generator-system	https://openfaster.org/standards/bzst-reclaim	https://openfaster.org/ontologies/core
mikadiv:Surname	Surname (MiKaDiv-FM)	skos:exactMatch	core:PersonFamilyName	Person family name	semapv:ManualMappingCuration	0.95	urn:uuid:generator-system	https://openfaster.org/standards/mikadiv-fm	https://openfaster.org/ontologies/core
```

Also serializable as RDF (Turtle):

```turtle
@prefix sssom: <https://w3id.org/sssom/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix mikadiv: <https://openfaster.org/standards/mikadiv-fm/> .
@prefix core: <https://openfaster.org/ontologies/core/> .

<urn:uuid:mapping-1>
  a sssom:Mapping ;
  sssom:subjectId mikadiv:GivenName ;
  sssom:subjectLabel "Given name (MiKaDiv-FM)" ;
  sssom:predicateId skos:exactMatch ;
  sssom:objectId core:PersonGivenName ;
  sssom:objectLabel "Person given name" ;
  sssom:mappingJustification semapv:ManualMappingCuration ;
  sssom:confidence "0.95"^^xsd:float ;
  sssom:authorId <urn:uuid:generator-system> ;
  sssom:subjectSource <https://openfaster.org/standards/mikadiv-fm> ;
  sssom:objectSource <https://openfaster.org/ontologies/core> .
```

### Core Ontology of Real-World Concepts

Minimal set covering MiKaDiv-FM first, extensible to other standards:

**`ontologies/core/persons.ttl`** (natural persons):
```turtle
@prefix core: <https://openfaster.org/ontologies/core/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

core:Person
  a owl:Class ;
  rdfs:label "Person"@en ;
  rdfs:comment "A natural person (individual human being)"@en .

core:PersonGivenName
  a owl:DatatypeProperty ;
  rdfs:domain core:Person ;
  rdfs:range xsd:string ;
  rdfs:label "Given name"@en ;
  rdfs:comment "First name, forename, or given name of a person"@en .

core:PersonFamilyName
  a owl:DatatypeProperty ;
  rdfs:domain core:Person ;
  rdfs:range xsd:string ;
  rdfs:label "Family name"@en ;
  rdfs:comment "Last name, surname, or family name of a person"@en .

core:PersonBirthDate
  a owl:DatatypeProperty ;
  rdfs:domain core:Person ;
  rdfs:range xsd:date ;
  rdfs:label "Birth date"@en .

core:PersonTaxResidence
  a owl:ObjectProperty ;
  rdfs:domain core:Person ;
  rdfs:range core:Country ;
  rdfs:label "Tax residence"@en .
```

**`ontologies/core/organizations.ttl`** (legal entities):
```turtle
core:Organization
  a owl:Class ;
  rdfs:label "Organization"@en ;
  rdfs:comment "A legal entity, company, or institution"@en .

core:OrganizationLegalName
  a owl:DatatypeProperty ;
  rdfs:domain core:Organization ;
  rdfs:range xsd:string ;
  rdfs:label "Legal name"@en .

core:OrganizationTaxId
  a owl:DatatypeProperty ;
  rdfs:domain core:Organization ;
  rdfs:range xsd:string ;
  rdfs:label "Tax identification number"@en .
```

**`ontologies/core/financial-accounts.ttl`**:
```turtle
core:FinancialAccount
  a owl:Class ;
  rdfs:label "Financial account"@en .

core:AccountNumber
  a owl:DatatypeProperty ;
  rdfs:domain core:FinancialAccount ;
  rdfs:range xsd:string ;
  rdfs:label "Account number"@en .

core:AccountBalance
  a owl:DatatypeProperty ;
  rdfs:domain core:FinancialAccount ;
  rdfs:range xsd:decimal ;
  rdfs:label "Account balance"@en .
```

### Integration with Existing reference_model

The existing `/work/generator/reference_model/` tracks citations - where a fact came from (XSD element, PDF region). The alignment layer adds a second dimension: what that cited fact semantically means across standards.

**Before alignment (Task 1 only)**:
```python
# Two separate citations, no connection
citation1 = Leaf(
    fact_key="mikadiv-given-name",
    selector=XPathSelector("//xs:element[@name='GivenName']"),
    content_hash=ContentHash("sha256", "abc123"),
)

citation2 = Leaf(
    fact_key="bzst-reclaim-vorname",
    selector=XPathSelector("//xs:element[@name='Vorname']"),
    content_hash=ContentHash("sha256", "def456"),
)

# No way to know these refer to the same real-world concept
```

**After alignment (this task)**:
```python
# Citations still separate (correct - different sources)
citation1 = Leaf(fact_key="mikadiv-given-name", ...)
citation2 = Leaf(fact_key="bzst-reclaim-vorname", ...)

# But now linked via SSSOM mappings
alignment_graph = load_sssom_mappings("alignments/mikadiv-to-core.sssom.tsv")

# Query: what core concept does mikadiv:GivenName map to?
core_concept = alignment_graph.value(
    mikadiv.GivenName, sssom.objectId
)
# → core:PersonGivenName

# Query: all standards' fields mapping to core:PersonGivenName
mapped_fields = list(alignment_graph.subjects(
    sssom.objectId, core.PersonGivenName
))
# → [mikadiv:GivenName, bzst_reclaim:Vorname, ...]
```

### Storage and Data Flow

**Storage locations**:
- SSSOM mappings: `generator/alignments/*.sssom.tsv` (canonical TSV, version-controlled)
- Core ontology: `generator/ontologies/core/*.ttl` (OWL/RDFS, version-controlled)
- Mapping provenance: `references_catalog/` (each mapping has a Reference tracking who created it, when, why)

**Data flow for multi-standard output generation**:

1. **User action**: "Generate MiKaDiv-FM filing for beneficial owner Alice Mueller"
2. **Alignment layer query**: What core concepts does MiKaDiv-FM need?
   - SPARQL query over SSSOM mappings: "all subject fields where subject source = mikadiv-fm"
   - Results: `mikadiv:GivenName → core:PersonGivenName`, `mikadiv:Surname → core:PersonFamilyName`, ...
3. **Data retrieval**: Fetch Alice's data from core storage
   - `core:PersonGivenName = "Alice"`, `core:PersonFamilyName = "Mueller"`, ...
4. **Reverse mapping**: What standard-specific fields populate from core?
   - `core:PersonGivenName → mikadiv:GivenName` (via SSSOM exactMatch)
5. **Task 2 transformation**: Generate MiKaDiv-FM XML with `<GivenName>Alice</GivenName>`
6. **Repeat for other standard**: BZSt reclaim filing needs same person
   - Same core data (`core:PersonGivenName = "Alice"`)
   - Different mapping: `core:PersonGivenName → bzst_reclaim:Vorname`
   - Different output: `<Vorname>Alice</Vorname>`

**Key invariant**: Alice's name stored ONCE as `core:PersonGivenName`, used in MANY outputs via mappings.

## Implementation Steps

### Phase 1: Design & Research

**Design Spec** (`docs/specs/alignment-layer-design.md`):
1. SSSOM spec review: required fields, confidence scoring, provenance metadata
2. Core ontology scope: which real-world entity types for MVP (Person, Organization, Account), which deferred (complex financial instruments, multi-party relationships)
3. Mapping predicates: when to use `skos:exactMatch` vs. `skos:closeMatch` vs. `skos:relatedMatch`
4. Integration with Task 1 (input shapes) and Task 2 (output transformations)
5. Institutional-ontology repo integration: how this aligns with existing ROBOT+BFO+IAO+SSSOM tooling in that repo
6. Mapping lifecycle: creation (human curator via webapp), versioning (via references_catalog), staleness detection (when source shape changes)

**Research Deliverables**:
- Survey SSSOM tooling: `sssom-py` (Python library for SSSOM I/O, validation)
- Evaluate ROBOT (OWL ontology Swiss Army knife, already used in institutional-ontology)
- Study real SSSOM mapping sets: Mondo, UMLS, Schema.org crosswalks
- Performance: 1000 mappings, query "all fields for standard X" in <100ms

### Phase 2: Core Ontology Development

**Ontology Files** (`generator/ontologies/core/`):
- `persons.ttl`: Person, PersonGivenName, PersonFamilyName, PersonBirthDate, PersonTaxResidence, PersonAddress
- `organizations.ttl`: Organization, OrganizationLegalName, OrganizationTaxId, OrganizationJurisdiction
- `financial-accounts.ttl`: FinancialAccount, AccountNumber, AccountBalance, AccountCurrency, AccountHolder (→ Person | Organization)
- `countries.ttl`: Country enumeration (ISO 3166-1 alpha-2, for tax residence, jurisdiction)
- `common.ttl`: Shared base (Address, Date, Currency, Amount)

**Ontology Validation**:
- All .ttl files parse correctly (rdflib)
- No contradictory axioms (ROBOT verify)
- All classes/properties have rdfs:label, rdfs:comment
- Passes ROBOT report (no logical inconsistencies)

### Phase 3: SSSOM Mapping Creation

**Initial Mapping Sets** (`generator/alignments/`):
- `mikadiv-to-core.sssom.tsv`: MiKaDiv-FM Meldeart 23 fields → core ontology
  - At least 50 mappings (cover all required fields for one filing type)
  - Confidence scores: 0.95 for exact matches (same concept, same cardinality), 0.8 for close matches (minor semantic differences)
- `core-metadata.sssom.yml`: SSSOM metadata (mapping set ID, creator, license, creation date)

**Mapping Creation Workflow**:
1. Load per-standard shapes (Task 1 output)
2. For each shape property:
   - Human curator reviews XSD/PDF source (via existing reference_model.Reference)
   - Matches to core ontology concept (or proposes new core concept if none fits)
   - Records mapping in SSSOM TSV
   - Justification: `semapv:ManualMappingCuration` (not automated, not lexical)
3. Validate mapping set (sssom-py validate)
4. Commit to version control

### Phase 4: SSSOM Tooling Integration

**Python API** (`alignment/`):
```python
# alignment/__init__.py
from dataclasses import dataclass
from rdflib import Graph, Namespace

SSSOM = Namespace("https://w3id.org/sssom/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

@dataclass
class Mapping:
    subject_id: str          # Standard-specific field URI
    predicate_id: str        # skos:exactMatch, skos:closeMatch, etc.
    object_id: str           # Core ontology concept URI
    confidence: float        # 0.0-1.0
    justification: str       # semapv:ManualMappingCuration, etc.
    author_id: str

def load_mappings(sssom_file: str) -> Graph:
    """Load SSSOM TSV into RDF graph using sssom-py."""
    import sssom.parsers
    mapping_set = sssom.parsers.parse_sssom_table(sssom_file)
    return mapping_set.to_rdf_graph()

def find_core_concept(graph: Graph, standard_field_uri: str) -> str | None:
    """Given a standard-specific field URI, return the core concept it maps to."""
    return graph.value(
        URIRef(standard_field_uri), SSSOM.objectId
    )

def find_standard_fields(graph: Graph, core_concept_uri: str) -> list[str]:
    """Given a core concept URI, return all standard fields mapping to it."""
    return [
        str(subj)
        for subj in graph.subjects(SSSOM.objectId, URIRef(core_concept_uri))
    ]
```

**CLI Tool** (`alignment/cli.py`):
```bash
# Validate SSSOM file
python -m alignment.cli validate alignments/mikadiv-to-core.sssom.tsv

# Query mappings
python -m alignment.cli query --subject mikadiv:GivenName
# Output: maps to core:PersonGivenName (confidence 0.95, exactMatch)

python -m alignment.cli query --object core:PersonGivenName
# Output: mapped from mikadiv:GivenName, bzst_reclaim:Vorname, ...

# Convert SSSOM TSV <-> RDF Turtle
python -m alignment.cli convert alignments/mikadiv-to-core.sssom.tsv --format turtle
```

### Phase 5: Integration with Task 2 Transformations

**Alignment-Aware Transformation Pattern**:

**Before (Task 2 only, no alignment)**:
```sparql
# Generate MiKaDiv-FM output - pulls directly from standard-specific shapes
CONSTRUCT {
    ?submission mikadiv:GivenName ?name .
}
WHERE {
    ?person mikadiv:GivenName ?name .
}
```

**After (with alignment layer)**:
```sparql
# Generate MiKaDiv-FM output - pulls from core, applies alignment
PREFIX core: <https://openfaster.org/ontologies/core/>
PREFIX mikadiv: <https://openfaster.org/standards/mikadiv-fm/>

CONSTRUCT {
    ?submission mikadiv:GivenName ?name .
}
WHERE {
    # Data stored as core concept
    ?person a core:Person ;
            core:PersonGivenName ?name .
    
    # Alignment mapping (loaded from SSSOM)
    # (In practice, this WHERE clause references a pre-loaded alignment graph)
}
```

**Transformation Engine Enhancement** (Task 2's `transformations/engines/sparql_construct.py`):
```python
class AlignmentAwareSparqlEngine(SparqlConstructEngine):
    def apply(self, data_graph: Graph, alignment_graph: Graph, 
              rules_path: Path) -> Graph:
        # Merge data + alignment graphs for query context
        combined = data_graph + alignment_graph
        construct_query = load_sparql_query(rules_path)
        result_graph = combined.query(construct_query).graph
        return result_graph
```

### Phase 6: Webapp Integration (Mapping Management UI)

**New Webapp Endpoints** (`generator/webapp/app.py`):
```python
@app.get("/api/alignments")
def list_alignments():
    """List all SSSOM mapping sets."""
    return [
        {"file": "mikadiv-to-core.sssom.tsv", "mappings": 52, "last_modified": "..."},
    ]

@app.get("/api/alignments/{file}")
def get_alignment(file: str):
    """Get specific SSSOM mapping set as JSON."""
    graph = load_mappings(f"alignments/{file}")
    return serialize_mappings_as_json(graph)

@app.post("/api/alignments/{file}/mappings")
def add_mapping(file: str, mapping: Mapping):
    """Add new SSSOM mapping to set (curator action)."""
    # Validate mapping
    # Append to SSSOM TSV
    # Record as Reference (who created it, when, why)
    # Return updated mapping set
```

**Webapp View** (React component):
```tsx
// generator/webapp/frontend/src/views/AlignmentView.tsx
// Table of mappings: [Standard Field | Predicate | Core Concept | Confidence]
// Add mapping dialog: dropdowns for source field, core concept, predicate
// Visual graph view: Cytoscape.js rendering mappings as graph
```

### Phase 7: Institutional-Ontology Repo Integration

The existing institutional-ontology repo (referenced in task description) already uses ROBOT+BFO+IAO+SSSOM. This task doesn't duplicate that tooling - instead:

**Division of Responsibility**:
- **Institutional-ontology repo**: Upper ontology (BFO), information artifact ontology (IAO), general institutional concepts (organization, role, process) - domain-independent
- **This task (generator/ontologies/core/)**: Financial-domain specific (Person, FinancialAccount, TaxResidence) - scoped to MiKaDiv-FM and similar regulatory filings
- **SSSOM mappings**: Bridge the two (e.g., `core:Person skos:broadMatch iao:InformationContentEntity`)

**Tooling Reuse**:
- Use ROBOT for ontology validation, merging, reasoning (same as institutional-ontology)
- Use sssom-py for mapping I/O, validation (same as institutional-ontology)
- Version-control workflow: same PR-review + merge pattern

**Collaboration Pattern**:
- Core concepts stabilize → propose upstreaming to institutional-ontology if general enough
- Institutional-ontology adds new general concept → import into generator/ontologies/core/ if relevant
- SSSOM mappings stay in generator repo (specific to OpenFASTER standards, not general institutional knowledge)

## Technology Stack

- **SSSOM Library**: `sssom-py` (Python, SSSOM spec reference implementation)
- **RDF Library**: `rdflib` (already used in Task 1)
- **Ontology Tooling**: ROBOT (Swiss Army knife, already used in institutional-ontology)
- **Validation**: ROBOT verify, sssom validate
- **Storage**: SSSOM TSV (canonical, diff-friendly, version-controlled)
- **Interchange**: RDF Turtle, JSON-LD (for API)
- **Visualization**: Cytoscape.js (webapp mapping graph view)

## Testing Strategy

### Unit Tests

**SSSOM I/O Tests** (`tests/alignment/test_sssom_io.py`):
- Load SSSOM TSV → RDF graph (sssom-py)
- Query mappings by subject, object, predicate
- Round-trip: TSV → RDF → TSV preserves all fields
- Validation: missing required fields raises clear error

**Core Ontology Tests** (`tests/alignment/test_core_ontology.py`):
- All .ttl files parse correctly
- ROBOT verify passes (no logical inconsistencies)
- All classes/properties have rdfs:label, rdfs:comment
- Imports resolve correctly (if core imports BFO/IAO from institutional-ontology)

### Integration Tests

**Alignment-Aware Transformation** (`tests/alignment/test_aligned_transformation.py`):
```python
def test_mikadiv_output_from_core_data():
    # 1. Create core data (Person with PersonGivenName)
    data_graph = Graph()
    data_graph.add((ex.alice, RDF.type, core.Person))
    data_graph.add((ex.alice, core.PersonGivenName, Literal("Alice")))
    
    # 2. Load SSSOM mappings (core:PersonGivenName → mikadiv:GivenName)
    alignment_graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    
    # 3. Run aligned transformation
    engine = AlignmentAwareSparqlEngine()
    output_graph = engine.apply(data_graph, alignment_graph, "transforms/core-to-mikadiv.sparql")
    
    # 4. Verify MiKaDiv-FM output has correct field
    assert (ex.submission, mikadiv.GivenName, Literal("Alice")) in output_graph
```

### Real-World Validation

**MiKaDiv-FM Complete Filing** (`tests/alignment/integration/`):
- Core data: Person (Alice Mueller, DOB 1985-03-15, tax residence DE)
- SSSOM mappings: all MiKaDiv-FM Meldeart 23 required fields mapped to core
- Transformation: generate complete MiKaDiv-FM XML via aligned transformation
- Validation: XML validates against official XSD, all required fields populated
- Round-trip: parse XML back to core concepts, verify Alice's data intact

## Dependencies

**Depends On**:
- **Task 1 (RDF+SHACL model)**: This task consumes Task 1's per-standard SHACL shapes as the "input layer" / "wrappers" to align
- **Task 2 (transformation layer)**: This task extends Task 2's transformation engine to be alignment-aware (consumes both data graph and alignment graph)

**Depended On By** (future):
- Multi-standard data entry UIs: single form populates core concepts, auto-generates multiple standards' outputs
- Cross-standard validation: detect inconsistencies when same person appears in two standards with conflicting data
- Reporting/analytics: unified queries across all standards (e.g., "all persons with tax residence in DE, from any standard")

## Non-Goals (Explicit Exclusions)

- **NOT** automatic mapping inference (ML/NLP-based schema matching) - all mappings human-curated via ManualMappingCuration
- **NOT** a data warehouse (core concepts stored in lightweight RDF graphs, not a separate relational DB)
- **NOT** real-time synchronization (batch-oriented, not streaming)
- **NOT** ontology reasoning for mapping inference (ROBOT used for validation only, not to infer new mappings)
- **NOT** replacing Task 1's per-standard shapes (those remain, this adds a layer on top)

## Definition of Done

1. Design spec written to `docs/specs/alignment-layer-design.md` and approved
2. Core ontology defined (Person, Organization, FinancialAccount, ~20 properties)
3. SSSOM mapping set: MiKaDiv-FM → core (50+ mappings, covering one complete filing type)
4. Python API: `load_mappings()`, `find_core_concept()`, `find_standard_fields()`
5. CLI tool: validate, query, convert SSSOM files
6. Task 2 integration: `AlignmentAwareSparqlEngine` implemented and tested
7. Webapp endpoints: list/get/add mappings
8. Test suite: unit tests (I/O, ontology), integration tests (aligned transformation)
9. Real-world validation: complete MiKaDiv-FM filing generated from core data
10. Documentation: design spec, mapping creation guide, API reference
11. Institutional-ontology alignment: confirm division of responsibility, no duplication

**Test Strategy:**

## Verification Strategy

### 1. Design Approval Gate

**Pre-Implementation Checkpoint**:
- [ ] Design spec in `docs/specs/alignment-layer-design.md` reviewed and approved
- [ ] Stakeholder confirmation: SSSOM approach aligns with institutional-ontology repo's existing patterns
- [ ] Scope validated: core ontology concepts cover MiKaDiv-FM MVP, extensible to other standards
- [ ] Integration points confirmed: Task 1 (shapes), Task 2 (transformations), references_catalog (provenance)

### 2. SSSOM I/O and Validation Tests

**SSSOM Loading** (`tests/alignment/test_sssom_io.py`):
```python
def test_load_sssom_tsv_to_rdf():
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    assert len(graph) > 0
    # Verify subject/object/predicate triples exist
    mappings = list(graph.subjects(RDF.type, SSSOM.Mapping))
    assert len(mappings) >= 50  # At least 50 mappings in MVP set

def test_find_core_concept():
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    core_concept = find_core_concept(graph, "https://openfaster.org/standards/mikadiv-fm/GivenName")
    assert str(core_concept) == "https://openfaster.org/ontologies/core/PersonGivenName"

def test_find_standard_fields():
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    fields = find_standard_fields(graph, "https://openfaster.org/ontologies/core/PersonGivenName")
    assert "https://openfaster.org/standards/mikadiv-fm/GivenName" in fields

def test_sssom_validation():
    # Invalid SSSOM (missing required field) raises error
    with pytest.raises(ValueError, match="missing required field"):
        load_mappings("tests/fixtures/invalid-missing-subject.sssom.tsv")
```

**Round-Trip Serialization**:
```python
def test_sssom_tsv_to_rdf_to_tsv():
    original_tsv = Path("alignments/mikadiv-to-core.sssom.tsv").read_text()
    
    # Load as RDF
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    
    # Serialize back to TSV
    roundtrip_tsv = serialize_mappings_to_tsv(graph)
    
    # Parse both, compare mappings (ignore header/comment differences)
    assert parse_mappings(original_tsv) == parse_mappings(roundtrip_tsv)
```

### 3. Core Ontology Validation Tests

**Ontology Parsing** (`tests/alignment/test_core_ontology.py`):
```python
def test_all_ontology_files_parse():
    for ttl_file in Path("ontologies/core").glob("*.ttl"):
        graph = Graph()
        graph.parse(ttl_file, format="turtle")
        assert len(graph) > 0, f"{ttl_file} is empty or invalid"

def test_all_classes_have_labels():
    graph = load_core_ontology()
    classes = list(graph.subjects(RDF.type, OWL.Class))
    for cls in classes:
        label = graph.value(cls, RDFS.label)
        assert label is not None, f"Class {cls} missing rdfs:label"
        comment = graph.value(cls, RDFS.comment)
        assert comment is not None, f"Class {cls} missing rdfs:comment"

def test_robot_verify_passes():
    # Use ROBOT to check logical consistency
    result = subprocess.run(
        ["robot", "verify", "--input", "ontologies/core/persons.ttl"],
        capture_output=True
    )
    assert result.returncode == 0, f"ROBOT verify failed: {result.stderr}"
```

**Ontology Completeness**:
```python
def test_core_ontology_covers_mvp_concepts():
    graph = load_core_ontology()
    
    # Person concepts
    assert (core.Person, RDF.type, OWL.Class) in graph
    assert (core.PersonGivenName, RDF.type, OWL.DatatypeProperty) in graph
    assert (core.PersonFamilyName, RDF.type, OWL.DatatypeProperty) in graph
    
    # Organization concepts
    assert (core.Organization, RDF.type, OWL.Class) in graph
    assert (core.OrganizationLegalName, RDF.type, OWL.DatatypeProperty) in graph
    
    # Financial concepts
    assert (core.FinancialAccount, RDF.type, OWL.Class) in graph
    assert (core.AccountBalance, RDF.type, OWL.DatatypeProperty) in graph
```

### 4. Alignment-Aware Transformation Tests

**Basic Aligned Transformation** (`tests/alignment/test_aligned_transformation.py`):
```python
def test_core_to_mikadiv_transformation():
    # Data graph: Person with core properties
    data_graph = Graph()
    data_graph.add((ex.alice, RDF.type, core.Person))
    data_graph.add((ex.alice, core.PersonGivenName, Literal("Alice")))
    data_graph.add((ex.alice, core.PersonFamilyName, Literal("Mueller")))
    
    # Alignment graph: SSSOM mappings
    alignment_graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    
    # Transformation: core → MiKaDiv-FM
    engine = AlignmentAwareSparqlEngine()
    sparql_query = """
    PREFIX core: <https://openfaster.org/ontologies/core/>
    PREFIX mikadiv: <https://openfaster.org/standards/mikadiv-fm/>
    
    CONSTRUCT {
        ?submission mikadiv:GivenName ?given ;
                   mikadiv:Surname ?family .
    }
    WHERE {
        ?person a core:Person ;
                core:PersonGivenName ?given ;
                core:PersonFamilyName ?family .
        BIND(IRI(CONCAT(str(?person), "-submission")) AS ?submission)
    }
    """
    
    output_graph = engine.apply(data_graph, alignment_graph, sparql_query)
    
    # Verify MiKaDiv-FM output
    submission_uri = URIRef(str(ex.alice) + "-submission")
    assert (submission_uri, mikadiv.GivenName, Literal("Alice")) in output_graph
    assert (submission_uri, mikadiv.Surname, Literal("Mueller")) in output_graph
```

**Multi-Standard Output**:
```python
def test_one_person_multiple_standards():
    # Single Person in core ontology
    data_graph = Graph()
    data_graph.add((ex.alice, RDF.type, core.Person))
    data_graph.add((ex.alice, core.PersonGivenName, Literal("Alice")))
    
    # Two alignment sets: MiKaDiv-FM and BZSt Reclaim
    mikadiv_alignment = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    bzst_alignment = load_mappings("alignments/bzst-reclaim-to-core.sssom.tsv")
    
    # Generate MiKaDiv-FM output
    mikadiv_output = transform(data_graph, mikadiv_alignment, "transforms/core-to-mikadiv.sparql")
    assert (_, mikadiv.GivenName, Literal("Alice")) in mikadiv_output
    
    # Generate BZSt Reclaim output (different field name, same data)
    bzst_output = transform(data_graph, bzst_alignment, "transforms/core-to-bzst-reclaim.sparql")
    assert (_, bzst_reclaim.Vorname, Literal("Alice")) in bzst_output
    
    # Key test: Alice's name stored ONCE, used in BOTH outputs
    assert data_graph.value(ex.alice, core.PersonGivenName) == Literal("Alice")
```

### 5. Real-World Complete Filing Tests

**MiKaDiv-FM Meldeart 23 Complete Example** (`tests/alignment/integration/test_mikadiv_complete.py`):
```python
def test_generate_complete_mikadiv_filing():
    # 1. Create core data (Person + FinancialAccount + Organization)
    data_graph = Graph()
    data_graph.add((ex.alice, RDF.type, core.Person))
    data_graph.add((ex.alice, core.PersonGivenName, Literal("Alice")))
    data_graph.add((ex.alice, core.PersonFamilyName, Literal("Mueller")))
    data_graph.add((ex.alice, core.PersonBirthDate, Literal("1985-03-15", datatype=XSD.date)))
    data_graph.add((ex.alice, core.PersonTaxResidence, core.Country_DE))
    
    data_graph.add((ex.account123, RDF.type, core.FinancialAccount))
    data_graph.add((ex.account123, core.AccountNumber, Literal("DE89370400440532013000")))
    data_graph.add((ex.account123, core.AccountBalance, Literal("50000.00", datatype=XSD.decimal)))
    data_graph.add((ex.account123, core.AccountHolder, ex.alice))
    
    # 2. Load SSSOM mappings
    alignment_graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    
    # 3. Run aligned transformation → MiKaDiv-FM XML
    xml_output = generate_mikadiv_xml(data_graph, alignment_graph)
    
    # 4. Validate against official XSD
    schema = ET.XMLSchema(ET.parse("tests/corpus_fixtures/MiKaDiv_FM_Meldeart23_1.02.xsd"))
    doc = ET.fromstring(xml_output)
    assert schema.validate(doc), f"Generated XML invalid: {schema.error_log}"
    
    # 5. Verify specific field mappings
    assert doc.find(".//GivenName").text == "Alice"
    assert doc.find(".//Surname").text == "Mueller"
    assert doc.find(".//AccountNumber").text == "DE89370400440532013000"
```

**Round-Trip Test** (data integrity):
```python
def test_core_to_mikadiv_to_core_preserves_data():
    # Core data → MiKaDiv-FM XML
    original_core_data = create_person_graph(ex.alice, "Alice", "Mueller")
    xml = generate_mikadiv_xml(original_core_data, alignment_graph)
    
    # MiKaDiv-FM XML → back to core (reverse transformation)
    reconstructed_core_data = parse_mikadiv_to_core(xml, alignment_graph)
    
    # Verify data integrity
    assert (ex.alice, core.PersonGivenName, Literal("Alice")) in reconstructed_core_data
    assert (ex.alice, core.PersonFamilyName, Literal("Mueller")) in reconstructed_core_data
```

### 6. Mapping Provenance Tests

**Reference Integration** (`tests/alignment/test_mapping_provenance.py`):
```python
def test_mapping_has_reference():
    # Create SSSOM mapping with provenance
    mapping = create_mapping(
        subject_id=mikadiv.GivenName,
        object_id=core.PersonGivenName,
        author="curator@openfaster.org",
        justification="Manual review of MiKaDiv-FM XSD and BZSt PDF documentation"
    )
    
    # Verify mapping recorded in references_catalog
    catalog = load_catalog()
    mapping_ref = catalog.get_revision(fact_key="mapping-mikadiv-givenname")
    assert mapping_ref is not None
    assert "curator@openfaster.org" in mapping_ref.author
    assert "Manual review" in mapping_ref.comment
```

### 7. CLI Tool Tests

**CLI Validation** (`tests/alignment/test_cli.py`):
```bash
# Validate SSSOM file
python -m alignment.cli validate alignments/mikadiv-to-core.sssom.tsv
# Exit code 0, no output = valid

# Query by subject
python -m alignment.cli query --subject mikadiv:GivenName
# Output:
# Subject: mikadiv:GivenName
# Predicate: skos:exactMatch
# Object: core:PersonGivenName
# Confidence: 0.95

# Query by object
python -m alignment.cli query --object core:PersonGivenName
# Output:
# Mappings to core:PersonGivenName:
#   mikadiv:GivenName (exactMatch, 0.95)
#   bzst_reclaim:Vorname (exactMatch, 0.95)

# Convert TSV → Turtle
python -m alignment.cli convert alignments/mikadiv-to-core.sssom.tsv --format turtle > output.ttl
# Verify output.ttl parses as valid RDF
```

### 8. Webapp Integration Tests

**Alignment Endpoints** (`tests/webapp/test_alignment_api.py`):
```python
def test_list_alignments_endpoint(client):
    response = client.get("/api/alignments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(a["file"] == "mikadiv-to-core.sssom.tsv" for a in data)

def test_get_alignment_endpoint(client):
    response = client.get("/api/alignments/mikadiv-to-core.sssom.tsv")
    assert response.status_code == 200
    mappings = response.json()
    assert len(mappings) >= 50

def test_add_mapping_endpoint(client):
    new_mapping = {
        "subject_id": "mikadiv:NewField",
        "predicate_id": "skos:exactMatch",
        "object_id": "core:NewConcept",
        "confidence": 0.9,
        "author_id": "curator@openfaster.org"
    }
    response = client.post("/api/alignments/mikadiv-to-core.sssom.tsv/mappings", json=new_mapping)
    assert response.status_code == 201
    
    # Verify mapping persisted
    response = client.get("/api/alignments/mikadiv-to-core.sssom.tsv")
    mappings = response.json()
    assert any(m["subject_id"] == "mikadiv:NewField" for m in mappings)
```

### 9. Performance Benchmarks

**Query Performance** (`tests/alignment/benchmarks/`):
```python
def test_find_standard_fields_performance():
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    
    # Query: all fields mapping to a core concept
    start = time.time()
    fields = find_standard_fields(graph, core.PersonGivenName)
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # <100ms for query
    assert len(fields) >= 1

def test_load_mappings_performance():
    start = time.time()
    graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
    elapsed = time.time() - start
    
    assert elapsed < 1.0  # <1s to load 50-100 mappings
```

### 10. Institutional-Ontology Integration Verification

**No Duplication** (`tests/alignment/test_institutional_integration.py`):
```python
def test_core_concepts_not_duplicating_institutional():
    core_graph = load_core_ontology()
    institutional_graph = load_institutional_ontology()  # From external repo
    
    # Verify no exact class URI duplication
    core_classes = set(core_graph.subjects(RDF.type, OWL.Class))
    institutional_classes = set(institutional_graph.subjects(RDF.type, OWL.Class))
    overlap = core_classes & institutional_classes
    
    # Allow intentional imports (e.g., BFO, IAO base classes), but no accidental duplication
    assert len(overlap) == 0 or all(is_imported_class(c) for c in overlap)
```

**ROBOT Tooling Consistency**:
```python
def test_robot_commands_work_on_core_ontology():
    # Verify, merge, reason - same commands as institutional-ontology uses
    subprocess.run(["robot", "verify", "--input", "ontologies/core/persons.ttl"], check=True)
    subprocess.run(["robot", "merge", "--input", "ontologies/core/*.ttl", "--output", "/tmp/merged.ttl"], check=True)
```

### 11. Final Acceptance Test

**Complete Workflow** (single script, must pass end-to-end):
```python
# 1. Load core ontology
core_graph = load_core_ontology()
assert len(core_graph) > 100  # Non-trivial ontology

# 2. Load SSSOM mappings
alignment_graph = load_mappings("alignments/mikadiv-to-core.sssom.tsv")
assert len(list(alignment_graph.subjects(RDF.type, SSSOM.Mapping))) >= 50

# 3. Create core data (Person + Account)
data_graph = create_person_with_account("Alice Mueller")

# 4. Generate MiKaDiv-FM XML via aligned transformation
xml_output = generate_mikadiv_xml(data_graph, alignment_graph)
validate_mikadiv_xml(xml_output)  # Must pass official XSD

# 5. Query alignment layer
assert find_core_concept(alignment_graph, mikadiv.GivenName) == core.PersonGivenName

# 6. CLI tool works
subprocess.run(["python", "-m", "alignment.cli", "validate", "alignments/mikadiv-to-core.sssom.tsv"], check=True)

# 7. Webapp endpoints respond
response = requests.get("http://localhost:8012/api/alignments")
assert response.status_code == 200

print("✅ All alignment layer acceptance tests passed")
```

### 12. Documentation Verification

**Design Spec Completeness**:
- [ ] SSSOM spec review and application documented
- [ ] Core ontology scope justified (MVP concepts, deferred concepts)
- [ ] Mapping predicate usage guide (exactMatch vs. closeMatch vs. relatedMatch)
- [ ] Integration with Task 1, Task 2, institutional-ontology all described
- [ ] Migration path: how existing per-standard data becomes aligned

**Mapping Creation Guide** (`docs/guides/creating-alignments.md`):
- [ ] Tutorial: Create first SSSOM mapping (10 minutes)
- [ ] Reference: All SSSOM required/optional fields explained
- [ ] Examples: 5+ real MiKaDiv-FM → core mappings with rationale
- [ ] Validation checklist: what to verify before committing a mapping
