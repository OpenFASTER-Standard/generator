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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from citation_workflow.add_citation import add_citation
from discovery.corpus_candidates import list_corpus_candidates
from errors import GeneratorError
from references_catalog.catalog import get_current_revision, get_history, list_pages
from review_recording.record import Verdict
from review_workflow.orchestrate import get_review_summary, submit_review

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"
DEFAULT_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
DEFAULT_REVIEWS_DIR = "/work/ontologies/mikadiv-fm/reviews"

app = FastAPI()


@app.exception_handler(GeneratorError)
async def generator_error_handler(request: Request, exc: GeneratorError) -> JSONResponse:
    # One handler for every domain error in the system (see errors.py) --
    # each subclass says its own http_status, so no endpoint needs its own
    # try/except to get a meaningful status + message instead of a bare
    # 500 with no detail.
    return JSONResponse(status_code=exc.http_status, content={"detail": str(exc)})


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

    @field_validator("reviewer", "reasoning")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # A review's whole point is accountability: a blank reviewer or
        # reasoning would permanently suppress a drift finding with no
        # record of who did it or why. Same reasoning as
        # AddCitationRequest's own _reject_blank validator on author.
        if not value.strip():
            raise ValueError("must not be blank")
        return value


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
    current = get_current_revision(_catalog_path(), fact_key)
    return {
        "fact_key": fact_key,
        "current": dataclasses.asdict(current) if current is not None else None,
        "history": [dataclasses.asdict(r) for r in history],
    }


@app.get("/api/candidates")
def list_candidates_endpoint() -> dict:
    results = list_corpus_candidates(_module_root())
    return {
        family: {
            "candidates": [dataclasses.asdict(c) for c in result.candidates],
            "excluded": [dataclasses.asdict(e) for e in result.excluded],
        }
        for family, result in results.items()
    }


@app.post("/api/citations")
def add_citation_endpoint(request: AddCitationRequest) -> dict:
    # FamilyNotFoundError/FamilyNotCitableError/CitationError all derive
    # from GeneratorError, so generator_error_handler() maps them to 400
    # uniformly -- no try/except needed here.
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
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


def _serialize_flagged_leaf(flagged_leaf) -> dict:
    # `outcome.raw_content` is an internal resolution artifact -- for an
    # XPathSelector it's a real lxml Element (see xpath_selector.resolve()),
    # which dataclasses.asdict() leaves untouched and FastAPI/pydantic then
    # cannot serialize at all. The frontend only ever needs outcome.status,
    # so that's all this sends.
    return {
        "leaf": dataclasses.asdict(flagged_leaf.leaf),
        "outcome": {"status": flagged_leaf.outcome.status.value},
        "drift_kind": flagged_leaf.drift_kind.value,
        "fingerprint": flagged_leaf.fingerprint,
    }


@app.get("/api/review")
def get_review_endpoint() -> dict:
    result = get_review_summary(_catalog_path(), _module_root(), _reviews_dir())
    return {
        "flagged": {
            fact_key: [_serialize_flagged_leaf(fl) for fl in entries]
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
