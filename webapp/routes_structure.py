"""Serves reporting/data.py's existing, already-tested shaping functions
against a live-materialized "current" graph -- no rewrite of that logic,
just a new data source (the store's latest run + approved corrections,
via review.current_view.materialize_current_graph) instead of a graph
handed to it once by Phase 1's CLI.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from extraction.annex_pdf import extract_name_occurrences
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
    _, _, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    # build_documentation_texts doesn't just use `occurrences` to fill in an
    # already-known-ambiguous subject's `candidates` list -- it actually
    # COMPUTES ambiguity from it (`len(set(occurrences.get(name, []))) > 1`),
    # so an empty dict here would silently misclassify every genuinely
    # ambiguous subject as unmatched instead. Re-parsing the real PDF on
    # every request is an accepted, deliberate trade-off already made
    # elsewhere in this plan (see its Global Constraints) at this project's
    # real scale, not a new performance concession introduced here.
    occurrences = extract_name_occurrences(request.app.state.latest_run.pdf_path)
    return build_documentation_texts(graph, occurrences, issues)


@router.get("/audit")
def get_audit(request: Request):
    attachment, coverage, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    return build_audit(attachment, coverage, issues)
