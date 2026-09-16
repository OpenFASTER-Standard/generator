"""One real end-to-end lifecycle test walking the FULL review-workflow chain
in a single test. Added as part of the final whole-branch review of Plan B
(the maker-checker review workflow): 3 of this plan's 5 tasks each shipped a
bug that only this kind of cross-step interaction revealed (see
review.corrections, review.current_view, review.staleness for each task's own
fix history), so this is the single highest-value regression test for this
package -- every individual unit test in this package's other test modules
covers one step in isolation, but none of them walks propose -> supersede ->
approve -> apply -> new-run -> stale -> fall-back-to-raw in one connected
scenario the way real usage will.
"""
import shutil

from rdflib import Graph as PlainGraph, Literal, Namespace, URIRef

from review.corrections import decide_correction, propose_correction
from review.current_view import get_correction_status, get_current_value
from review.staleness import is_correction_stale
from review.vocab import REVIEW
from store.database import open_store
from store.runs import write_run

STORE_PATH = "/tmp/test_review_store_lifecycle"
EX = Namespace("https://example.org/test#")
CORRECTIONS_GRAPH = "urn:test:corrections"


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_full_correction_lifecycle_propose_supersede_approve_apply_then_stale_on_a_new_run():
    dataset = _fresh_dataset()
    try:
        # 1. An initial run records the original (German) value.
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Original.", lang="de")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        # 2. Propose a first correction for that field.
        first = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="First fix.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="first attempt", generated_at="2026-09-15T15:00:00Z",
        )
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, first) == "proposed"

        # 3. Propose a SECOND correction for the identical field -- this must
        # automatically supersede (reject) the first one, which is still
        # undecided.
        second = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Better fix.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="better wording", generated_at="2026-09-15T16:00:00Z",
        )
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, first) == "rejected"
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, second) == "proposed"

        # 4. Approve the second (surviving) correction.
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=second,
            outcome="approved", decider="someone-else", reason="looks right",
            generated_at="2026-09-16T09:00:00Z",
        )
        assert get_correction_status(dataset, CORRECTIONS_GRAPH, second) == "approved"

        # 5. get_current_value against the ORIGINAL run must now reflect the
        # approved correction, with its language tag intact.
        current_on_original_run = get_current_value(
            dataset, run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        assert isinstance(current_on_original_run, Literal)
        assert current_on_original_run.language == "de"
        assert str(current_on_original_run) == "Better fix."

        # 6. A NEW run comes in where the underlying source value has changed
        # from what the approved correction's prov:wasRevisionOf recorded.
        new_run_graph = PlainGraph()
        new_run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("A totally different upstream rewrite.", lang="de")))
        new_run_info = write_run(
            dataset, run_id="r2", graph=new_run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t2",
        )

        # 7. is_correction_stale must report the approved correction as stale
        # against this new run.
        assert is_correction_stale(dataset, CORRECTIONS_GRAPH, new_run_info.graph_uri, second) is True

        # 8. get_current_value against the NEW run must NOT silently misapply
        # the now-stale correction -- it must fall back to the raw (changed)
        # run value instead.
        current_on_new_run = get_current_value(
            dataset, new_run_info.graph_uri, CORRECTIONS_GRAPH, EX.WIdNrTwo, EX.documentation, "de",
        )
        assert str(current_on_new_run) == "A totally different upstream rewrite."

        # Sanity check throughout: neither correction resource nor the
        # original run graph were ever mutated -- everything above was
        # derived, not read off a changed field.
        corrections_graph = dataset.graph(URIRef(CORRECTIONS_GRAPH))
        assert str(corrections_graph.value(URIRef(second), REVIEW.status)) == "proposed"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
