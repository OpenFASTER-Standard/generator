import shutil

from rdflib import Literal, Namespace, URIRef

from citations.locator import PdfLocator, XsdLocator
from provenance.record import attach_provenance
from provenance.reverse_lookup import find_facts_by_locator
from store.database import open_store
from store.runs import write_run
from rdflib import Graph

STORE_PATH = "/tmp/test_reverse_lookup_store"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_find_facts_by_locator_finds_a_pdf_fact_by_page_ignoring_bbox():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectA, EX.documentation, Literal("hello", lang="en")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectA, EX.documentation, Literal("hello", lang="en"),
            source_uri="citation:pdf?path=/a.pdf&page=5&x0=1&top=2&x1=3&bottom=4",
            generated_at="2026-09-17T00:00:00Z",
        )

        # A locator for the SAME page, DIFFERENT bbox -- must still match,
        # since PDF reverse lookup is page-level, not exact-region.
        locator = PdfLocator(path="/a.pdf", page=5, bbox=(999.0, 999.0, 1000.0, 1000.0))
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == [(str(EX.SubjectA), str(EX.documentation), "hello")]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_does_not_match_a_different_page_with_a_shared_numeric_prefix():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectB, EX.documentation, Literal("world", lang="en")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectB, EX.documentation, Literal("world", lang="en"),
            source_uri="citation:pdf?path=/a.pdf&page=1960&x0=1&top=2&x1=3&bottom=4",
            generated_at="2026-09-17T00:00:00Z",
        )

        locator = PdfLocator(path="/a.pdf", page=196)
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_finds_an_xsd_fact_by_exact_component():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectC, EX.documentation, Literal("Deutsch.", lang="de")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectC, EX.documentation, Literal("Deutsch.", lang="de"),
            source_uri="citation:xsd?file=/a.xsd&component={urn:ns}TypeName",
            generated_at="2026-09-17T00:00:00Z",
        )

        locator = XsdLocator(file="/a.xsd", component="{urn:ns}TypeName")
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == [(str(EX.SubjectC), str(EX.documentation), "Deutsch.")]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_returns_empty_list_when_nothing_matches():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        locator = PdfLocator(path="/nowhere.pdf", page=1)
        assert find_facts_by_locator(dataset, info.graph_uri, locator) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
