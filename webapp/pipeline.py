"""Runs the real extraction pipeline end to end, persists everything it
produces (graph + audit artifacts) as one immutable run, and attaches
real provenance to every fact this plan can honestly source -- see this
module's own Task 18 in the plan for the exact, confirmed scope split
between global and local constructs.
"""
from __future__ import annotations

import xmlschema
from rdflib import Dataset

from citations.xsd_citation import capture_xsd_fragment
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
        x0, top, x1, bottom = matching.bbox
        source_uri = (
            f"citation:pdf?path={pdf_path}&page={matching.page_number}"
            f"&x0={x0}&top={top}&x1={x1}&bottom={bottom}"
        )
        attach_provenance(dataset, graph_uri, subject, XSDO.documentation, english, source_uri, generated_at)


def _attach_german_provenance_for_global_constructs(dataset, graph_uri, graph, schema, generated_at):
    for subject in set(graph.subjects(XSDO.documentation, None)):
        uri = str(subject)
        if "#" not in uri:
            continue
        namespace, fragment = uri.split("#", 1)
        if "." in fragment:
            continue  # locally-scoped declaration -- out of scope, see this task's own scope note
        qname = f"{{{namespace}}}{fragment}"
        component = schema.maps.types.get(qname) or schema.maps.elements.get(qname)
        if component is None:
            continue
        german = next((o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")), None)
        if german is None:
            continue
        citation = capture_xsd_fragment(component)
        source_uri = f"citation:xsd?file={citation.source_file}&component={qname}"
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
    _attach_german_provenance_for_global_constructs(dataset, info.graph_uri, graph, schema, created_at)

    return info
