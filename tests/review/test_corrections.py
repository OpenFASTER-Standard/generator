import shutil

import pytest
from rdflib import BNode, Literal, Namespace, RDF, URIRef

from provenance.vocab import PROV
from review.corrections import (
    SYSTEM_AGENT,
    _find_pending_corrections,
    decide_correction,
    propose_correction,
    reviewer_uri,
)
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
        # str(), not `== Literal("proposed")`: confirmed live that this store's
        # Oxigraph backend round-trips a plain (no datatype/lang) literal back
        # out with an explicit xsd:string datatype attached, which fails
        # rdflib's strict, datatype-aware Literal.__eq__ against a freshly
        # constructed plain Literal -- same pitfall test_database.py's own
        # test already sidesteps the same way.
        assert str(graph.value(subject, REVIEW.status)) == "proposed"
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
        # str(), not `== Literal("rejected")`: same plain-literal round-trip
        # normalization noted above.
        assert str(graph.value(decision, REVIEW.outcome)) == "rejected"
        assert graph.value(decision, PROV.wasAttributedTo) == SYSTEM_AGENT
        assert "superseded" in str(graph.value(decision, REVIEW.reason))

        # the second one is still undecided
        assert list(graph.subjects(REVIEW.decides, URIRef(second))) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_supersession_is_scoped_exactly_to_subject_predicate_and_language():
    """A prior undecided correction must only be superseded by a new proposal
    for the EXACT same (target_subject, target_predicate, target_language) --
    not a broader match (same subject+predicate, different language) nor a
    narrower one (same subject, different predicate)."""
    dataset = _fresh_dataset()
    try:
        de_correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="German fix.", prior_value=Literal("Original de.", lang="de"),
            proposer="julian", reason="de fix", generated_at="2026-09-15T15:00:00Z",
        )

        # Same subject+predicate, different language -- must NOT supersede the German one.
        en_correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="en",
            proposed_value="English fix.", prior_value=Literal("Original en.", lang="en"),
            proposer="julian", reason="en fix", generated_at="2026-09-15T15:05:00Z",
        )

        # Same subject+language, different predicate -- must NOT supersede the German one either.
        other_predicate_correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.otherField, target_language="de",
            proposed_value="Other field fix.", prior_value=Literal("Original other.", lang="de"),
            proposer="julian", reason="other field fix", generated_at="2026-09-15T15:10:00Z",
        )

        graph = dataset.graph(URIRef(GRAPH_URI))
        # None of the three corrections should have been superseded/decided --
        # each occupies a distinct (subject, predicate, language) slot.
        for uri in (de_correction, en_correction, other_predicate_correction):
            assert list(graph.subjects(REVIEW.decides, URIRef(uri))) == [], (
                f"{uri} should still be undecided but was superseded"
            )

        # Now propose a genuine second German fix -- this one SHOULD supersede
        # only the original German correction, leaving the other two untouched.
        second_de_correction = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Better German fix.", prior_value=Literal("Original de.", lang="de"),
            proposer="julian", reason="better de fix", generated_at="2026-09-15T15:15:00Z",
        )

        decisions_on_de = list(graph.subjects(REVIEW.decides, URIRef(de_correction)))
        assert len(decisions_on_de) == 1
        assert str(graph.value(decisions_on_de[0], REVIEW.outcome)) == "rejected"

        assert list(graph.subjects(REVIEW.decides, URIRef(en_correction))) == []
        assert list(graph.subjects(REVIEW.decides, URIRef(other_predicate_correction))) == []
        assert list(graph.subjects(REVIEW.decides, URIRef(second_de_correction))) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_a_third_proposal_only_supersedes_the_still_undecided_second_one():
    """After first is superseded by second, a third proposal must supersede
    the (still-undecided) second one, not reach past it to the already-decided
    first -- i.e. FILTER NOT EXISTS excludes anything with ANY decision, not
    just approved ones."""
    dataset = _fresh_dataset()
    try:
        first = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="First.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="r1", generated_at="2026-09-15T15:00:00Z",
        )
        second = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Second.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="r2", generated_at="2026-09-15T16:00:00Z",
        )
        third = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Third.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="r3", generated_at="2026-09-15T17:00:00Z",
        )

        graph = dataset.graph(URIRef(GRAPH_URI))
        # first has exactly one decision (from when second was proposed)
        assert len(list(graph.subjects(REVIEW.decides, URIRef(first)))) == 1
        # second now has exactly one decision (from when third was proposed) -- not zero, not two
        second_decisions = list(graph.subjects(REVIEW.decides, URIRef(second)))
        assert len(second_decisions) == 1
        assert str(graph.value(second_decisions[0], REVIEW.outcome)) == "rejected"
        # third is still undecided
        assert list(graph.subjects(REVIEW.decides, URIRef(third))) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_propose_correction_rejects_a_bnode_target_subject():
    """A BNode interpolated into _find_pending_corrections's SPARQL SELECT text
    becomes a non-distinguished (wildcard-like) variable, not a fixed value --
    it would silently match/supersede an unrelated correction instead of
    erroring. Same injection shape provenance.record._reject_bnode already
    guards against (Plan A); propose_correction must reject it up front too."""
    dataset = _fresh_dataset()
    try:
        with pytest.raises(TypeError):
            propose_correction(
                dataset, graph_uri=GRAPH_URI,
                target_subject=BNode(), target_predicate=EX.documentation, target_language="de",
                proposed_value="x", prior_value=Literal("Original.", lang="de"),
                proposer="julian", reason="r", generated_at="2026-09-15T15:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


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
        # str(), not `== Literal("approved")`: same plain-literal round-trip
        # normalization noted above.
        assert str(graph.value(URIRef(decision_uri), REVIEW.outcome)) == "approved"
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


def test_propose_correction_failed_call_leaves_original_pending_correction_untouched():
    """Critical whole-branch-review finding: the old propose_correction wrote
    step (a) (supersede the prior pending correction, i.e. write a rejection
    Decision) BEFORE steps (b)-(d) (build + SHACL-validate the new correction,
    write its triples, write its wasRevisionOf link). Those later steps can
    fail independently (e.g. prior_value isn't a real rdflib term and has no
    .n3()) -- and by then step (a) had ALREADY committed, permanently
    rejecting a legitimate pending correction with no replacement, since the
    store is append-only and nothing can be un-written. Fixed by reordering so
    ALL validation/term-coercion happens before ANY write, and supersession
    happens LAST, only after the new correction is fully, successfully
    written. This test proves a failed call leaves no trace at all."""
    dataset = _fresh_dataset()
    try:
        original = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Original fix.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="first attempt", generated_at="2026-09-15T15:00:00Z",
        )

        with pytest.raises(TypeError):
            propose_correction(
                dataset, graph_uri=GRAPH_URI,
                target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
                proposed_value="Doomed fix.", prior_value="not a term",
                proposer="julian", reason="malformed prior_value", generated_at="2026-09-15T16:00:00Z",
            )

        graph = dataset.graph(URIRef(GRAPH_URI))
        # str(), not `== Literal("proposed")`: same plain-literal round-trip
        # normalization noted above.
        assert str(graph.value(URIRef(original), REVIEW.status)) == "proposed"
        assert list(graph.subjects(REVIEW.decides, URIRef(original))) == []
        pending = _find_pending_corrections(dataset, GRAPH_URI, EX.WIdNrTwo, EX.documentation, "de")
        assert URIRef(original) in pending
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_a_third_proposal_supersedes_both_of_two_independently_pending_corrections():
    """If two pending (undecided) corrections somehow exist for the identical
    (subject, predicate, language) target -- reachable, before this fix wave,
    via the exact non-atomicity bug the previous test covers, or via any
    future concurrent-write scenario -- a third proposal must supersede BOTH,
    not arbitrarily orphan one of them the way the old, singular
    _find_pending_correction (no ORDER BY, results[0] taken) would have.
    Constructed via direct graph writes since propose_correction's own
    supersession would normally prevent two pending corrections from
    coexisting in the first place."""
    dataset = _fresh_dataset()
    try:
        graph = dataset.graph(URIRef(GRAPH_URI))

        def _write_bare_pending_correction(uri, value):
            graph.add((uri, RDF.type, REVIEW.Correction))
            graph.add((uri, REVIEW.status, Literal("proposed")))
            graph.add((uri, REVIEW.targetSubject, EX.WIdNrTwo))
            graph.add((uri, REVIEW.targetPredicate, EX.documentation))
            graph.add((uri, REVIEW.targetLanguage, Literal("de")))
            graph.add((uri, REVIEW.proposedValue, Literal(value, lang="de")))
            graph.add((uri, PROV.wasAttributedTo, reviewer_uri("julian")))
            graph.add((uri, PROV.generatedAtTime, Literal("2026-09-15T15:00:00Z")))

        pending_a = REVIEW["correction-manual-a"]
        pending_b = REVIEW["correction-manual-b"]
        _write_bare_pending_correction(pending_a, "Manual A.")
        _write_bare_pending_correction(pending_b, "Manual B.")

        third = propose_correction(
            dataset, graph_uri=GRAPH_URI,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Third.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="r3", generated_at="2026-09-15T17:00:00Z",
        )

        for pending in (pending_a, pending_b):
            decisions = list(graph.subjects(REVIEW.decides, pending))
            assert len(decisions) == 1, f"{pending} should have exactly one (superseding) decision"
            assert str(graph.value(decisions[0], REVIEW.outcome)) == "rejected"

        assert list(graph.subjects(REVIEW.decides, URIRef(third))) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_decide_correction_on_an_unknown_correction_raises_value_error_not_assertion_error():
    """_write_decision does `graph.value(correction_uri, PROV.wasAttributedTo)`,
    which returns None for a nonexistent (or unattributed) correction; adding
    a triple with None as the object used to trip rdflib's own internal
    assert -- a raw AssertionError, silently a no-op under `python -O`, and
    not a distinguishable error type for an API layer."""
    dataset = _fresh_dataset()
    try:
        with pytest.raises(ValueError):
            decide_correction(
                dataset, graph_uri=GRAPH_URI, correction_uri=str(REVIEW["correction-does-not-exist"]),
                outcome="approved", decider="someone-else", reason="ok",
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
