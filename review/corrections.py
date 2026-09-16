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

from rdflib import RDF, BNode, Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.term import Node

from provenance.vocab import PROV
from review.validate import validate_graph
from review.vocab import REVIEW

SYSTEM_AGENT = REVIEW["system"]


def reviewer_uri(name: str) -> URIRef:
    return REVIEW[f"reviewer-{name}"]


def _reject_bnode_target(target_subject: Node, target_predicate: Node) -> None:
    """A blank node embedded in a SPARQL text pattern (as ``_find_pending_corrections``'s
    SELECT and ``propose_correction``'s ``wasRevisionOf`` INSERT DATA both build via
    ``.n3()`` interpolation) is a non-distinguished variable, not a fixed value -- inside
    the SELECT's WHERE clause it would silently match ANY term, potentially
    auto-superseding the wrong correction instead of erroring. Same injection shape,
    same fix, as ``provenance.record._reject_bnode`` (Plan A) -- see that module for the
    original rationale; this only needs to guard ``target_subject``/``target_predicate``
    since those are the terms this module ever interpolates into a *pattern* (as opposed
    to the ``wasRevisionOf`` INSERT DATA's fixed-data ``prior_value``, which is not
    matched against anything).
    """
    for name, term in (("target_subject", target_subject), ("target_predicate", target_predicate)):
        if isinstance(term, BNode):
            raise TypeError(
                f"{name} is a BNode ({term!r}); propose_correction only supports "
                "real, addressable subjects/predicates -- a BNode interpolated into "
                "this module's SPARQL text becomes a non-distinguished (wildcard-like) "
                "variable rather than a fixed value, and could silently match/supersede "
                "the wrong correction."
            )


def _find_pending_corrections(
    dataset: Dataset, graph_uri: str, target_subject: Node, target_predicate: Node, target_language: str
) -> list[URIRef]:
    """Returns ALL undecided (pending) corrections for this exact target, not
    just one -- more than one can exist (e.g. reachable via a failure window
    in an older, non-atomic version of propose_correction, or any future
    concurrent-write scenario), and a new proposal must supersede every one
    of them, not arbitrarily orphan the rest.
    """
    _reject_bnode_target(target_subject, target_predicate)
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
    return [URIRef(str(row["correction"])) for row in results]


def _write_decision(
    dataset: Dataset, graph_uri: str, correction_uri: URIRef, outcome: str, decider: Node, reason: str, generated_at: str,
) -> str:
    graph = dataset.graph(URIRef(graph_uri))

    # A correction may only ever be decided once -- without this guard,
    # decide_correction could be called twice on the same correction_uri
    # (e.g. approved, then later "rejected" too), leaving
    # review.current_view.get_correction_status to resolve the ambiguity by
    # generatedAtTime, which is undefined behavior on a timestamp tie (ties
    # fall back to RDF-store subject-iteration order, which is not a
    # specified ordering). Confirmed live: without this check, both calls
    # silently succeeded. This check also runs for propose_correction's own
    # internal auto-supersession call below, but is always a no-op there --
    # _find_pending_corrections's FILTER NOT EXISTS already guarantees the
    # correction being superseded has no existing decision.
    if any(graph.subjects(REVIEW.decides, correction_uri)):
        raise ValueError(f"correction {correction_uri} has already been decided")

    proposer = graph.value(correction_uri, PROV.wasAttributedTo)
    if proposer is None:
        # graph.value(...) returns None both for "correction_uri doesn't exist
        # at all" and "it exists but has no prov:wasAttributedTo" -- either way
        # there is nothing valid to attribute the decision against. Without this
        # check, `check.add((correction_uri, PROV.wasAttributedTo, None))` below
        # trips rdflib's own internal assert (a raw, undocumented AssertionError
        # -- silently a no-op under `python -O`, and not a distinguishable error
        # type for an API layer to catch).
        raise ValueError(f"no correction {correction_uri} (or it has no prov:wasAttributedTo) in <{graph_uri}>")

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
    _reject_bnode_target(target_subject, target_predicate)
    if not isinstance(prior_value, Node) or isinstance(prior_value, BNode):
        # prior_value is interpolated via .n3() below (both into the check
        # graph's own SHACL-validated triples, indirectly, and directly into
        # the wasRevisionOf INSERT DATA text) -- a non-Node (e.g. a plain
        # Python str) has no .n3() and raises a raw AttributeError deep
        # inside step (d) below, well after step (a) (supersession) used to
        # already have committed. Reject it up front, before anything is
        # written, so this is a clean, typed failure instead of a partial write.
        raise TypeError(f"prior_value must be a non-BNode rdflib term, got {prior_value!r}")

    # Build and SHACL-validate the new correction FIRST -- entirely before any
    # write happens -- so a failure anywhere in this block (bad terms, SHACL
    # violation) leaves the graph completely unchanged. Supersession of any
    # prior pending correction(s) is deliberately the LAST thing this function
    # does, after the new correction has been fully and successfully written,
    # so a failure never permanently rejects a legitimate pending correction
    # with no replacement (the store is append-only; nothing can be un-written).
    correction_uri = REVIEW[f"correction-{uuid4()}"]
    revision_n3 = f"<< {target_subject.n3()} {target_predicate.n3()} {prior_value.n3()} >>"

    check = Graph()
    check.add((correction_uri, RDF.type, REVIEW.Correction))
    check.add((correction_uri, REVIEW.status, Literal("proposed")))
    check.add((correction_uri, REVIEW.targetSubject, target_subject))
    check.add((correction_uri, REVIEW.targetPredicate, target_predicate))
    check.add((correction_uri, REVIEW.targetLanguage, Literal(target_language)))
    # lang=target_language (not a bare Literal): the value being corrected
    # carries a real language tag, so the correction's replacement value must
    # round-trip with the same tag instead of coming back as an untyped
    # xsd:string.
    check.add((correction_uri, REVIEW.proposedValue, Literal(proposed_value, lang=target_language)))
    check.add((correction_uri, REVIEW.reason, Literal(reason)))
    check.add((correction_uri, PROV.wasAttributedTo, reviewer_uri(proposer)))
    check.add((correction_uri, PROV.generatedAtTime, Literal(generated_at, datatype=XSD.dateTime)))

    conforms, results_text = validate_graph(check)
    if not conforms:
        raise ValueError(f"correction failed SHACL validation: {results_text}")

    # Read-only lookup of what (if anything) needs superseding -- still no
    # writes yet.
    pending_list = _find_pending_corrections(dataset, graph_uri, target_subject, target_predicate, target_language)

    graph = dataset.graph(URIRef(graph_uri))
    for triple in check:
        graph.add(triple)

    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        <{correction_uri}> prov:wasRevisionOf {revision_n3} .
      }}
    }}
    """)

    # Only now, after the new correction is fully and successfully written,
    # supersede every prior pending correction for this exact target (there
    # may be more than one -- see _find_pending_corrections).
    for pending in pending_list:
        _write_decision(
            dataset, graph_uri, pending, outcome="rejected", decider=SYSTEM_AGENT,
            reason="superseded by a newer proposal", generated_at=generated_at,
        )

    return str(correction_uri)


def decide_correction(
    dataset: Dataset, graph_uri: str, correction_uri: str, outcome: str, decider: str, reason: str, generated_at: str,
) -> str:
    if outcome not in ("approved", "rejected"):
        raise ValueError(f"invalid outcome: {outcome!r} (must be 'approved' or 'rejected')")
    return _write_decision(
        dataset, graph_uri, URIRef(correction_uri), outcome, reviewer_uri(decider), reason, generated_at,
    )
