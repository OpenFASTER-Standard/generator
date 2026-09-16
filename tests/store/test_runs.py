import shutil

import pytest
from rdflib import BNode, Graph, Graph as PlainGraph, Literal, Namespace, URIRef

from extraction.annex_pdf import AttachmentReport
from extraction.extract import extract
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue
from store.database import open_store
from store.runs import diff_runs, list_runs, read_run_audit, write_run, write_run_audit

STORE_PATH = "/tmp/test_provenance_store_task2"
EX = Namespace("https://example.org/test#")
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
PDF_PATH = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_write_run_stores_the_graph_under_a_new_named_graph_and_returns_info():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.WIdNr, EX.documentation, Literal("German text", lang="de")))

        info = write_run(
            dataset,
            run_id="2026-09-15T14:00:00Z",
            graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T14:00:00Z",
        )

        assert info.run_id == "2026-09-15T14:00:00Z"
        assert info.xsd_hash and info.pdf_hash  # real sha256 hex digests, non-empty

        stored_graph = dataset.graph(URIRef(info.graph_uri))
        stored = list(stored_graph.triples((None, None, None)))
        assert len(stored) == 1
        assert str(stored[0][2]) == "German text"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_list_runs_returns_every_written_run_sorted_by_created_at():
    dataset = _fresh_dataset()
    try:
        write_run(
            dataset, run_id="run-b", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T09:00:00Z",
        )
        write_run(
            dataset, run_id="run-a", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T08:00:00Z",
        )

        runs = list_runs(dataset)

        assert [r.run_id for r in runs] == ["run-a", "run-b"]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_diff_runs_reports_only_added_and_removed_triples_not_unchanged_ones():
    dataset = _fresh_dataset()
    try:
        graph_a = PlainGraph()
        graph_a.add((EX.X, EX.doc, Literal("old text")))
        graph_a.add((EX.Y, EX.doc, Literal("unchanged")))
        write_run(dataset, run_id="a", graph=graph_a, xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd", pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf", created_at="t1")

        graph_b = PlainGraph()
        graph_b.add((EX.X, EX.doc, Literal("new text")))
        graph_b.add((EX.Y, EX.doc, Literal("unchanged")))
        graph_b.add((EX.Z, EX.doc, Literal("brand new")))
        write_run(dataset, run_id="b", graph=graph_b, xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd", pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf", created_at="t2")

        diff = diff_runs(dataset, "a", "b")

        removed_objects = {str(o) for (_, _, o) in diff.removed}
        added_objects = {str(o) for (_, _, o) in diff.added}
        assert removed_objects == {"old text"}
        assert added_objects == {"new text", "brand new"}
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_diff_runs_between_two_identical_real_extractions_is_empty():
    """Regression test for Critical Fix 1: extraction.extract()'s real output
    is ~42% blank nodes, freshly and randomly labeled on every call. Before
    write_run canonicalized blank-node labels via rdflib.compare.to_canonical_graph
    before copying triples into the named graph, two extract() calls on the
    identical corpus produced "added=1367, removed=1367" out of ~3270 triples
    in diff_runs -- verified live -- when the real answer should be zero
    changes. This uses the real extractor against the real root XSD, not a
    synthetic fixture, since a synthetic fixture with hand-picked blank nodes
    would not have caught this bug (it was invisible until real, heavily
    blank-node-shaped extraction output was used).
    """
    dataset = _fresh_dataset()
    try:
        graph_1 = extract(ROOT_XSD)
        graph_2 = extract(ROOT_XSD)

        # Sanity: the real corpus really does produce a substantial,
        # blank-node-heavy graph -- otherwise this test would pass
        # vacuously even with the bug present.
        assert len(graph_1) > 1000
        bnode_subjects = {s for s in graph_1.subjects() if isinstance(s, BNode)}
        assert len(bnode_subjects) > 0

        write_run(
            dataset, run_id="real-a", graph=graph_1,
            xsd_path=ROOT_XSD, pdf_path=PDF_PATH, created_at="2026-09-15T10:00:00Z",
        )
        write_run(
            dataset, run_id="real-b", graph=graph_2,
            xsd_path=ROOT_XSD, pdf_path=PDF_PATH, created_at="2026-09-15T11:00:00Z",
        )

        diff = diff_runs(dataset, "real-a", "real-b")

        assert diff.added == []
        assert diff.removed == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_write_run_raises_on_duplicate_run_id():
    """Regression test for Fix 6: write_run's own module docstring claims run
    graphs are immutable and never mutated, but nothing enforced it -- writing
    the same run_id twice used to silently merge both graphs' triples together
    and leave the index with duplicate/conflicting metadata.
    """
    dataset = _fresh_dataset()
    try:
        write_run(
            dataset, run_id="dup", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T08:00:00Z",
        )

        with pytest.raises(ValueError, match="dup"):
            write_run(
                dataset, run_id="dup", graph=Graph(),
                xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
                pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
                created_at="2026-09-15T09:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_write_run_stores_created_at_as_xsd_datetime_literal():
    """Regression test for Fix 5: the spec's own data model specifies
    prov:generatedAtTime "..."^^xsd:dateTime, but the code stored plain
    untyped/string literals for created_at."""
    from rdflib.namespace import XSD

    from store.runs import RUNS

    dataset = _fresh_dataset()
    try:
        info = write_run(
            dataset, run_id="typed-ts", graph=Graph(),
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T08:00:00Z",
        )

        index = dataset.graph(URIRef(str(RUNS["index"])))
        literal = index.value(URIRef(info.graph_uri), RUNS.createdAt)
        assert literal.datatype == XSD.dateTime
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_write_and_read_run_audit_round_trips_the_real_dataclasses():
    dataset = _fresh_dataset()
    try:
        attachment = AttachmentReport(attached=["A", "B"], ambiguous=["C"], unmatched=["D"])
        coverage = CoverageReport(total_documented_subjects=4, attached=2, ambiguous=1, unmatched=1)
        issues = [PlausibilityIssue("length_ratio", "A", "ratio=9.99", subject_uri="urn:test:A")]

        write_run_audit(dataset, run_id="run-1", attachment=attachment, coverage=coverage, issues=issues)
        read_attachment, read_coverage, read_issues = read_run_audit(dataset, run_id="run-1")

        assert read_attachment == attachment
        assert read_coverage == coverage
        assert read_issues == issues
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
