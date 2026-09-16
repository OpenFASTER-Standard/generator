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
