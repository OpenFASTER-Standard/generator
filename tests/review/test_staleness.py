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
