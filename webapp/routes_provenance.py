"""Provenance lookups and real inline citations -- an actual PDF page
crop or an actual XSD source fragment, not a re-typed string. Citation
endpoints take raw locator parameters (path/page/bbox, or file/qname)
rather than an opaque citation id -- there is no separate citation-blob
store in this first cut; each is computed on request from the real
source file, which is cheap (a single page crop / a single component
lookup) and keeps this endpoint's own state trivial.
"""
from __future__ import annotations

import xmlschema
from fastapi import APIRouter, Request, Response
from rdflib import Literal, URIRef

from citations.pdf_citation import crop_pdf_page
from citations.xsd_citation import capture_xsd_fragment
from provenance.record import get_provenance

router = APIRouter(prefix="/api")


@router.get("/provenance")
def get_provenance_route(request: Request, subject: str, predicate: str, value: str, lang: str | None = None):
    graph_uri = request.app.state.latest_run.graph_uri
    obj = Literal(value, lang=lang) if lang else Literal(value)
    record = get_provenance(request.app.state.dataset, graph_uri, URIRef(subject), URIRef(predicate), obj)
    if record is None:
        return None
    return {"sourceUri": record.source_uri, "generatedAt": record.generated_at}


@router.get("/citations/pdf")
def get_pdf_citation(path: str, page: int, x0: float, top: float, x1: float, bottom: float):
    png_bytes = crop_pdf_page(path, page_number=page, bbox=(x0, top, x1, bottom))
    return Response(content=png_bytes, media_type="image/png")


@router.get("/citations/xsd")
def get_xsd_citation(file: str, type_qname: str):
    schema = xmlschema.XMLSchema(file)
    component = schema.maps.types[type_qname]
    citation = capture_xsd_fragment(component)
    return {"fragment": citation.fragment, "sourceFile": citation.source_file}
