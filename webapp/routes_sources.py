"""The reverse-lookup and full-source-rendering endpoints Synced Panes
mode needs -- see citations.locator and provenance.reverse_lookup for
the underlying capability. Kept separate from webapp/routes_provenance.py
(which only ever answers "where did this ONE fact come from") since this
module answers the opposite direction and serves whole documents, not
per-fact crops.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response

from citations.locator import PdfLocator, XsdLocator
from citations.pdf_citation import count_pdf_pages, render_pdf_page
from provenance.reverse_lookup import find_facts_by_locator

router = APIRouter(prefix="/api/sources")


@router.get("/lookup")
def lookup(
    request: Request, kind: str, path: str | None = None, page: int | None = None,
    file: str | None = None, component: str | None = None,
):
    if kind == "pdf":
        locator = PdfLocator(path=path, page=page)
    elif kind == "xsd":
        locator = XsdLocator(file=file, component=component)
    else:
        raise ValueError(f"kind={kind!r} is not a supported source kind (expected 'pdf' or 'xsd')")

    graph_uri = request.app.state.latest_run.graph_uri
    results = find_facts_by_locator(request.app.state.dataset, graph_uri, locator)
    return [{"subject": s, "predicate": p, "object": o} for s, p, o in results]


@router.get("/pdf/page")
def get_pdf_page(path: str, page: int):
    png_bytes = render_pdf_page(path, page_number=page)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/pdf/info")
def get_pdf_info(path: str):
    return {"totalPages": count_pdf_pages(path)}


@router.get("/xsd/file")
def get_xsd_file(file: str):
    if not Path(file).exists():
        raise FileNotFoundError(f"no such file: {file}")
    return {"content": Path(file).read_text(encoding="utf-8")}
