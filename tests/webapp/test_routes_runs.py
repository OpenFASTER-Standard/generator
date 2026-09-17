import shutil

from fastapi.testclient import TestClient
from rdflib import Graph, Literal, Namespace

from store.runs import write_run
from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task16"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")


def test_runs_endpoint_lists_every_real_run():
    store_path = STORE_PATH + "_list"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/runs")

        assert response.status_code == 200
        run_ids = [r["runId"] for r in response.json()]
        assert app.state.latest_run.run_id in run_ids
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_diff_endpoint_reports_added_and_removed_triples_between_two_runs():
    store_path = STORE_PATH + "_diff"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)

        extra_graph = Graph()
        extra_graph.add((EX.NewSubject, EX.newFact, Literal("brand new")))
        write_run(
            app.state.dataset, run_id="extra-run", graph=extra_graph,
            xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF, created_at="2026-09-17T00:00:00Z",
        )

        client = TestClient(app)
        response = client.get(f"/api/runs/{app.state.latest_run.run_id}/diff/extra-run")

        assert response.status_code == 200
        added_objects = {row[2] for row in response.json()["added"]}
        assert "brand new" in added_objects
    finally:
        shutil.rmtree(store_path, ignore_errors=True)
