import shutil

import pytest
from rdflib import BNode, Graph as PlainGraph, Literal, Namespace, URIRef

from review.corrections import decide_correction, propose_correction
from review.current_view import (
    _find_approved_correction,
    get_correction_status,
    get_current_value,
    materialize_current_graph,
)
from review.staleness import is_correction_stale
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


def test_get_current_value_returns_the_most_recently_approved_correction_when_two_are_independently_approved():
    """Two SEPARATE corrections for the identical (subject, predicate, language)
    can each legitimately end up "approved": propose_correction's auto-supersession
    only ever supersedes an UNDECIDED prior correction, so proposing correction B
    after correction A has already been approved leaves A's approval untouched --
    nothing stops B from later being independently approved too. get_current_value
    must resolve this by preferring the most recently approved one (by the
    deciding Decision's own generatedAtTime), not an arbitrary SPARQL match."""
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrThree, EX.documentation, Literal("Original.", lang="de")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        correction_a = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrThree, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fix A.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="first fix", generated_at="2026-09-15T15:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction_a,
            outcome="approved", decider="reviewer-a", reason="ok",
            generated_at="2026-09-15T15:30:00Z",
        )

        # A is already approved (not pending), so this second proposal does NOT
        # supersede it -- it's a wholly independent correction for the same target.
        correction_b = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrThree, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fix B (newer).", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="better fix", generated_at="2026-09-16T09:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction_b,
            outcome="approved", decider="reviewer-b", reason="even better",
            generated_at="2026-09-16T10:00:00Z",
        )

        current = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrThree, EX.documentation, "de",
        )
        assert str(current) == "Fix B (newer)."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_decide_correction_on_an_already_decided_correction_raises():
    dataset = _fresh_dataset()
    try:
        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
            outcome="approved", decider="reviewer-a", reason="ok",
            generated_at="2026-09-16T09:00:00Z",
        )

        with pytest.raises(ValueError):
            decide_correction(
                dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
                outcome="rejected", decider="reviewer-b", reason="actually no",
                generated_at="2026-09-16T09:00:01Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_current_value_falls_back_to_raw_value_when_the_approved_correction_is_stale():
    """Important whole-branch-review finding: get_current_value used to never
    check staleness at all -- it applied whichever correction
    _find_approved_correction returned, even if the real source value had
    since changed underneath it, directly contradicting review.staleness's
    own stated purpose ("never silently misapplied"). Fixed by checking
    is_correction_stale against the run being asked about before applying an
    approved correction; if stale, fall back to the raw (changed) run value."""
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

        # Sanity check: against the ORIGINAL run, the approved correction still applies.
        current_on_original_run = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        assert str(current_on_original_run) == "Fixed text."

        # Now a NEW run comes in where the underlying source value has changed
        # from what the correction's prov:wasRevisionOf recorded -- the
        # correction is stale against this new run.
        new_run_graph = PlainGraph()
        new_run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("A completely different upstream value.", lang="de")))
        new_run_info = write_run(
            dataset, run_id="r2", graph=new_run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t2",
        )
        assert is_correction_stale(dataset, CORRECTIONS_GRAPH, new_run_info.graph_uri, correction) is True

        current_on_new_run = get_current_value(
            dataset, new_run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        # Must be the RAW (changed) value, NOT the now-stale correction's value.
        assert str(current_on_new_run) == "A completely different upstream value."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_proposed_value_round_trips_with_its_target_language_tag():
    """Important whole-branch-review finding: review:proposedValue used to be
    stored as a bare, untagged Literal even though the correction has a real
    target_language -- a corrected German string came back as an untyped
    xsd:string instead of a "..."@de literal, inconsistent with the raw value
    it replaced and not round-trippable."""
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

        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Korrigierter deutscher Text.", prior_value=Literal("Original.", lang="de"),
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
        assert isinstance(current, Literal)
        assert current.language == "de"
        assert str(current) == "Korrigierter deutscher Text."
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_approved_correction_is_deterministic_on_an_identical_generated_at_timestamp():
    """Important whole-branch-review finding, confirmed live by the reviewer
    across 6 trials: _find_approved_correction's `ORDER BY DESC(?time) LIMIT 1`
    had no secondary sort key, so two different corrections approved with the
    IDENTICAL timestamp produced a nondeterministic winner across repeated
    queries. Fixed with a deterministic secondary sort key (the correction's
    own URI). This test calls _find_approved_correction/get_current_value
    repeatedly and asserts the SAME result every time."""
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrFour, EX.documentation, Literal("Original.", lang="de")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        identical_timestamp = "2026-09-16T09:00:00Z"

        correction_a = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrFour, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fix A.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="first fix", generated_at="2026-09-15T15:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction_a,
            outcome="approved", decider="reviewer-a", reason="ok",
            generated_at=identical_timestamp,
        )

        # B is proposed against the SAME original value -- since A is already
        # approved (not pending), this does NOT supersede it.
        correction_b = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrFour, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fix B.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="second fix", generated_at="2026-09-15T15:05:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction_b,
            outcome="approved", decider="reviewer-b", reason="ok too",
            generated_at=identical_timestamp,
        )

        first_result = _find_approved_correction(
            dataset, CORRECTIONS_GRAPH, EX.WIdNrFour, EX.documentation, "de",
        )
        for _ in range(10):
            repeat_result = _find_approved_correction(
                dataset, CORRECTIONS_GRAPH, EX.WIdNrFour, EX.documentation, "de",
            )
            assert repeat_result == first_result, "the winner must be deterministic across repeated queries"

        first_value = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrFour, EX.documentation, "de",
        )
        for _ in range(10):
            repeat_value = get_current_value(
                dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrFour, EX.documentation, "de",
            )
            assert str(repeat_value) == str(first_value), "the applied value must be deterministic across repeated calls"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_current_value_rejects_a_bnode_subject():
    """Same injection shape review.corrections._reject_bnode_target already
    guards against: a BNode interpolated into _find_approved_correction's
    SPARQL text becomes a non-distinguished (wildcard-like) variable, not a
    fixed value, and could silently match the wrong correction."""
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        with pytest.raises(TypeError):
            get_current_value(
                dataset, run_info.graph_uri, CORRECTIONS_GRAPH, BNode(), EX.documentation, "de",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_materialize_current_graph_substitutes_approved_corrections_in_place():
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Original.", lang="de")))
        run_graph.add((EX.Other, EX.name, Literal("Other")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

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

        current = materialize_current_graph(dataset, run_info.graph_uri, CORRECTIONS_GRAPH)

        docs = list(current.objects(EX.WIdNrTwo, EX.documentation))
        assert [str(d) for d in docs] == ["Fixed text."]
        # Untouched facts pass through -- compared by value (str()), not raw
        # Literal term equality: Oxigraph (RDF-1.1-compliant) always round-trips
        # a plain/untyped literal with an explicit xsd:string datatype, while a
        # freshly-constructed Literal("Other") here leaves .datatype as None.
        # rdflib's Literal.__eq__ (what plain Graph.__contains__ uses) is strict
        # term equality, not RDF-1.1 value equality (Literal.eq() agrees they're
        # equal) -- so `(EX.Other, EX.name, Literal("Other")) in current` would
        # fail here on a pure store round-trip artifact unrelated to
        # materialize_current_graph's corrections-resolution logic.
        assert [str(o) for o in current.objects(EX.Other, EX.name)] == ["Other"]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
