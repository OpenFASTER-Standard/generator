# Task ID: 7

**Title:** Personal/institutional data storage and consent-sharing abstraction layer

**Status:** deferred

**Dependencies:** 1 ✓, 2, 3, 4

**Priority:** low

**Description:** Design and implement a participant-generic data-spaces architecture where individuals and institutions (banks, regulators) each maintain their own knowledge-graph-based data stores, with granular consent controls for sharing specific data subsets across organizational boundaries, building on Solid (personal data pods) and International Data Spaces / Dataspace Protocol prior art.

**Details:**

## Overview

This task implements the long-term architectural vision where OpenFASTER's annotation and transformation layers (Tasks 1-4) operate over a federated data-spaces model rather than a centralized database. **The key insight: a personal data pod and a bank's multi-tenant internal database are both valid instances of the same abstraction** — each participant (person or institution) has sovereignty over their own data store, and cross-boundary data access happens through explicit consent grants with granular visibility controls.

**Ground Truth Prior Art** (not invented here):

- **Solid (Social Linked Data)**: Tim Berners-Lee/Inrupt's personal data pod architecture — individuals have their own RDF-based data stores (pods) with fine-grained access control (WAC/ACP), applications request specific data with user consent. Provides the individual-sovereignty model and the technical RDF+LDP+access-control stack.

- **International Data Spaces (IDS) / Dataspace Protocol**: European data-spaces initiative (Gaia-X, IDS Association) that generalizes the participant concept beyond individuals to any organization — a data provider and data consumer negotiate usage policies and exchange data via standardized connectors. Treats "participant" as institution-first rather than person-first, which matches this project's multi-stakeholder regulatory context better than Solid's pure personal-pod framing.

- **Gaia-X Federation Services**: Builds on IDS to define cross-border, multi-cloud federated data infrastructure with self-descriptions, trust frameworks, and compliance verification — relevant for cross-jurisdictional regulatory reporting where a German bank, a UK regulator, and an EU data subject all participate on equal architectural footing.

- **SHACL shapes as data contracts**: Task 1's existing SHACL-based annotation model becomes the **schema a participant publishes** to describe what data they hold and under what constraints — other participants request data that conforms to specific shapes, and the consent system enforces which shapes/properties are actually visible to each requestor.

**What This Changes Architecturally:**

1. **Task 1's shapes** (SHACL per-standard annotations) are no longer just internal metadata — they become the **published data contract** a participant exposes to potential consumers. A bank declares "I have data conforming to `mikadiv:BeneficialOwnerShape`"; a regulator requests "give me all instances of `mikadiv:BeneficialOwnerShape` where the beneficial owner's jurisdiction is Germany."

2. **Task 2's transformations** (pure stateless graph-to-graph/graph-to-document mappings) run **across trust boundaries** instead of over a single centralized graph. The transformation engine itself is unchanged (still RML/SPARQL CONSTRUCT), but the input graph is now a **virtual federated graph** assembled from multiple participants' pods/stores based on granted consents.

3. **Task 3's shape-driven UI** (auto-generated forms/tables) becomes the **consent management interface** — a participant sees a shape-based request ("Institution X wants to read properties A, B, C from your beneficial ownership record") and grants/denies it through the same UI machinery already built for data entry.

4. **Task 4's alignment layer** (SSSOM-based mappings between per-standard shapes and shared real-world concepts) is what enables **semantic interoperability across participants** — one participant's internal "customer name" property aligns to another's "beneficial owner name" via the shared mediator concept, so cross-boundary queries work even when internal schemas differ.

5. **A new consent/policy layer** (this task's core contribution) sits between participants and enforces:
   - **What** can be shared (which shapes, which properties, which individual instances).
   - **With whom** (specific participants, or anyone satisfying a trust credential).
   - **Under what conditions** (purpose limitation, time bounds, audit logging).
   - **With what evidence** (cryptographic proof of consent, queryable audit trail).

**No Upfront Topology Imposed:**

Unlike traditional client-server or hub-and-spoke regulatory architectures, this model has **no predetermined roles or central aggregator**. A regulatory submission might involve:
- A beneficial owner (individual) consenting to share their identity data from their personal pod.
- A bank's internal compliance system pulling that consented identity data plus the bank's own transaction records (from the bank's own data store).
- The bank generating a MiKaDiv-FM submission via Task 2's transformation layer (both datasets now visible due to consent).
- The submission being sent to BZSt's regulatory data store, which is itself a participant with its own shapes and access policies.

All four participants — the individual, the bank, BZSt, and potentially a third-party auditor — are **symmetric architectural peers**, differing only in what data they hold and what policies they enforce, not in their role within a predetermined protocol.

## Implementation Approach

### Phase 1: Core Abstractions (Foundation)

#### 1.1 Participant Model

**File: `data_spaces/participant.py`**

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ParticipantIdentity:
    \"\"\"A participant (person or institution) in the data space.
    
    No built-in distinction between individual/organization — that's a
    policy-level concern (what shapes they publish, what credentials
    they hold), not an architectural one.
    \"\"\"
    participant_id: str  # globally unique (DID, URI, etc.)
    display_name: str
    participant_type: str  # "individual" | "institution" | "regulator" (informational only)

class DataStore(Protocol):
    \"\"\"The storage abstraction every participant implements.
    
    Could be backed by:
    - A Solid pod (individual, LDP+Turtle storage)
    - A PostgreSQL database (bank, multi-tenant via row-level security)
    - An Oxigraph RDF store (any participant wanting native graph storage)
    - A read-only SPARQL endpoint (a regulator exposing published data)
    
    The only contract: can answer SPARQL queries over shapes this
    participant has declared, subject to the caller's access grants.
    \"\"\"
    def query_shapes(self, sparql: str, requesting_participant: ParticipantIdentity) -> list[dict]:
        \"\"\"Execute a SPARQL query, enforcing consent policies.
        
        Returns only results the requesting_participant is allowed to see
        based on active consent grants. Empty list if no consent or no matches.
        \"\"\"
        ...
    
    def list_published_shapes(self) -> list[str]:
        \"\"\"Shape URIs this participant declares they have data for.
        
        Analogous to a database's INFORMATION_SCHEMA or an API's
        OpenAPI spec — the participant's public data contract.
        \"\"\"
        ...
```

**Why this abstraction:** A personal Solid pod and a bank's internal Postgres are radically different implementations, but both can satisfy the `DataStore` protocol — the pod via native SPARQL over RDF, the bank via a SPARQL-to-SQL adapter (Ontop, Morph-RDB prior art). The consent layer and transformation engine (Tasks 2/3) only ever talk to this interface, never to a specific backend.

#### 1.2 Consent Grant Model

**File: `data_spaces/consent.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class ConsentGrant:
    \"\"\"A participant's explicit authorization for another to access specific data.
    
    Granularity matches Task 1's shape model: consent is per-shape +
    per-property, not per-file or per-table (too coarse) and not
    per-triple (too fine, unmanageable at scale).
    \"\"\"
    grant_id: str
    grantor: ParticipantIdentity  # who is sharing their data
    grantee: ParticipantIdentity  # who is receiving access
    
    # What data is covered
    shape_uri: str  # from Task 1's SHACL shapes (e.g. "mikadiv:BeneficialOwnerShape")
    property_uris: list[str]  # specific properties within that shape ([] = all properties)
    instance_filter: Optional[str]  # SPARQL WHERE clause to limit instances (e.g. "?instance mikadiv:jurisdiction 'DE'")
    
    # Constraints
    purpose: str  # why the grantee needs this ("regulatory_reporting", "audit", "analytics")
    valid_from: datetime
    valid_until: Optional[datetime]  # None = indefinite
    
    # Provenance
    granted_at: datetime
    evidence_uri: Optional[str]  # cryptographic proof (signed consent record, blockchain anchor, etc.)
    
    # Audit
    access_count: int = 0  # incremented on each query
    last_accessed: Optional[datetime] = None

def evaluate_consent(
    store_owner: ParticipantIdentity,
    requesting_participant: ParticipantIdentity,
    requested_shape: str,
    requested_properties: list[str],
    active_grants: list[ConsentGrant]
) -> bool:
    \"\"\"Check if a query is permitted under active consent grants.
    
    Returns True only if there exists a grant covering all requested
    properties for the requested shape, valid now, matching purpose, etc.
    \"\"\"
    # Implementation: filter grants by grantor=store_owner,
    # grantee=requesting_participant, shape_uri=requested_shape,
    # valid time window, then check property_uris coverage.
    ...
```

**Why this model:** Matches real-world regulatory consent requirements (GDPR Article 7 — consent must be specific, informed, unambiguous, with clear purpose) while being technically enforceable at query time. A participant can revoke a grant (delete it / set `valid_until` to now), and subsequent queries immediately fail — no stale cached data, no "we'll propagate the revocation eventually."

#### 1.3 Federated Query Engine

**File: `data_spaces/federation.py`**

```python
from typing import Iterator

@dataclass
class QueryPlan:
    \"\"\"Decomposition of a cross-participant query into per-store subqueries.
    
    A SPARQL query like 'give me all beneficial owners whose bank
    reported transactions > 10M' might require data from:
    - The individual's personal pod (identity properties)
    - The bank's internal store (transaction records)
    - A regulatory reference dataset (sanctions lists)
    
    The federation engine rewrites the query into one subquery per
    participant, executes each (subject to consent), and joins results.
    \"\"\"
    subqueries: list[tuple[ParticipantIdentity, str]]  # (participant, SPARQL)
    join_strategy: str  # "hash_join" | "nested_loop" | "bind_join" (FedX, ANAPSID prior art)

def federated_query(
    query: str,
    initiating_participant: ParticipantIdentity,
    participant_stores: dict[ParticipantIdentity, DataStore]
) -> Iterator[dict]:
    \"\"\"Execute a SPARQL query across multiple participants' stores.
    
    Prior art:
    - FedX (federated SPARQL query engine): decomposes a query via
      source selection (which endpoint has which predicates), executes
      subqueries in parallel, joins via bind/hash strategies.
    - ANAPSID (adaptive query processing): handles partial results and
      failures gracefully, important when a participant's store is
      temporarily unreachable or a consent is revoked mid-query.
    
    Returns only results the initiating_participant is allowed to see —
    if a subquery to participant X fails consent checks, that branch
    returns empty, not an error (graceful degradation).
    \"\"\"
    plan = _build_query_plan(query, participant_stores)
    for subquery_participant, subquery_sparql in plan.subqueries:
        store = participant_stores[subquery_participant]
        # This call enforces consent internally (see DataStore.query_shapes)
        partial_results = store.query_shapes(subquery_sparql, initiating_participant)
        yield from partial_results
    # Join partial results per plan.join_strategy (omitted for brevity)
```

**Why federated query:** Task 2's transformation layer already assumes a single input graph to transform. With this federation layer, that graph is **virtually unified** from N participants' stores at query time, so transformations need no rewrite — they just work over a larger (but consent-filtered) view.

### Phase 2: Integration with Existing Layers

#### 2.1 Shape Publication (extends Task 1)

**File: `data_spaces/shape_catalog.py`**

Every participant maintains a **public shape catalog** — the list of SHACL shapes they have data for, plus the shapes' own definitions. This is analogous to publishing an OpenAPI spec for a REST API: it tells potential data consumers what to ask for.

```python
@dataclass
class PublishedShape:
    shape_uri: str
    shape_definition: str  # Turtle/JSON-LD SHACL shape
    instance_count: Optional[int]  # None if participant doesn't want to reveal volume
    sample_available: bool  # whether the participant offers a public sample (e.g. for testing)

def publish_shapes(participant: ParticipantIdentity, shapes: list[PublishedShape]) -> None:
    \"\"\"Register this participant's data contract in the data space.
    
    Stored in a discoverable location (DNS TXT record, a federated
    catalog service, a blockchain-based registry, etc.) so other
    participants can find "who has beneficial ownership data" without
    contacting every participant one by one.
    \"\"\"
    ...
```

**Consequence for Task 1:** Shapes are no longer just internal schema — they're externalized, versioned, and discoverable. A shape change (adding a property, tightening a constraint) is a **breaking change** to the participant's published contract, requiring version negotiation (Dataspace Protocol's contract negotiation prior art).

#### 2.2 Consent-Aware Transformation (extends Task 2)

**File: `data_spaces/transformation.py`**

Task 2's RML/SPARQL CONSTRUCT transformations now run over a **federated graph** instead of a single local one. The transformation itself is unchanged; only the input graph's source changes.

```python
def transform_with_federation(
    transformation_def: str,  # RML or SPARQL CONSTRUCT from Task 2
    initiating_participant: ParticipantIdentity,
    participant_stores: dict[ParticipantIdentity, DataStore]
) -> str:  # output document (XML, JSON, RDF, etc.)
    \"\"\"Run a Task 2 transformation over federated data.
    
    Example: a bank generating a MiKaDiv-FM submission needs:
    - Beneficial owner identity (from the individual's Solid pod)
    - Transaction records (from the bank's own internal DB)
    - Regulatory codes (from BZSt's public reference dataset)
    
    The RML mapping references all three via shape URIs; the federation
    layer pulls data from three different DataStores (subject to
    consent), assembles a virtual RDF graph, then runs the mapping.
    \"\"\"
    virtual_graph = _assemble_federated_graph(transformation_def, initiating_participant, participant_stores)
    return apply_transformation(transformation_def, virtual_graph)  # Task 2's existing logic
```

**Why this works:** Task 2's transformations are already stateless, pure functions from one graph to another. The federated graph is just another graph (semantically) — the fact that it's assembled from multiple sources at query time is transparent to the transformation engine.

#### 2.3 Consent UI Generation (extends Task 3)

**File: `data_spaces/consent_ui.py`**

Task 3's shape-driven UI generator already knows how to render a form from a SHACL shape. For consent, the same machinery generates a **consent request review screen**: "Institution X wants to read properties A, B, C from your `mikadiv:BeneficialOwnerShape` instances — approve or deny?"

```python
def render_consent_request(
    request: ConsentRequest,
    target_shape: str,  # SHACL shape URI
    target_properties: list[str]
) -> str:  # HTML form or React component
    \"\"\"Generate a consent approval UI using Task 3's shape renderer.
    
    Shows:
    - Who is requesting (institution name, trust credential)
    - What data (shape + property labels from DASH UI hints)
    - Why (stated purpose)
    - Sample data (if available, what they would actually see)
    - Constraints (time limit, revocability, audit logging)
    
    Returns a form with Approve/Deny buttons; on submit, creates a
    ConsentGrant or logs a denial.
    \"\"\"
    shape_def = load_shape_definition(target_shape)  # from Task 1's registry
    return render_shape_form(shape_def, mode="consent_review", properties=target_properties)
```

**Why reuse Task 3:** A consent decision is fundamentally a data-entry task — the user is providing structured input (grant/deny, purpose, time bounds). Task 3's shape-driven forms already handle arbitrary structured input; consent is just another application of the same abstraction.

### Phase 3: Trust and Compliance

#### 3.1 Verifiable Credentials for Participants

**File: `data_spaces/credentials.py`**

A participant's identity (`ParticipantIdentity.participant_id`) is not self-asserted — it's backed by a **verifiable credential** (W3C VC standard, already used in Gaia-X and IDS). A regulator issues a credential to a bank saying "this institution is licensed to hold customer data"; a bank only accepts consent requests from participants holding such a credential.

```python
@dataclass
class VerifiableCredential:
    credential_id: str
    issuer: ParticipantIdentity  # who issued this credential (e.g. a regulatory authority)
    subject: ParticipantIdentity  # who holds it (e.g. a bank)
    claims: dict[str, Any]  # {"license_type": "credit_institution", "jurisdiction": "DE", ...}
    issued_at: datetime
    expires_at: Optional[datetime]
    proof: str  # cryptographic signature (JWT, Linked Data Proof, etc.)

def verify_credential(credential: VerifiableCredential, trusted_issuers: list[ParticipantIdentity]) -> bool:
    \"\"\"Check if a credential is valid and from a trusted issuer.\"\"\"
    # Verify cryptographic signature, check expiration, confirm issuer is in trusted list
    ...

def enforce_credential_policy(
    consent_request: ConsentRequest,
    requester_credentials: list[VerifiableCredential],
    policy: dict
) -> bool:
    \"\"\"Evaluate if a consent request meets the data owner's credential policy.
    
    Example policy: "Only licensed credit institutions in Germany with
    an active BaFin registration can request transaction data."
    \"\"\"
    ...
```

**Why verifiable credentials:** Without them, any attacker could claim to be "BZSt" or "Deutsche Bank" and request consent — the data owner has no way to verify the claim. VCs provide cryptographic proof of identity and authority, bootstrapping trust in a fully decentralized system.

#### 3.2 Audit Trail

**File: `data_spaces/audit.py`**

Every consent grant, every query, every access is **immutably logged** (append-only ledger, local database, or distributed ledger like Hyperledger Fabric / IOTA). Required for GDPR Article 30 (records of processing activities) and regulatory accountability.

```python
@dataclass
class AuditEntry:
    entry_id: str
    timestamp: datetime
    actor: ParticipantIdentity  # who performed the action
    action: str  # "grant_consent" | "revoke_consent" | "query_data" | "deny_request"
    subject: ParticipantIdentity  # whose data was involved
    details: dict  # shape, properties, query text, consent_id, etc.
    evidence_hash: str  # cryptographic hash of the full event payload

def append_audit_entry(entry: AuditEntry) -> None:
    \"\"\"Write an audit entry to the immutable log.\"\"\"
    ...

def query_audit_trail(
    participant: ParticipantIdentity,
    action_filter: Optional[str] = None,
    time_range: Optional[tuple[datetime, datetime]] = None
) -> list[AuditEntry]:
    \"\"\"Retrieve audit entries for a participant's data.
    
    A data owner can see "who accessed my data and when"; a regulator
    (with appropriate consent/authority) can audit an institution's
    compliance with consent policies.
    \"\"\"
    ...
```

**Why immutable audit:** Trust in a decentralized system requires transparency and non-repudiation. An institution can't claim "we never accessed that data" when the append-only log proves otherwise; a data owner can prove "I revoked consent on date X" if a downstream dispute arises.

## Non-Goals (Explicit Deferrals)

- **Not building a new Solid pod implementation.** Reuse Inrupt's existing Solid servers (Community Solid Server, ESS) for individual participants who want personal pods. This task focuses on the **abstraction layer** that treats a Solid pod and a bank's internal DB uniformly, not reimplementing Solid itself.

- **Not building a blockchain.** Audit trails and consent evidence can be stored in a distributed ledger if a participant chooses (IOTA, Hyperledger), but that's a backend choice, not architecturally required. A simple append-only PostgreSQL table with cryptographic hashes is a valid implementation.

- **No built-in regulatory schema.** This task provides the infrastructure for consent-based data sharing; **what** data to share (the MiKaDiv-FM shapes, the BIRD taxonomy, etc.) comes from Tasks 1-4, not this task. The data-spaces layer is deliberately domain-agnostic.

- **No upfront global participant registry.** Participants discover each other through domain-specific mechanisms (a bank's customer onboarding flow, a regulatory filing directory, peer recommendations) — not a single centralized "phone book of all data-space participants." The architecture supports federation, not forced centralization.

## Dependencies

This task depends on:

- **Task 1** (SHACL shape model): Shapes become the published data contracts participants expose. Without Task 1's shape machinery, there's no semantic basis for "request access to beneficial ownership data" — only unstructured file/table requests.

- **Task 2** (transformation layer): Federating transformations across participants requires the transformation engine itself to be pure and stateless (already true in Task 2's design). If Task 2 were stateful or tightly coupled to a specific database schema, federation would require a full rewrite.

- **Task 3** (shape-driven UI): Consent request/approval UIs reuse Task 3's form generation. Without it, every participant would need custom consent UI code instead of auto-generating it from shapes.

- **Task 4** (alignment layer): Cross-participant semantic interoperability (a bank's internal "customer name" aligning to a regulator's "beneficial owner name") requires Task 4's SSSOM-based mappings. Without alignment, each participant is a semantic island — queries can't span them.

Tasks 5 (stateful process) and 6 (collaborative annotation) are **not** dependencies — they're orthogonal features. A data-spaces architecture works without multi-step workflows (Task 5) or public/private visibility scopes (Task 6); conversely, those features work without federation (they just operate over centralized storage instead).

**Test Strategy:**

## Verification Strategy

### 1. Design Approval Gate

**Pre-Implementation Checkpoint**:
- [ ] Design spec in `docs/specs/data-spaces-architecture-design.md` reviewed and approved by product owner
- [ ] Stakeholder confirmation: Solid + IDS/Dataspace Protocol alignment matches intended regulatory multi-stakeholder model
- [ ] Technical validation: confirmed that federation doesn't break Tasks 1-4's assumptions (all are designed to be stateless/composable, but verify explicitly)
- [ ] Scope confirmation: personal pod + bank internal DB as the two reference implementations is sufficient initial coverage (no need for blockchain/IPFS/etc. backends upfront)

Do NOT write code until this gate is passed — scope clarity is mandatory given this task's long-term architectural impact.

---

### 2. Core Abstraction Tests (`tests/data_spaces/`)

#### 2.1 Participant Model (`test_participant.py`)

**ParticipantIdentity Creation**:
```python
def test_participant_identity_valid():
    participant = ParticipantIdentity(
        participant_id="did:example:123",
        display_name="Alice (Individual)",
        participant_type="individual"
    )
    assert participant.participant_id == "did:example:123"

def test_participant_identity_institution():
    participant = ParticipantIdentity(
        participant_id="urn:bank:deutsche-bank",
        display_name="Deutsche Bank AG",
        participant_type="institution"
    )
    assert participant.participant_type == "institution"
```

**DataStore Protocol Compliance** (test both in-memory mock and a real implementation):
```python
def test_datastore_protocol_query_shapes():
    \"\"\"A DataStore implementation must enforce consent at query time.\"\"\"
    store = InMemoryDataStore(owner=alice_participant)
    # No consent grant exists
    results = store.query_shapes("SELECT ?s WHERE { ?s a mikadiv:BeneficialOwner }", requesting_participant=bob_participant)
    assert results == []  # access denied, gracefully returns empty
    
    # Grant consent
    store.add_consent_grant(ConsentGrant(
        grant_id="grant-1",
        grantor=alice_participant,
        grantee=bob_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=[],  # all properties
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    results = store.query_shapes("SELECT ?s WHERE { ?s a mikadiv:BeneficialOwner }", requesting_participant=bob_participant)
    assert len(results) > 0  # access now permitted

def test_datastore_list_published_shapes():
    store = InMemoryDataStore(owner=bank_participant)
    shapes = store.list_published_shapes()
    assert "mikadiv:BeneficialOwnerShape" in shapes
    assert "mikadiv:TransactionShape" in shapes
```

#### 2.2 Consent Model (`test_consent.py`)

**ConsentGrant Validation**:
```python
def test_consent_grant_time_bounds():
    grant = ConsentGrant(
        grant_id="grant-time-test",
        grantor=alice_participant,
        grantee=bob_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=["mikadiv:givenName", "mikadiv:familyName"],
        instance_filter=None,
        purpose="audit",
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_until=datetime(2026, 12, 31, tzinfo=timezone.utc),
        granted_at=datetime(2025, 12, 1, tzinfo=timezone.utc)
    )
    
    # Before valid_from
    assert not is_grant_active(grant, check_time=datetime(2025, 6, 1, tzinfo=timezone.utc))
    # During validity
    assert is_grant_active(grant, check_time=datetime(2026, 6, 1, tzinfo=timezone.utc))
    # After valid_until
    assert not is_grant_active(grant, check_time=datetime(2027, 1, 1, tzinfo=timezone.utc))

def test_consent_property_coverage():
    grant = ConsentGrant(
        grant_id="grant-prop-test",
        grantor=alice_participant,
        grantee=bob_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=["mikadiv:givenName"],  # only first name, not family name
        instance_filter=None,
        purpose="analytics",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    )
    
    # Request for granted property
    assert evaluate_consent(alice_participant, bob_participant, "mikadiv:BeneficialOwnerShape", ["mikadiv:givenName"], [grant])
    # Request for non-granted property
    assert not evaluate_consent(alice_participant, bob_participant, "mikadiv:BeneficialOwnerShape", ["mikadiv:familyName"], [grant])
    # Request for both (partial coverage = denial)
    assert not evaluate_consent(alice_participant, bob_participant, "mikadiv:BeneficialOwnerShape", ["mikadiv:givenName", "mikadiv:familyName"], [grant])
```

**Instance Filter Enforcement**:
```python
def test_consent_instance_filter():
    grant = ConsentGrant(
        grant_id="grant-filter-test",
        grantor=bank_participant,
        grantee=regulator_participant,
        shape_uri="mikadiv:TransactionShape",
        property_uris=[],
        instance_filter="?instance mikadiv:amount ?amt . FILTER(?amt > 10000)",  # only large transactions
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    )
    
    store = InMemoryDataStore(owner=bank_participant)
    store.add_consent_grant(grant)
    
    # Query for all transactions
    all_results = store.query_shapes("SELECT ?t WHERE { ?t a mikadiv:Transaction }", requesting_participant=regulator_participant)
    # Should only return transactions matching the filter
    for result in all_results:
        amount = result.get("amount")
        assert amount > 10000
```

#### 2.3 Federated Query (`test_federation.py`)

**Query Plan Decomposition**:
```python
def test_query_plan_multi_participant():
    # Mock stores for three participants
    stores = {
        alice_participant: InMemoryDataStore(owner=alice_participant),
        bank_participant: InMemoryDataStore(owner=bank_participant),
        regulator_participant: InMemoryDataStore(owner=regulator_participant)
    }
    
    # Federated query spanning two participants' data
    query = \"\"\"
    SELECT ?owner ?transaction WHERE {
      ?owner a mikadiv:BeneficialOwner .
      ?transaction mikadiv:beneficialOwner ?owner ;
                   mikadiv:amount ?amt .
      FILTER(?amt > 50000)
    }
    \"\"\"
    
    plan = build_query_plan(query, stores)
    # Should decompose into subqueries to alice's store (beneficial owner data)
    # and bank's store (transaction data), with a join
    assert len(plan.subqueries) >= 2
    participants_in_plan = {p for p, _ in plan.subqueries}
    assert alice_participant in participants_in_plan
    assert bank_participant in participants_in_plan

def test_federated_query_consent_enforcement():
    # Alice has beneficial owner data, Bank has transactions
    alice_store = InMemoryDataStore(owner=alice_participant)
    bank_store = InMemoryDataStore(owner=bank_participant)
    
    # Alice grants consent to Bank for beneficial owner data
    alice_store.add_consent_grant(ConsentGrant(
        grant_id="alice-to-bank",
        grantor=alice_participant,
        grantee=bank_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=[],
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    
    stores = {alice_participant: alice_store, bank_participant: bank_store}
    
    # Bank queries federated data (needs Alice's consent to succeed)
    results = list(federated_query(
        "SELECT ?owner WHERE { ?owner a mikadiv:BeneficialOwner }",
        initiating_participant=bank_participant,
        participant_stores=stores
    ))
    assert len(results) > 0  # consent granted, query succeeds
    
    # Revoke consent
    alice_store.revoke_consent("alice-to-bank")
    
    # Same query now returns empty
    results = list(federated_query(
        "SELECT ?owner WHERE { ?owner a mikadiv:BeneficialOwner }",
        initiating_participant=bank_participant,
        participant_stores=stores
    ))
    assert len(results) == 0  # consent revoked, access denied
```

**Graceful Degradation** (partial failure handling):
```python
def test_federated_query_partial_consent():
    # Three participants: Alice, Bob (both individuals), and Bank
    # Bank queries for all beneficial owners; Alice grants consent, Bob does not
    alice_store = InMemoryDataStore(owner=alice_participant)
    bob_store = InMemoryDataStore(owner=bob_participant)
    bank_store = InMemoryDataStore(owner=bank_participant)
    
    alice_store.add_consent_grant(ConsentGrant(
        grant_id="alice-to-bank",
        grantor=alice_participant,
        grantee=bank_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=[],
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    # Bob grants no consent
    
    stores = {alice_participant: alice_store, bob_participant: bob_store, bank_participant: bank_store}
    
    results = list(federated_query(
        "SELECT ?owner WHERE { ?owner a mikadiv:BeneficialOwner }",
        initiating_participant=bank_participant,
        participant_stores=stores
    ))
    # Should return Alice's data (consent granted) but not Bob's (no consent)
    # Critically: does NOT raise an error, just omits Bob's results
    owner_ids = {r["owner"] for r in results}
    assert alice_participant.participant_id in str(owner_ids)
    assert bob_participant.participant_id not in str(owner_ids)
```

---

### 3. Integration Tests (Tasks 1-4)

#### 3.1 Shape Publication Integration (`test_shape_catalog_integration.py`)

**Task 1 SHACL Shapes as Published Contracts**:
```python
def test_publish_shacl_shape():
    # Task 1's existing shape registry
    from shape_registry import get_shape_definition  # hypothetical Task 1 API
    
    shape_def = get_shape_definition("mikadiv:BeneficialOwnerShape")
    published = PublishedShape(
        shape_uri="mikadiv:BeneficialOwnerShape",
        shape_definition=shape_def,
        instance_count=42,
        sample_available=True
    )
    
    publish_shapes(bank_participant, [published])
    
    # Another participant can discover this
    catalog = query_shape_catalog(search_term="beneficial owner")
    assert any(s.shape_uri == "mikadiv:BeneficialOwnerShape" for s in catalog)
```

#### 3.2 Consent-Aware Transformation Integration (`test_transformation_integration.py`)

**Task 2 Transformations Over Federated Data**:
```python
def test_rml_transformation_with_federation():
    # RML mapping that references data from two participants
    rml_mapping = \"\"\"
    @prefix rml: <http://semweb.mmlab.be/ns/rml#> .
    @prefix mikadiv: <http://openfaster.org/mikadiv#> .
    
    <#BeneficialOwnerMapping> a rml:TriplesMap ;
      rml:logicalSource [
        a rml:LogicalSource ;
        # References Alice's pod (via federation)
        rml:source "sparql://alice-pod/beneficial-owners" ;
      ] ;
      # ... rest of mapping
    \"\"\"
    
    alice_store = InMemoryDataStore(owner=alice_participant)
    bank_store = InMemoryDataStore(owner=bank_participant)
    
    # Grant consent
    alice_store.add_consent_grant(ConsentGrant(
        grant_id="alice-to-bank-transform",
        grantor=alice_participant,
        grantee=bank_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=[],
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    
    stores = {alice_participant: alice_store, bank_participant: bank_store}
    
    # Bank runs transformation (from Task 2)
    output_xml = transform_with_federation(rml_mapping, bank_participant, stores)
    
    # Output should contain Alice's data (consent granted)
    assert "<BeneficialOwner>" in output_xml
    assert "Alice" in output_xml  # her actual name from the pod

def test_transformation_fails_gracefully_without_consent():
    # Same RML mapping, no consent grant
    alice_store = InMemoryDataStore(owner=alice_participant)
    bank_store = InMemoryDataStore(owner=bank_participant)
    stores = {alice_participant: alice_store, bank_participant: bank_store}
    
    rml_mapping = \"\"\"...(same as above)...\"\"\"
    
    output_xml = transform_with_federation(rml_mapping, bank_participant, stores)
    
    # Output is valid XML but missing Alice's data (no consent = empty result)
    assert "<BeneficialOwner>" not in output_xml
```

#### 3.3 Consent UI Integration (`test_consent_ui_integration.py`)

**Task 3 Shape-Driven Consent Forms**:
```python
def test_render_consent_request_ui():
    request = ConsentRequest(
        request_id="req-123",
        requesting_participant=bank_participant,
        target_participant=alice_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=["mikadiv:givenName", "mikadiv:familyName", "mikadiv:dateOfBirth"],
        purpose="regulatory_reporting",
        requested_duration_days=365
    )
    
    # Task 3's shape renderer generates a consent review UI
    html = render_consent_request(request, "mikadiv:BeneficialOwnerShape", request.property_uris)
    
    # Check that the UI shows human-readable labels (from DASH hints in the shape)
    assert "Given Name" in html or "First Name" in html  # DASH label
    assert "Family Name" in html or "Last Name" in html
    assert "Date of Birth" in html
    
    # Check that purpose and requester are visible
    assert "regulatory_reporting" in html or "Regulatory Reporting" in html
    assert bank_participant.display_name in html

def test_consent_approval_creates_grant():
    request = ConsentRequest(...)  # same as above
    
    # User clicks "Approve" (simulated form submission)
    approval_data = {
        "request_id": "req-123",
        "action": "approve",
        "custom_duration_days": 90  # user overrides the requested 365 days
    }
    
    grant = process_consent_approval(alice_participant, approval_data)
    
    assert grant.grantor == alice_participant
    assert grant.grantee == bank_participant
    assert grant.shape_uri == "mikadiv:BeneficialOwnerShape"
    assert (grant.valid_until - grant.valid_from).days == 90
```

#### 3.4 Alignment Layer Integration (`test_alignment_integration.py`)

**Task 4 SSSOM Mappings Across Participants**:
```python
def test_cross_participant_semantic_alignment():
    # Alice's internal property: "first_name"
    # Bank's internal property: "customer_given_name"
    # Both align to the same mediator concept via Task 4's SSSOM mappings
    
    # SSSOM mapping (from Task 4):
    # alice:first_name -> mediator:givenName (exact match)
    # bank:customer_given_name -> mediator:givenName (exact match)
    
    alice_store = InMemoryDataStore(owner=alice_participant)
    bank_store = InMemoryDataStore(owner=bank_participant)
    
    # Alice grants consent using her internal property name
    alice_store.add_consent_grant(ConsentGrant(
        grant_id="alice-to-bank-aligned",
        grantor=alice_participant,
        grantee=bank_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=["alice:first_name"],  # her internal name
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    
    stores = {alice_participant: alice_store, bank_participant: bank_store}
    
    # Bank queries using their internal property name
    query = "SELECT ?name WHERE { ?owner bank:customer_given_name ?name }"
    
    # Federation layer uses Task 4's alignment to rewrite the query:
    # bank:customer_given_name -> mediator:givenName -> alice:first_name
    results = list(federated_query(query, bank_participant, stores))
    
    # Bank gets Alice's data even though property names don't literally match
    assert len(results) > 0
    assert results[0]["name"] == "Alice"
```

---

### 4. Compliance and Trust Tests

#### 4.1 Verifiable Credentials (`test_credentials.py`)

**Credential Verification**:
```python
def test_verify_valid_credential():
    regulator = ParticipantIdentity(participant_id="did:regulator:bafin", ...)
    bank = ParticipantIdentity(participant_id="did:bank:deutsche-bank", ...)
    
    credential = VerifiableCredential(
        credential_id="cred-bank-license",
        issuer=regulator,
        subject=bank,
        claims={"license_type": "credit_institution", "jurisdiction": "DE"},
        issued_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        proof="<cryptographic-signature>"
    )
    
    # Verify the credential (signature valid, not expired, issuer trusted)
    assert verify_credential(credential, trusted_issuers=[regulator])

def test_reject_expired_credential():
    credential = VerifiableCredential(
        credential_id="cred-expired",
        issuer=regulator,
        subject=bank,
        claims={...},
        issued_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2025, 1, 1, tzinfo=timezone.utc),  # expired
        proof="<signature>"
    )
    
    # Verification fails due to expiration
    assert not verify_credential(credential, trusted_issuers=[regulator], check_time=datetime(2026, 1, 1, tzinfo=timezone.utc))

def test_credential_policy_enforcement():
    # Alice's policy: only licensed banks in Germany can request transaction data
    policy = {
        "required_claims": {
            "license_type": "credit_institution",
            "jurisdiction": "DE"
        }
    }
    
    valid_credential = VerifiableCredential(
        issuer=bafin_regulator,
        subject=deutsche_bank,
        claims={"license_type": "credit_institution", "jurisdiction": "DE"},
        ...
    )
    
    invalid_credential = VerifiableCredential(
        issuer=fca_regulator,
        subject=uk_bank,
        claims={"license_type": "credit_institution", "jurisdiction": "UK"},  # wrong jurisdiction
        ...
    )
    
    request_valid = ConsentRequest(requesting_participant=deutsche_bank, ...)
    request_invalid = ConsentRequest(requesting_participant=uk_bank, ...)
    
    assert enforce_credential_policy(request_valid, [valid_credential], policy)
    assert not enforce_credential_policy(request_invalid, [invalid_credential], policy)
```

#### 4.2 Audit Trail (`test_audit.py`)

**Audit Entry Creation**:
```python
def test_append_audit_entry():
    entry = AuditEntry(
        entry_id="audit-1",
        timestamp=now(),
        actor=bank_participant,
        action="query_data",
        subject=alice_participant,
        details={"shape": "mikadiv:BeneficialOwnerShape", "query": "SELECT ?s WHERE ..."},
        evidence_hash=hashlib.sha256(b"...full-event-payload...").hexdigest()
    )
    
    append_audit_entry(entry)
    
    # Entry is immutable — attempting to modify it fails
    with pytest.raises(ImmutableAuditLogError):
        modify_audit_entry(entry.entry_id, new_action="something_else")

def test_query_audit_trail_for_data_owner():
    # Alice queries her own audit trail
    entries = query_audit_trail(alice_participant, action_filter="query_data", time_range=(datetime(2026, 1, 1), datetime(2026, 12, 31)))
    
    # Should see all queries against her data
    assert len(entries) > 0
    for entry in entries:
        assert entry.subject == alice_participant
        assert entry.action == "query_data"

def test_audit_trail_consent_lifecycle():
    # Full lifecycle: grant consent, query data, revoke consent
    # Each step must be audited
    
    grant_entry = AuditEntry(action="grant_consent", actor=alice_participant, subject=alice_participant, details={"grantee": bank_participant.participant_id})
    append_audit_entry(grant_entry)
    
    query_entry = AuditEntry(action="query_data", actor=bank_participant, subject=alice_participant, details={"consent_id": "grant-123"})
    append_audit_entry(query_entry)
    
    revoke_entry = AuditEntry(action="revoke_consent", actor=alice_participant, subject=alice_participant, details={"consent_id": "grant-123"})
    append_audit_entry(revoke_entry)
    
    # Retrieve full history
    history = query_audit_trail(alice_participant)
    actions = [e.action for e in history]
    assert actions == ["grant_consent", "query_data", "revoke_consent"]
```

---

### 5. End-to-End Scenario Tests

**Complete Regulatory Reporting Flow**:
```python
def test_e2e_regulatory_reporting_with_consent():
    # Scenario: Bank generates a MiKaDiv-FM submission, needing data from:
    # 1. Alice (beneficial owner, personal Solid pod)
    # 2. Bank's own internal DB (transaction records)
    # 3. BZSt's public reference dataset (regulatory codes)
    
    alice_pod = SolidPodDataStore(owner=alice_participant, pod_url="https://alice.solidcommunity.net/")
    bank_db = PostgresDataStore(owner=bank_participant, connection_string="postgresql://...")
    bzst_endpoint = SPARQLEndpointDataStore(owner=bzst_participant, endpoint_url="https://bzst.de/sparql")
    
    stores = {alice_participant: alice_pod, bank_participant: bank_db, bzst_participant: bzst_endpoint}
    
    # 1. Alice grants consent to Bank
    alice_pod.add_consent_grant(ConsentGrant(
        grant_id="alice-to-bank-reporting",
        grantor=alice_participant,
        grantee=bank_participant,
        shape_uri="mikadiv:BeneficialOwnerShape",
        property_uris=[],
        instance_filter=None,
        purpose="regulatory_reporting",
        valid_from=now(),
        valid_until=None,
        granted_at=now()
    ))
    
    # 2. Bank requests transformation (Task 2 RML mapping)
    rml_mapping = load_rml_mapping("mikadiv_fm_submission.rml")
    
    # 3. Transformation engine federates across all three stores
    submission_xml = transform_with_federation(rml_mapping, bank_participant, stores)
    
    # 4. Verify output contains data from all sources
    assert "<BeneficialOwner>" in submission_xml  # from Alice's pod
    assert "<Transaction>" in submission_xml  # from Bank's DB
    assert "<RegulatoryCode>" in submission_xml  # from BZSt's endpoint
    
    # 5. Check audit trail
    alice_audit = query_audit_trail(alice_participant, action_filter="query_data")
    assert any(e.actor == bank_participant and "mikadiv:BeneficialOwnerShape" in str(e.details) for e in alice_audit)

def test_e2e_consent_revocation_mid_process():
    # Scenario: Alice grants consent, Bank starts a long-running transformation,
    # Alice revokes consent mid-way — subsequent queries fail gracefully
    
    alice_pod = SolidPodDataStore(owner=alice_participant)
    bank_db = PostgresDataStore(owner=bank_participant)
    stores = {alice_participant: alice_pod, bank_participant: bank_db}
    
    # Grant consent
    grant_id = alice_pod.add_consent_grant(ConsentGrant(...))
    
    # Bank starts transformation
    rml_mapping = load_rml_mapping("mikadiv_fm_submission.rml")
    
    # Simulate revocation mid-process (in a real system, this might happen in another thread/process)
    alice_pod.revoke_consent(grant_id)
    
    # Transformation continues but gets empty results from Alice's pod
    submission_xml = transform_with_federation(rml_mapping, bank_participant, stores)
    
    # Output is valid but missing Alice's data (graceful degradation, not a crash)
    assert "<BeneficialOwner>" not in submission_xml
    assert "<Transaction>" in submission_xml  # Bank's own data still present
```

---

### 6. Performance and Scalability Tests

**Federated Query Performance** (verify it doesn't degrade linearly with participant count):
```python
def test_federated_query_performance_100_participants():
    # Simulate 100 participants, each with a small dataset
    stores = {ParticipantIdentity(participant_id=f"did:test:{i}", ...): InMemoryDataStore(...) for i in range(100)}
    
    # Query that could theoretically hit all 100 stores (but should optimize to only relevant ones)
    query = "SELECT ?owner WHERE { ?owner a mikadiv:BeneficialOwner }"
    
    start = time.time()
    results = list(federated_query(query, initiating_participant=bank_participant, participant_stores=stores))
    elapsed = time.time() - start
    
    # Should complete in reasonable time (< 5 seconds for in-memory stores)
    assert elapsed < 5.0
    
    # Verify query plan only contacted stores that actually have beneficial owner data
    # (not a full scan of all 100 stores)
    plan = build_query_plan(query, stores)
    assert len(plan.subqueries) < 100  # optimization worked

def test_consent_evaluation_cache():
    # Verify that repeated consent checks (common in a federated query loop) are cached
    grant = ConsentGrant(...)
    alice_store = InMemoryDataStore(owner=alice_participant)
    alice_store.add_consent_grant(grant)
    
    # First evaluation (cache miss)
    start = time.time()
    result1 = evaluate_consent(alice_participant, bank_participant, "mikadiv:BeneficialOwnerShape", ["mikadiv:givenName"], [grant])
    elapsed1 = time.time() - start
    
    # Second evaluation (cache hit)
    start = time.time()
    result2 = evaluate_consent(alice_participant, bank_participant, "mikadiv:BeneficialOwnerShape", ["mikadiv:givenName"], [grant])
    elapsed2 = time.time() - start
    
    assert result1 == result2
    assert elapsed2 < elapsed1 * 0.5  # at least 2x faster due to caching
```

---

### 7. Acceptance Criteria

- [ ] **Core Abstractions**: `ParticipantIdentity`, `DataStore` protocol, `ConsentGrant`, `federated_query` all implemented and tested
- [ ] **Consent Enforcement**: Queries return empty (not error) when consent is absent; revoking consent immediately blocks access
- [ ] **Federation Works**: A transformation (Task 2) can pull data from 3+ different participant stores in one pass
- [ ] **Shape Catalog**: Participants can publish SHACL shapes (Task 1) as discoverable data contracts
- [ ] **Consent UI**: Task 3's shape renderer generates a usable consent approval screen from a shape definition
- [ ] **Alignment Integration**: Task 4's SSSOM mappings enable cross-participant queries where property names differ
- [ ] **Verifiable Credentials**: Credential verification works; policy enforcement rejects requesters without required claims
- [ ] **Audit Trail**: Every consent grant/revoke/query is immutably logged; data owners can query their own audit trail
- [ ] **Documentation**: `docs/specs/data-spaces-architecture-design.md` fully describes the design, prior art, and integration points with Tasks 1-4
- [ ] **No Breaking Changes**: Tasks 1-4's existing tests still pass (federation is additive, not a rewrite)

---

### 8. Definition of Done

Task 7 is complete when:

1. All unit tests pass (`tests/data_spaces/`)
2. All integration tests pass (shape catalog, transformation, consent UI, alignment)
3. All compliance tests pass (credentials, audit)
4. At least one end-to-end scenario test passes (regulatory reporting with consent)
5. Performance tests confirm federated queries scale reasonably (< 5s for 100 participants, in-memory)
6. Design spec is written and approved
7. Existing Tasks 1-4 tests still pass (no regressions)
8. Code review passed (if applicable)
9. Operator confirms the consent UI is usable (manual UAT on a real Solid pod + mock bank DB)
