"""Provenance lookups and real inline citations -- an actual PDF page
crop or an actual XSD source fragment, not a re-typed string. Citation
endpoints take raw locator parameters (path/page/bbox, or file/qname)
rather than an opaque citation id -- there is no separate citation-blob
store in this first cut; each is computed on request from the real
source file, which is cheap (a single page crop / a single component
lookup) and keeps this endpoint's own state trivial.

Bad input on any of these endpoints (a nonexistent path, an unknown XSD
component, an out-of-range page, a malformed IRI or language tag) is
translated to a clean 4xx by `webapp.errors`, installed once on the app
-- no per-route `except` ladder here, see that module's docstring.
"""
from __future__ import annotations

import xmlschema
from fastapi import APIRouter, Request, Response
from rdflib import Literal

from citations.pdf_citation import crop_pdf_page
from citations.xsd_citation import capture_xsd_fragment
from provenance.record import get_provenance
from webapp.errors import validated_iri

router = APIRouter(prefix="/api")


@router.get("/provenance")
def get_provenance_route(request: Request, subject: str, predicate: str, value: str, lang: str | None = None):
    graph_uri = request.app.state.latest_run.graph_uri
    # validated_iri, not a bare URIRef(): see webapp.errors.validated_iri
    # for why this boundary check is kept even though the underlying
    # SPARQL construction was separately confirmed non-exploitable.
    subject_term = validated_iri(subject, "subject")
    predicate_term = validated_iri(predicate, "predicate")
    obj = Literal(value, lang=lang) if lang else Literal(value)
    record = get_provenance(request.app.state.dataset, graph_uri, subject_term, predicate_term, obj)
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
