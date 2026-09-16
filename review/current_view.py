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
from review.corrections import _reject_bnode_target
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
    # Same injection shape review.corrections._reject_bnode_target guards
    # against: a BNode interpolated into this SPARQL text below becomes a
    # non-distinguished (wildcard-like) variable, not a fixed value, and
    # could silently match the wrong correction.
    _reject_bnode_target(subject, predicate)

    language_filter = f"review:targetLanguage {Literal(language).n3()} ;" if language is not None else ""
    # Two independent corrections can each legitimately end up "approved"
    # for the identical (subject, predicate, language): propose_correction's
    # auto-supersession only ever supersedes an UNDECIDED prior correction
    # (see _find_pending_correction's FILTER NOT EXISTS in review.corrections),
    # so proposing a new correction for a target that already has an
    # approved one leaves that older approval untouched -- nothing stops
    # both from independently being approved later. Binding each approving
    # Decision's own generatedAtTime and taking the most recent one applies
    # the same "most recent wins" rule get_correction_status already uses,
    # so the newest approval is always the one that counts as "current".
    results = list(dataset.query(f"""
    PREFIX review: <{REVIEW}>
    PREFIX prov: <{PROV}>
    SELECT ?correction WHERE {{
      GRAPH <{corrections_graph_uri}> {{
        ?correction a review:Correction ;
                    review:targetSubject {subject.n3()} ;
                    review:targetPredicate {predicate.n3()} ;
                    {language_filter}
                    review:proposedValue ?value .
        ?decision review:decides ?correction ; review:outcome "approved" ; prov:generatedAtTime ?time .
      }}
    }}
    ORDER BY DESC(?time)
    LIMIT 1
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
