# Provenance Platform — Plan B: Maker-Checker Review Workflow

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the correction proposal + maker-checker approval workflow:
append-only records, SHACL-enforced integrity (no self-approval, valid
status values), automatic supersession of stale pending proposals, and
staleness detection when a source value changes under an approved
correction.

**Architecture:** Corrections and Decisions are separate RDF resources in
`graph:corrections` (never edited/deleted in place — a correction's
lifecycle is reconstructed by finding the Decision that decides it, not
by mutating its own status). `prov:wasRevisionOf` links a Correction to
the exact quoted-triple value it supersedes, via RDF-star. SHACL shapes
validate every write before it commits.

**Tech Stack:** `pyshacl`, `rdflib`/`oxrdflib` (from Plan A).

**Spec:** `generator/docs/specs/2026-09-15-provenance-and-review-platform-design.md`

**Depends on:** Plan A (`store.database.open_store`, `provenance.vocab.PROV`) must be merged first.

## Global Constraints

- **Two different working directories matter here**: `pip install`/git
  commands run from `/work/generator`; pytest runs from `/work` as
  `python3 -m pytest generator/tests/...`, and real fixture files are
  referenced by *absolute* `/work/ontologies/...` paths in test code —
  see Plan A's own Global Constraints for why (a real bug hit and fixed
  while writing these plans).
- `review:status` on a `review:Correction` is written exactly once, at
  creation, and is always the literal `"proposed"` — it is a historical
  marker, never mutated. A correction's *effective* current status is
  always computed from whether a `review:Decision` decides it, never
  read directly off the Correction's own `review:status` triple by
  calling code outside this package.
- `review:outcome` on a `review:Decision` is one of exactly `"approved"`
  or `"rejected"` — never `"proposed"` (you cannot "decide" something
  into remaining undecided).
- Automatic supersession (an old pending proposal being replaced by a
  newer one for the same field) is attributed to `REVIEW["system"]`, not
  a human reviewer — it is bookkeeping, not a review decision.
- No mutation of any triple once written to `graph:corrections` in this
  plan — every state change is a new triple/resource.

---

### Task 7: `review/shapes.ttl` + `review/validate.py`

**Files:**
- Create: `review/__init__.py`
- Create: `review/vocab.py`
- Create: `review/shapes.ttl`
- Create: `review/validate.py`
- Test: `tests/review/__init__.py` (empty)
- Test: `tests/review/test_validate.py`

**Interfaces:**
- Produces:
  - `review.vocab.REVIEW` — `Namespace("https://purl.openfaster.org/review/")`
  - `review.validate.load_shapes() -> rdflib.Graph`
  - `review.validate.validate_graph(data_graph: rdflib.Graph) -> tuple[bool, str]` (conforms, results_text)

- [ ] **Step 1: Write the failing test**

`tests/review/__init__.py`: empty file.

`tests/review/test_validate.py`:

```python
from rdflib import RDF, Graph, Literal

from review.validate import validate_graph
from review.vocab import REVIEW
from provenance.vocab import PROV


def test_a_correction_with_status_proposed_conforms():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_correction_with_an_invalid_status_value_does_not_conform():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("bogus")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_with_a_valid_outcome_conforms():
    graph = Graph()
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, REVIEW["correction-1"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_decision_with_outcome_proposed_does_not_conform():
    graph = Graph()
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("proposed")))
    graph.add((decision, REVIEW.decides, REVIEW["correction-1"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_by_the_same_agent_that_proposed_the_correction_does_not_conform():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_by_a_different_agent_conforms():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-someone-else"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/review/test_validate.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'review'`.

- [ ] **Step 3: Implement the package**

`review/__init__.py`: empty file.

`review/vocab.py`:

```python
"""This project's real review-workflow vocabulary: corrections and
decisions are plain RDF resources in graph:corrections (see
provenance.vocab for the PROV terms used alongside these).
"""
from rdflib import Namespace

REVIEW = Namespace("https://purl.openfaster.org/review/")
```

`review/shapes.ttl`:

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix review: <https://purl.openfaster.org/review/> .
@prefix prov: <http://www.w3.org/ns/prov#> .

review:CorrectionShape a sh:NodeShape ;
    sh:targetClass review:Correction ;
    sh:property [
        sh:path review:status ;
        sh:hasValue "proposed" ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] ;
    sh:property [
        sh:path review:targetSubject ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] ;
    sh:property [
        sh:path review:targetPredicate ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] .

review:DecisionShape a sh:NodeShape ;
    sh:targetClass review:Decision ;
    sh:property [
        sh:path review:outcome ;
        sh:in ("approved" "rejected") ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] ;
    sh:property [
        sh:path review:decides ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
    ] ;
    sh:sparql [
        sh:message "A Decision's reviewer must differ from the Correction's proposer (no self-approval)." ;
        sh:select """
            PREFIX review: <https://purl.openfaster.org/review/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            SELECT $this WHERE {
                $this review:decides ?correction ;
                      prov:wasAttributedTo ?decider .
                ?correction prov:wasAttributedTo ?proposer .
                FILTER (?decider = ?proposer)
            }
        """ ;
    ] .
```

`review/validate.py`:

```python
"""SHACL validation for review-workflow writes -- gives the integrity
guarantees a SQL schema's CHECK constraints/foreign keys would otherwise
give for free (valid status/outcome values, no self-approval), as an
explicit step rather than built into the storage engine. Verified live
during design: pyshacl correctly rejects a self-approval attempt via a
SPARQL-based SHACL constraint, and accepts a decision by a different
reviewer.
"""
from __future__ import annotations

import os

import pyshacl
from rdflib import Graph

_SHAPES_PATH = os.path.join(os.path.dirname(__file__), "shapes.ttl")


def load_shapes() -> Graph:
    return Graph().parse(_SHAPES_PATH, format="turtle")


def validate_graph(data_graph: Graph) -> tuple[bool, str]:
    shapes = load_shapes()
    conforms, _, results_text = pyshacl.validate(data_graph, shacl_graph=shapes)
    return conforms, results_text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_validate.py -v`

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add review/ tests/review/
git commit -m "Add review package: SHACL shapes for corrections/decisions, incl. no-self-approval"
```

---

### Task 8: `review/corrections.py` — propose a correction, with automatic supersession

**Files:**
- Create: `review/corrections.py`
- Test: `tests/review/test_corrections.py`

**Interfaces:**
- Consumes: `store.database.open_store` (Plan A Task 1), `review.vocab.REVIEW` (Task 7), `review.validate.validate_graph` (Task 7), `provenance.vocab.PROV` (Plan A Task 4)
- Produces:
  - `review.corrections.reviewer_uri(name: str) -> rdflib.URIRef` (`REVIEW[f"reviewer-{name}"]`)
  - `review.corrections.SYSTEM_AGENT` — `REVIEW["system"]`
  - `review.corrections.propose_correction(dataset, graph_uri: str, target_subject, target_predicate, target_language: str, proposed_value: str, prior_value, proposer: str, reason: str, generated_at: str) -> str` (returns the new correction's URI as a string)

- [ ] **Step 1: Write the failing test**

`tests/review/test_corrections.py`:

```python
import shutil

from rdflib import Literal, Namespace, RDF, URIRef

from provenance.vocab import PROV
from review.corrections import SYSTEM_AGENT, propose_correction, reviewer_uri
from review.vocab import REVIEW
from store.database import open_store

STORE_PATH = "/tmp/test_review_store_task8"
EX = Namespace("https://example.org/test#")
GRAPH_URI = "urn:test:corrections"


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_propose_correction_writes_a_valid_correction_with_a_revision_link():
    dataset = _fresh_dataset()
    try:
        correction_uri = propose_correction(
            dataset,
            graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo,
            target_predicate=EX.documentation,
            target_language="de",
            proposed_value="Eine viel laengere Wirtschafts-Identifikationsnummer.",
            prior_value=Literal("Eine viel, viel, viel laengere Wirtschafts-Identifikationsnummer.", lang="de"),
            proposer="julian",
            reason="Removed a run-on repetition.",
            generated_at="2026-09-15T15:00:00Z",
        )

        graph = dataset.graph(URIRef(GRAPH_URI))
        subject = URIRef(correction_uri)
        assert (subject, RDF.type, REVIEW.Correction) in graph
        assert graph.value(subject, REVIEW.status) == Literal("proposed")
        assert graph.value(subject, REVIEW.targetSubject) == EX.WIdNrTwo
        assert graph.value(subject, PROV.wasAttributedTo) == reviewer_uri("julian")

        revision_check = list(dataset.query(f"""
        PREFIX prov: <{PROV}>
        SELECT ?s ?p ?priorValue WHERE {{
          GRAPH <{GRAPH_URI}> {{
            <{correction_uri}> prov:wasRevisionOf << ?s ?p ?priorValue >> .
          }}
        }}
        """))
        assert len(revision_check) == 1
        assert str(revision_check[0]["priorValue"]) == "Eine viel, viel, viel laengere Wirtschafts-Identifikationsnummer."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_a_second_proposal_for_the_same_field_supersedes_the_first():
    dataset = _fresh_dataset()
    try:
        first = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="First fix.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="first attempt", generated_at="2026-09-15T15:00:00Z",
        )

        second = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Better fix.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="better wording", generated_at="2026-09-15T16:00:00Z",
        )

        graph = dataset.graph(URIRef(GRAPH_URI))
        decisions = list(graph.subjects(REVIEW.decides, URIRef(first)))
        assert len(decisions) == 1
        decision = decisions[0]
        assert graph.value(decision, REVIEW.outcome) == Literal("rejected")
        assert graph.value(decision, PROV.wasAttributedTo) == SYSTEM_AGENT
        assert "superseded" in str(graph.value(decision, REVIEW.reason))

        # the second one is still undecided
        assert list(graph.subjects(REVIEW.decides, URIRef(second))) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/review/test_corrections.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'review.corrections'`.

- [ ] **Step 3: Implement `review/corrections.py`**

```python
"""Correction proposals: append-only records in graph:corrections, never
edited or deleted afterward. A new proposal for a field that already has
an undecided one automatically supersedes it (Task 8); approval/rejection
is a separate Decision resource (Task 9); a correction's effective
current status and the "current" value it contributes are both computed,
never read off a mutated field (Task 10); a later run changing the value
a correction was made against is detectable, not silently misapplied
(Task 11).
"""
from __future__ import annotations

from uuid import uuid4

from rdflib import RDF, Dataset, Graph, Literal, URIRef
from rdflib.term import Node

from provenance.vocab import PROV
from review.validate import validate_graph
from review.vocab import REVIEW

SYSTEM_AGENT = REVIEW["system"]


def reviewer_uri(name: str) -> URIRef:
    return REVIEW[f"reviewer-{name}"]


def _find_pending_correction(
    dataset: Dataset, graph_uri: str, target_subject: Node, target_predicate: Node, target_language: str
) -> URIRef | None:
    results = list(dataset.query(f"""
    PREFIX review: <{REVIEW}>
    SELECT ?correction WHERE {{
      GRAPH <{graph_uri}> {{
        ?correction a review:Correction ;
                    review:targetSubject {target_subject.n3()} ;
                    review:targetPredicate {target_predicate.n3()} ;
                    review:targetLanguage {Literal(target_language).n3()} .
        FILTER NOT EXISTS {{ ?decision review:decides ?correction }}
      }}
    }}
    """))
    if not results:
        return None
    return URIRef(str(results[0]["correction"]))


def _write_decision(
    dataset: Dataset, graph_uri: str, correction_uri: URIRef, outcome: str, decider: Node, reason: str, generated_at: str,
) -> str:
    graph = dataset.graph(URIRef(graph_uri))
    proposer = graph.value(correction_uri, PROV.wasAttributedTo)

    decision_uri = REVIEW[f"decision-{uuid4()}"]
    check = Graph()
    check.add((correction_uri, RDF.type, REVIEW.Correction))
    check.add((correction_uri, PROV.wasAttributedTo, proposer))
    check.add((decision_uri, RDF.type, REVIEW.Decision))
    check.add((decision_uri, REVIEW.decides, correction_uri))
    check.add((decision_uri, REVIEW.outcome, Literal(outcome)))
    check.add((decision_uri, REVIEW.reason, Literal(reason)))
    check.add((decision_uri, PROV.wasAttributedTo, decider))
    check.add((decision_uri, PROV.generatedAtTime, Literal(generated_at)))

    conforms, results_text = validate_graph(check)
    if not conforms:
        raise ValueError(f"decision failed SHACL validation: {results_text}")

    for triple in check.triples((decision_uri, None, None)):
        graph.add(triple)

    return str(decision_uri)


def propose_correction(
    dataset: Dataset,
    graph_uri: str,
    target_subject: Node,
    target_predicate: Node,
    target_language: str,
    proposed_value: str,
    prior_value: Node,
    proposer: str,
    reason: str,
    generated_at: str,
) -> str:
    pending = _find_pending_correction(dataset, graph_uri, target_subject, target_predicate, target_language)
    if pending is not None:
        _write_decision(
            dataset, graph_uri, pending, outcome="rejected", decider=SYSTEM_AGENT,
            reason="superseded by a newer proposal", generated_at=generated_at,
        )

    correction_uri = REVIEW[f"correction-{uuid4()}"]
    check = Graph()
    check.add((correction_uri, RDF.type, REVIEW.Correction))
    check.add((correction_uri, REVIEW.status, Literal("proposed")))
    check.add((correction_uri, REVIEW.targetSubject, target_subject))
    check.add((correction_uri, REVIEW.targetPredicate, target_predicate))
    check.add((correction_uri, REVIEW.targetLanguage, Literal(target_language)))
    check.add((correction_uri, REVIEW.proposedValue, Literal(proposed_value)))
    check.add((correction_uri, REVIEW.reason, Literal(reason)))
    check.add((correction_uri, PROV.wasAttributedTo, reviewer_uri(proposer)))
    check.add((correction_uri, PROV.generatedAtTime, Literal(generated_at)))

    conforms, results_text = validate_graph(check)
    if not conforms:
        raise ValueError(f"correction failed SHACL validation: {results_text}")

    graph = dataset.graph(URIRef(graph_uri))
    for triple in check:
        graph.add(triple)

    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        <{correction_uri}> prov:wasRevisionOf << {target_subject.n3()} {target_predicate.n3()} {prior_value.n3()} >> .
      }}
    }}
    """)

    return str(correction_uri)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_corrections.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add review/corrections.py tests/review/test_corrections.py
git commit -m "Add review.corrections.propose_correction with automatic supersession"
```

---

### Task 9: `review/corrections.py` — approve/reject a correction

**Files:**
- Modify: `review/corrections.py`
- Test: `tests/review/test_corrections.py`

**Interfaces:**
- Produces: `review.corrections.decide_correction(dataset, graph_uri: str, correction_uri: str, outcome: str, decider: str, reason: str, generated_at: str) -> str` (returns the new decision's URI; raises `ValueError` if `outcome` isn't `"approved"`/`"rejected"`, or if SHACL rejects the write — e.g. self-approval)

- [ ] **Step 1: Write the failing test**

Append to `tests/review/test_corrections.py`:

```python
import pytest

from review.corrections import decide_correction


def test_decide_correction_approved_by_a_different_reviewer_succeeds():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )

        decision_uri = decide_correction(
            dataset, graph_uri=GRAPH_URI, correction_uri=correction,
            outcome="approved", decider="someone-else", reason="looks right",
            generated_at="2026-09-16T09:00:00Z",
        )

        graph = dataset.graph(URIRef(GRAPH_URI))
        assert graph.value(URIRef(decision_uri), REVIEW.outcome) == Literal("approved")
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_decide_correction_self_approval_is_rejected():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )

        with pytest.raises(ValueError):
            decide_correction(
                dataset, graph_uri=GRAPH_URI, correction_uri=correction,
                outcome="approved", decider="julian", reason="self-approving",
                generated_at="2026-09-16T09:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_decide_correction_rejects_an_invalid_outcome():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )

        with pytest.raises(ValueError):
            decide_correction(
                dataset, graph_uri=GRAPH_URI, correction_uri=correction,
                outcome="bogus", decider="someone-else", reason="",
                generated_at="2026-09-16T09:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/review/test_corrections.py -v -k decide_correction`

Expected: FAIL with `ImportError: cannot import name 'decide_correction'`.

- [ ] **Step 3: Implement `decide_correction`**

Append to `review/corrections.py`:

```python
def decide_correction(
    dataset: Dataset, graph_uri: str, correction_uri: str, outcome: str, decider: str, reason: str, generated_at: str,
) -> str:
    if outcome not in ("approved", "rejected"):
        raise ValueError(f"invalid outcome: {outcome!r} (must be 'approved' or 'rejected')")
    return _write_decision(
        dataset, graph_uri, URIRef(correction_uri), outcome, reviewer_uri(decider), reason, generated_at,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_corrections.py -v`

Expected: PASS (5 tests total in this file).

- [ ] **Step 5: Commit**

```bash
git add review/corrections.py tests/review/test_corrections.py
git commit -m "Add review.corrections.decide_correction: approve/reject via SHACL-checked writes"
```

---

### Task 10: `review/current_view.py` — effective status + the merged "current" value

**Files:**
- Create: `review/current_view.py`
- Test: `tests/review/test_current_view.py`

**Interfaces:**
- Consumes: `store.runs` (Plan A Task 2), `review.vocab.REVIEW`, `provenance.vocab.PROV`
- Produces:
  - `review.current_view.get_correction_status(dataset, graph_uri: str, correction_uri: str) -> str` (`"proposed"`, `"approved"`, or `"rejected"`; if multiple decisions somehow exist, the most recent by `generatedAtTime` wins)
  - `review.current_view.get_current_value(dataset, run_graph_uri: str, corrections_graph_uri: str, subject, predicate, language: str | None) -> rdflib.term.Node | None` (an approved correction's value if one exists for this exact target, else the raw value from the run graph, else `None`)

- [ ] **Step 1: Write the failing test**

`tests/review/test_current_view.py`:

```python
import shutil

from rdflib import Graph as PlainGraph, Literal, Namespace, URIRef

from review.corrections import decide_correction, propose_correction
from review.current_view import get_correction_status, get_current_value
from store.database import open_store
from store.runs import write_run

STORE_PATH = "/tmp/test_review_store_task10"
EX = Namespace("https://example.org/test#")
CORRECTIONS_GRAPH = "urn:test:corrections"


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_correction_status_is_proposed_until_decided_then_reflects_the_decision():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, correction) == "proposed"

        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
            outcome="approved", decider="someone-else", reason="ok",
            generated_at="2026-09-16T09:00:00Z",
        )
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, correction) == "approved"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_current_value_prefers_an_approved_correction_over_the_raw_run_value():
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Original.", lang="de")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        raw_before_correction = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        assert str(raw_before_correction) == "Original."

        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
            outcome="approved", decider="someone-else", reason="ok",
            generated_at="2026-09-16T09:00:00Z",
        )

        current = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        assert str(current) == "Fixed text."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_current_value_falls_back_to_raw_when_no_correction_is_approved():
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.Untouched, EX.documentation, Literal("Never corrected.", lang="de")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        current = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.Untouched, EX.documentation, "de",
        )
        assert str(current) == "Never corrected."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/review/test_current_view.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'review.current_view'`.

- [ ] **Step 3: Implement `review/current_view.py`**

```python
"""Reconstructs a correction's effective status and the merged 'current'
value for a field, without ever reading a mutated field -- a
correction's own review:status triple is always literally "proposed"
(see review.corrections); the real state is derived from whichever
Decision (if any) decides it.
"""
from __future__ import annotations

from rdflib import Dataset, Literal, URIRef
from rdflib.term import Node

from provenance.vocab import PROV
from review.vocab import REVIEW


def get_correction_status(dataset: Dataset, graph_uri: str, correction_uri: str) -> str:
    graph = dataset.graph(URIRef(graph_uri))
    decisions = list(graph.subjects(REVIEW.decides, URIRef(correction_uri)))
    if not decisions:
        return "proposed"
    decisions_with_time = [
        (decision, str(graph.value(decision, PROV.generatedAtTime))) for decision in decisions
    ]
    decisions_with_time.sort(key=lambda pair: pair[1])
    latest_decision = decisions_with_time[-1][0]
    return str(graph.value(latest_decision, REVIEW.outcome))


def _find_approved_correction(
    dataset: Dataset, corrections_graph_uri: str, subject: Node, predicate: Node, language: str | None
) -> URIRef | None:
    language_filter = f"review:targetLanguage {Literal(language).n3()} ;" if language is not None else ""
    results = list(dataset.query(f"""
    PREFIX review: <{REVIEW}>
    SELECT ?correction WHERE {{
      GRAPH <{corrections_graph_uri}> {{
        ?correction a review:Correction ;
                    review:targetSubject {subject.n3()} ;
                    review:targetPredicate {predicate.n3()} ;
                    {language_filter}
                    review:proposedValue ?value .
        ?decision review:decides ?correction ; review:outcome "approved" .
      }}
    }}
    """))
    if not results:
        return None
    return URIRef(str(results[0]["correction"]))


def get_current_value(
    dataset: Dataset,
    run_graph_uri: str,
    corrections_graph_uri: str,
    subject: Node,
    predicate: Node,
    language: str | None,
) -> Node | None:
    approved = _find_approved_correction(dataset, corrections_graph_uri, subject, predicate, language)
    if approved is not None:
        corrections_graph = dataset.graph(URIRef(corrections_graph_uri))
        return corrections_graph.value(approved, REVIEW.proposedValue)

    run_graph = dataset.graph(URIRef(run_graph_uri))
    for obj in run_graph.objects(subject, predicate):
        if language is None or (isinstance(obj, Literal) and obj.language == language):
            return obj
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_current_view.py -v`

Expected: PASS (3 tests). Note: these tests hash the real corpus files
(via `write_run`) — run from `/work/generator` so the relative fixture
paths resolve.

- [ ] **Step 5: Commit**

```bash
git add review/current_view.py tests/review/test_current_view.py
git commit -m "Add review.current_view: derived correction status + merged current value"
```

---

### Task 11: `review/staleness.py` — detect a correction made against a now-changed value

**Files:**
- Create: `review/staleness.py`
- Test: `tests/review/test_staleness.py`

**Interfaces:**
- Consumes: `review.current_view`, `store.runs`
- Produces: `review.staleness.is_correction_stale(dataset, corrections_graph_uri: str, new_run_graph_uri: str, correction_uri: str) -> bool` (`True` if the correction is `"approved"` and the raw value in `new_run_graph_uri` for its target no longer matches the `prov:wasRevisionOf` value the correction was originally made against; `False` for a non-approved correction or one still matching)

- [ ] **Step 1: Write the failing test**

`tests/review/test_staleness.py`:

```python
import shutil

from rdflib import Graph as PlainGraph, Literal, Namespace

from review.corrections import decide_correction, propose_correction
from review.staleness import is_correction_stale
from store.database import open_store
from store.runs import write_run

STORE_PATH = "/tmp/test_review_store_task11"
EX = Namespace("https://example.org/test#")
CORRECTIONS_GRAPH = "urn:test:corrections"


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def _approved_correction(dataset):
    correction = propose_correction(
        dataset, graph_uri=CORRECTIONS_GRAPH,
        target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
        proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
        proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
    )
    decide_correction(
        dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
        outcome="approved", decider="someone-else", reason="ok",
        generated_at="2026-09-16T09:00:00Z",
    )
    return correction


def test_correction_is_not_stale_when_the_new_run_still_has_the_original_source_value():
    dataset = _fresh_dataset()
    try:
        correction = _approved_correction(dataset)

        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Original.", lang="de")))
        run_info = write_run(
            dataset, run_id="r-same", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t2",
        )

        assert is_correction_stale(dataset, CORRECTIONS_GRAPH, run_info.graph_uri, correction) is False
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_correction_is_stale_when_the_new_run_has_a_different_source_value():
    dataset = _fresh_dataset()
    try:
        correction = _approved_correction(dataset)

        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("A completely rewritten German sentence.", lang="de")))
        run_info = write_run(
            dataset, run_id="r-changed", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t2",
        )

        assert is_correction_stale(dataset, CORRECTIONS_GRAPH, run_info.graph_uri, correction) is True
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_a_still_pending_correction_is_never_reported_stale():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )

        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Something else entirely.", lang="de")))
        run_info = write_run(
            dataset, run_id="r-changed", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t2",
        )

        assert is_correction_stale(dataset, CORRECTIONS_GRAPH, run_info.graph_uri, correction) is False
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/review/test_staleness.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'review.staleness'`.

- [ ] **Step 3: Implement `review/staleness.py`**

```python
"""A correction is only ever silently applied, or silently flagged --
never silently misapplied. If the real value in a new run no longer
matches what an approved correction was originally made against, that
correction is stale and must be surfaced for re-review, not re-applied
as if nothing changed.
"""
from __future__ import annotations

from rdflib import Dataset, URIRef

from provenance.vocab import PROV
from review.current_view import get_correction_status


def _revision_of_value(dataset: Dataset, corrections_graph_uri: str, correction_uri: str):
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?s ?p ?priorValue WHERE {{
      GRAPH <{corrections_graph_uri}> {{
        <{correction_uri}> prov:wasRevisionOf << ?s ?p ?priorValue >> .
      }}
    }}
    """))
    if not results:
        raise ValueError(f"correction {correction_uri!r} has no prov:wasRevisionOf record")
    row = results[0]
    return URIRef(str(row["s"])), URIRef(str(row["p"])), row["priorValue"]


def is_correction_stale(
    dataset: Dataset, corrections_graph_uri: str, new_run_graph_uri: str, correction_uri: str
) -> bool:
    if get_correction_status(dataset, corrections_graph_uri, correction_uri) != "approved":
        return False

    subject, predicate, prior_value = _revision_of_value(dataset, corrections_graph_uri, correction_uri)

    new_run_graph = dataset.graph(URIRef(new_run_graph_uri))
    current_raw_values = list(new_run_graph.objects(subject, predicate))
    return prior_value not in current_raw_values
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_staleness.py -v`

Expected: PASS (3 tests).

- [ ] **Step 5: Run the full Plan B test suite**

Run: `cd /work && python3 -m pytest generator/tests/review/ -v`

Expected: all tests from Tasks 7-11 pass.

- [ ] **Step 6: Commit**

```bash
git add review/staleness.py tests/review/test_staleness.py
git commit -m "Add review.staleness: detect a correction made against a now-superseded source value"
```
