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
from rdflib.namespace import XSD
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
    # Deliberately NOT `check.add((correction_uri, RDF.type, REVIEW.Correction))`:
    # doing so would make pyshacl treat correction_uri as a CorrectionShape
    # target within this minimal, single-purpose validation subgraph, and
    # fail it for lacking review:status/targetSubject/targetPredicate (which
    # this subgraph never carries, on purpose -- confirmed live, this was
    # the exact failure the first version of this function hit). The
    # DecisionShape's own no-self-approval SPARQL constraint only needs
    # `?correction prov:wasAttributedTo ?proposer`, not `?correction`'s type.
    check.add((correction_uri, PROV.wasAttributedTo, proposer))
    check.add((decision_uri, RDF.type, REVIEW.Decision))
    check.add((decision_uri, REVIEW.decides, correction_uri))
    check.add((decision_uri, REVIEW.outcome, Literal(outcome)))
    check.add((decision_uri, REVIEW.reason, Literal(reason)))
    check.add((decision_uri, PROV.wasAttributedTo, decider))
    check.add((decision_uri, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime)))

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
    check.add((correction_uri, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime)))

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
