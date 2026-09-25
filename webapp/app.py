"""Serves the references catalog as browsable pages with revision
history, plus a candidate-browsing + citation-submission interaction
layer. See docs/specs/2026-09-25-catalog-revision-history-design.md and
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from citation_workflow.add_citation import FamilyNotFoundError, add_citation
from discovery.corpus_candidates import list_corpus_candidates
from reference_model.cite import CitationError
from references_catalog.catalog import get_history, list_pages

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"
DEFAULT_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


def _module_root() -> str:
    # Same call-time-read pattern as _catalog_path(), for the same reason.
    return os.environ.get("MIKADIV_MODULE_ROOT", DEFAULT_MODULE_ROOT)


class AddCitationRequest(BaseModel):
    family: str
    xpath: str
    fact_key: str
    author: str
    comment: str
    is_correction: bool


@app.get("/api/pages")
def list_pages_endpoint() -> dict:
    pages = list_pages(_catalog_path())
    return {
        fact_key: {
            "revision_count": summary.revision_count,
            "current": dataclasses.asdict(summary.current),
        }
        for fact_key, summary in pages.items()
    }


@app.get("/api/pages/{fact_key}")
def get_page(fact_key: str) -> dict:
    history = get_history(_catalog_path(), fact_key)
    if not history:
        raise HTTPException(status_code=404, detail=f"No such page: {fact_key!r}")
    return {
        "fact_key": fact_key,
        "current": dataclasses.asdict(history[-1]),
        "history": [dataclasses.asdict(r) for r in history],
    }


@app.get("/api/candidates")
def list_candidates_endpoint() -> dict:
    candidates = list_corpus_candidates(_module_root())
    return {
        family: [dataclasses.asdict(c) for c in family_candidates]
        for family, family_candidates in candidates.items()
    }


@app.post("/api/citations")
def add_citation_endpoint(request: AddCitationRequest) -> dict:
    try:
        revision = add_citation(
            _module_root(),
            _catalog_path(),
            request.family,
            request.xpath,
            request.fact_key,
            request.author,
            request.comment,
            request.is_correction,
        )
    except (FamilyNotFoundError, CitationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
