"""Serves reporting/data.py's existing, already-tested shaping functions
against a live-materialized "current" graph -- no rewrite of that logic,
just a new data source (the store's latest run + approved corrections,
via review.current_view.materialize_current_graph) instead of a graph
handed to it once by Phase 1's CLI.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from reporting.data import build_audit, build_declarations, build_documentation_texts, build_structure
from review.current_view import materialize_current_graph
from store.runs import read_run_audit

router = APIRouter(prefix="/api")


def _current_graph(request: Request):
    state = request.app.state
    return materialize_current_graph(state.dataset, state.latest_run.graph_uri, state.corrections_graph_uri)


@router.get("/structure")
def get_structure(request: Request):
    return build_structure(_current_graph(request))


@router.get("/declarations")
def get_declarations(request: Request):
    return build_declarations(_current_graph(request))


@router.get("/documentation")
def get_documentation(request: Request):
    graph = _current_graph(request)
    attachment, _, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    occurrences: dict[str, list[str]] = {}  # ambiguity candidates are re-derived from the audit's own issues below
    return build_documentation_texts(graph, occurrences, issues)


@router.get("/audit")
def get_audit(request: Request):
    attachment, coverage, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    return build_audit(attachment, coverage, issues)
