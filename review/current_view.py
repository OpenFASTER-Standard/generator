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
    # Secondary sort key (the decision's own URI string) for determinism on an
    # exact generatedAtTime tie -- _write_decision's "already decided" guard
    # makes more than one decision per correction impossible today, so this
    # scenario can't actually arise anymore, but sorting on the timestamp
    # alone is still only a partial order; keep a real tiebreaker here too,
    # for the same defense-in-depth/consistency reason
    # _find_approved_correction below adds one to its own ORDER BY.
    decisions_with_time = [
        (decision, str(graph.value(decision, PROV.generatedAtTime)), str(decision)) for decision in decisions
    ]
    decisions_with_time.sort(key=lambda triple: (triple[1], triple[2]))
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
    # (see _find_pending_corrections's FILTER NOT EXISTS in review.corrections),
    # so proposing a new correction for a target that already has an
    # approved one leaves that older approval untouched -- nothing stops
    # both from independently being approved later. Binding each approving
    # Decision's own generatedAtTime and taking the most recent one applies
    # the same "most recent wins" rule get_correction_status already uses,
    # so the newest approval is always the one that counts as "current".
    # `ORDER BY DESC(?time) DESC(?correction)`: ?time alone is not a total
    # order -- two corrections approved with the IDENTICAL generatedAtTime
    # (confirmed live: nondeterministic across repeated queries with only
    # DESC(?time)) need a deterministic secondary key. The correction's own
    # URI is arbitrary but always deterministic, which is all that's needed
    # here.
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
    ORDER BY DESC(?time) DESC(?correction)
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
        # Deferred, function-local import (not a module-level one) is
        # deliberate: review.staleness itself imports get_correction_status
        # from this module at module-load time, so importing review.staleness
        # at THIS module's top level would create an import cycle
        # (review.current_view -> review.staleness -> review.current_view).
        # Both modules are already fully loaded by the time any caller
        # actually invokes get_current_value, so a local import here resolves
        # cleanly with no cycle.
        from review.staleness import is_correction_stale

        # An approved correction is only ever silently applied, or silently
        # flagged -- never silently misapplied (review.staleness's own stated
        # purpose). If the real run-graph value has changed since this
        # correction was made against it, applying it here would be exactly
        # that silent misapplication -- fall back to the raw run value instead.
        if not is_correction_stale(dataset, corrections_graph_uri, run_graph_uri, str(approved)):
            corrections_graph = dataset.graph(URIRef(corrections_graph_uri))
            return corrections_graph.value(approved, REVIEW.proposedValue)

    run_graph = dataset.graph(URIRef(run_graph_uri))
    for obj in run_graph.objects(subject, predicate):
        if language is None or (isinstance(obj, Literal) and obj.language == language):
            return obj
    return None
