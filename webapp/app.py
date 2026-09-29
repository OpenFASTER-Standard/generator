"""Serves the references catalog as browsable pages with revision
history, plus a candidate-browsing + citation-submission interaction
layer, plus the drift-review pipeline. See
docs/specs/2026-09-25-catalog-revision-history-design.md,
docs/specs/2026-09-25-citation-workflow-design.md, and
docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from citation_workflow.add_citation import FamilyNotCitableError, FamilyNotFoundError, add_citation
from discovery.corpus_candidates import list_corpus_candidates
from reference_model.cite import CitationError
from references_catalog.catalog import get_history, list_pages
from review_recording.record import Verdict
from review_workflow.orchestrate import get_review_summary, submit_review

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"
DEFAULT_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
DEFAULT_REVIEWS_DIR = "/work/ontologies/mikadiv-fm/reviews"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


def _module_root() -> str:
    # Same call-time-read pattern as _catalog_path(), for the same reason.
    return os.environ.get("MIKADIV_MODULE_ROOT", DEFAULT_MODULE_ROOT)


def _reviews_dir() -> str:
    # Same call-time-read pattern as _catalog_path()/_module_root().
    return os.environ.get("MIKADIV_REVIEWS_DIR", DEFAULT_REVIEWS_DIR)


class AddCitationRequest(BaseModel):
    family: str
    xpath: str
    fact_key: str
    author: str
    comment: str
    is_correction: bool

    @field_validator("fact_key", "author")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # A blank fact_key would write a page into the real, git-tracked
        # catalog that no URL can ever reach again (GET /api/pages/ 404s
        # on an empty path segment); a blank author defeats the point of
        # recording one. Reject both at the boundary, before add_citation()
        # ever touches the catalog.
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class SubmitReviewRequest(BaseModel):
    fact_key: str
    leaf_reference_id: str  # identifies which FlaggedLeaf under fact_key this decision is for
    reviewer: str
    verdict: str  # "approved" | "rejected"
    reasoning: str


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
    except (FamilyNotFoundError, FamilyNotCitableError, CitationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


@app.get("/api/review")
def get_review_endpoint() -> dict:
    result = get_review_summary(_catalog_path(), _module_root(), _reviews_dir())
    return {
        "flagged": {
            fact_key: [dataclasses.asdict(fl) for fl in entries]
            for fact_key, entries in result.summary.flagged.items()
        },
        "unresolved_families": [dataclasses.asdict(f) for f in result.summary.unresolved_families],
        "excluded_keys": list(result.summary.excluded_keys),
        "deserialization_failures": list(result.deserialization_failures),
    }


@app.post("/api/reviews")
def submit_review_endpoint(request: SubmitReviewRequest) -> dict:
    # Re-fetches the current summary server-side and finds the exact FlaggedLeaf
    # by reference_id, rather than trusting a client-serialized FlaggedLeaf --
    # same "never trust client state for anything server-verifiable" principle
    # citation_workflow's add_citation() already established for `family`.
    # Verdict shape is validated first -- a pure input check independent of
    # any server state -- before the more expensive re-verification lookup.
    try:
        verdict = Verdict(request.verdict)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid verdict: {request.verdict!r}")

    result = get_review_summary(_catalog_path(), _module_root(), _reviews_dir())
    entries = result.summary.flagged.get(request.fact_key, ())
    flagged = next((fl for fl in entries if fl.leaf.reference_id == request.leaf_reference_id), None)
    if flagged is None:
        raise HTTPException(
            status_code=404,
            detail=f"no pending flagged leaf {request.leaf_reference_id!r} under {request.fact_key!r}",
        )

    revision = submit_review(
        _catalog_path(), _reviews_dir(), request.fact_key, flagged, request.reviewer, verdict, request.reasoning,
    )
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


_FRONTEND_DIST = Path(__file__).parent / "frontend_dist"

app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="static")


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request: Request, exc: StarletteHTTPException):
    # A real API 404 (an unknown fact_key, an unknown review, etc.) stays a
    # real 404 with its own JSON body. Anything else that reaches here is a
    # path StaticFiles itself couldn't resolve to a real built asset -- the
    # signal that it must be a React Router client-side route, which only
    # needs the SPA shell to take over from here.
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        return FileResponse(_FRONTEND_DIST / "index.html")
    # Not the SPA-fallback case (a real /api/* error, or a non-404) -- fall
    # through to FastAPI's own default HTTPException handling so a real API
    # error still gets its normal JSON {"detail": ...} response. Re-raising
    # `exc` here instead would propagate it as an actual Python exception
    # rather than a response, since this handler is itself what's registered
    # for it.
    return await http_exception_handler(request, exc)
