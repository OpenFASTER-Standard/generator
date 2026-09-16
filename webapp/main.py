"""The FastAPI service: opens the persistent store, ensures at least one
real run exists, and serves everything through it. Route modules
(Tasks 14-17) register themselves onto the app returned here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from store.database import open_store
from store.runs import list_runs
from webapp.pipeline import run_pipeline_and_store

CORRECTIONS_GRAPH_URI = "https://purl.openfaster.org/review/graph/corrections"


def create_app(store_path: str, xsd_path: str, pdf_path: str) -> FastAPI:
    app = FastAPI(title="OpenFASTER Provenance & Review Platform")
    dataset = open_store(store_path, create=True)

    runs = list_runs(dataset)
    if not runs:
        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        info = run_pipeline_and_store(dataset, xsd_path, pdf_path, run_id=run_id, created_at=run_id)
    else:
        info = runs[-1]

    app.state.dataset = dataset
    app.state.latest_run = info
    app.state.corrections_graph_uri = CORRECTIONS_GRAPH_URI

    return app
