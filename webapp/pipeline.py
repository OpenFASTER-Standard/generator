"""Runs the real extraction pipeline end to end and persists everything
it produces (graph + audit artifacts) as one immutable run -- the same
4 real function calls Phase 1's CLI (reporting/__main__.py) already made,
just writing into the store instead of building an HTML file directly.
"""
from __future__ import annotations

from rdflib import Dataset

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.translation_plausibility import check_translation_coverage, check_translation_plausibility
from store.runs import RunInfo, write_run, write_run_audit


def run_pipeline_and_store(
    dataset: Dataset, xsd_path: str, pdf_path: str, run_id: str, created_at: str
) -> RunInfo:
    graph = extract(xsd_path)
    attachment = attach_english_documentation(graph, pdf_path)
    occurrences = extract_name_occurrences(pdf_path)
    coverage = check_translation_coverage(graph, occurrences)
    issues = check_translation_plausibility(graph)

    info = write_run(dataset, run_id=run_id, graph=graph, xsd_path=xsd_path, pdf_path=pdf_path, created_at=created_at)
    write_run_audit(dataset, run_id=run_id, attachment=attachment, coverage=coverage, issues=issues)
    return info
