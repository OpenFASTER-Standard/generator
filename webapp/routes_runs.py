"""Run history and diffing straight off `store.runs`.

An unknown `run_id` on the diff endpoint raises `store.runs`' own
`ValueError`, which `webapp.errors` -- installed once on the app --
turns into a 400; no per-route `except` here, see that module's
docstring.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from store.runs import diff_runs, list_runs

router = APIRouter(prefix="/api")


@router.get("/runs")
def get_runs(request: Request):
    return [
        {"runId": r.run_id, "createdAt": r.created_at, "xsdPath": r.xsd_path, "pdfPath": r.pdf_path}
        for r in list_runs(request.app.state.dataset)
    ]


@router.get("/runs/{run_id_a}/diff/{run_id_b}")
def get_run_diff(request: Request, run_id_a: str, run_id_b: str):
    diff = diff_runs(request.app.state.dataset, run_id_a, run_id_b)
    return {"added": diff.added, "removed": diff.removed}
