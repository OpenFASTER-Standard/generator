import shutil

from rdflib import Graph, Literal, Namespace, URIRef

from store.database import open_store
from store.runs import list_runs, write_run

STORE_PATH = "/tmp/test_provenance_store_task2"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_write_run_stores_the_graph_under_a_new_named_graph_and_returns_info():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.WIdNr, EX.documentation, Literal("German text", lang="de")))

        info = write_run(
            dataset,
            run_id="2026-09-15T14:00:00Z",
            graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T14:00:00Z",
        )

        assert info.run_id == "2026-09-15T14:00:00Z"
        assert info.xsd_hash and info.pdf_hash  # real sha256 hex digests, non-empty

        stored_graph = dataset.graph(URIRef(info.graph_uri))
        stored = list(stored_graph.triples((None, None, None)))
        assert len(stored) == 1
        assert str(stored[0][2]) == "German text"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_list_runs_returns_every_written_run_sorted_by_created_at():
    dataset = _fresh_dataset()
    try:
        write_run(
            dataset, run_id="run-b", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T09:00:00Z",
        )
        write_run(
            dataset, run_id="run-a", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T08:00:00Z",
        )

        runs = list_runs(dataset)

        assert [r.run_id for r in runs] == ["run-a", "run-b"]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
