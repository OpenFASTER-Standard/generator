"""The FastAPI service: opens the persistent store, ensures at least one
real run exists, and serves everything through it. Route modules
(Tasks 14-17) register themselves onto the app returned here.

Every route module's error handling is installed here too, exactly once
(`webapp.errors.install_error_handlers`) rather than per endpoint -- see
that module's own docstring for the exception-to-status mapping and why
it lives in one place.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from store.database import open_store
from store.runs import list_runs
from webapp.errors import install_error_handlers
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

    from webapp.routes_structure import router as structure_router
    app.include_router(structure_router)

    from webapp.routes_provenance import router as provenance_router
    app.include_router(provenance_router)

    from webapp.routes_runs import router as runs_router
    app.include_router(runs_router)

    from webapp.routes_corrections import router as corrections_router
    app.include_router(corrections_router)

    from webapp.routes_sources import router as sources_router
    app.include_router(sources_router)

    install_error_handlers(app)

    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


def _e2e_app():
    """A zero-argument factory for Playwright's own webServer config
    (frontend/playwright.config.ts) -- uvicorn's --factory flag requires
    a callable with no arguments, unlike create_app's own real
    (store_path, xsd_path, pdf_path) signature every other caller uses.
    """
    import shutil

    store_path = "/tmp/e2e_test_store"
    shutil.rmtree(store_path, ignore_errors=True)
    return create_app(
        store_path,
        "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
        "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
    )
