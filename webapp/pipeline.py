"""Runs the real extraction pipeline end to end, persists everything it
produces (graph + audit artifacts) as one immutable run, and attaches
real provenance to every fact this plan can honestly source. German/XSD
provenance originally covered only globally-named constructs (Plan C's
own Task 18 scope limit); citations.xsd_citation.resolve_xsd_component
closed that gap by resolving locally-scoped declarations (element/
attribute declarations, and anonymous types, nested inside a global
type) back to their real xmlschema object too -- see that function's own
docstring for the real, confirmed scale of what was excluded before
(239 of 377 documented subjects in this corpus).
"""
from __future__ import annotations

import xmlschema
from rdflib import Dataset

from citations.locator import PdfLocator, XsdLocator, locator_to_source_uri
from citations.xsd_citation import capture_xsd_fragment, resolve_xsd_component
from extraction.annex_pdf import XSDO, attach_english_documentation, extract_name_occurrences_with_pages
from extraction.extract import extract
from extraction.translation_plausibility import check_translation_coverage, check_translation_plausibility
from provenance.record import attach_provenance
from store.runs import RunInfo, write_run, write_run_audit


def _attach_english_provenance(dataset, graph_uri, graph, occurrences_with_pages, pdf_path, generated_at):
    for subject in set(graph.subjects(XSDO.documentation, None)):
        name_literal = graph.value(subject, XSDO.name)
        if name_literal is None:
            continue
        english = next((o for o in graph.objects(subject, XSDO.documentation) if o.language == "en"), None)
        if english is None:
            continue
        matching = next(
            (c for c in occurrences_with_pages.get(str(name_literal), []) if c.text == str(english)), None,
        )
        if matching is None:
            continue
        source_uri = locator_to_source_uri(
            PdfLocator(path=pdf_path, page=matching.page_number, bbox=matching.bbox)
        )
        attach_provenance(dataset, graph_uri, subject, XSDO.documentation, english, source_uri, generated_at)


def _attach_german_provenance(dataset, graph_uri, graph, schema, generated_at):
    # Covers both globally-named constructs (a bare qname, e.g.
    # "{ns}SomeType") and locally-scoped declarations nested inside one
    # (a dotted qname, e.g. "{ns}SomeType.LocalElement.@LocalAttribute")
    # -- resolve_xsd_component (citations/xsd_citation.py) walks either
    # shape back to the real xmlschema object. Previously this only
    # handled the bare-qname case and unconditionally skipped anything
    # with a "." in it, which -- confirmed real -- was the majority of
    # this corpus's documented subjects (239 of 377), not an edge case.
    for subject in set(graph.subjects(XSDO.documentation, None)):
        uri = str(subject)
        if "#" not in uri:
            continue
        namespace, fragment = uri.split("#", 1)
        qname = f"{{{namespace}}}{fragment}"
        component = resolve_xsd_component(schema, qname)
        if component is None:
            continue
        german = next((o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")), None)
        if german is None:
            continue
        citation = capture_xsd_fragment(component)
        source_uri = locator_to_source_uri(XsdLocator(file=citation.source_file, component=qname))
        attach_provenance(dataset, graph_uri, subject, XSDO.documentation, german, source_uri, generated_at)


def run_pipeline_and_store(
    dataset: Dataset, xsd_path: str, pdf_path: str, run_id: str, created_at: str
) -> RunInfo:
    graph = extract(xsd_path)
    attachment = attach_english_documentation(graph, pdf_path)
    occurrences_with_pages = extract_name_occurrences_with_pages(pdf_path)
    coverage = check_translation_coverage(graph, {n: [c.text for c in cs] for n, cs in occurrences_with_pages.items()})
    issues = check_translation_plausibility(graph)

    info = write_run(dataset, run_id=run_id, graph=graph, xsd_path=xsd_path, pdf_path=pdf_path, created_at=created_at)
    write_run_audit(dataset, run_id=run_id, attachment=attachment, coverage=coverage, issues=issues)

    _attach_english_provenance(dataset, info.graph_uri, graph, occurrences_with_pages, pdf_path, created_at)
    schema = xmlschema.XMLSchema(xsd_path)
    _attach_german_provenance(dataset, info.graph_uri, graph, schema, created_at)

    return info
