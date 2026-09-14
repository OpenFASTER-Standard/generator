"""Tests for plausibility checks on attached (German, English)
documentation pairs -- and for real coverage visibility into how many
of the real corpus's documented subjects actually got a match."""
from rdflib import RDF, Graph, Literal, Namespace

from extraction.annex_pdf import extract_name_occurrences
from extraction.translation_plausibility import (
    XSDO,
    check_translation_coverage,
    check_translation_plausibility,
)

EX = Namespace("https://example.org/test/")
ANNEX_PDF = "ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def _documented(graph, subject, german, english):
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("Test")))
    graph.add((subject, XSDO.documentation, Literal(german)))
    graph.add((subject, XSDO.documentation, Literal(english, lang="en")))


def test_plausible_pair_produces_no_issues():
    graph = Graph()
    _documented(
        graph, EX.Good,
        "Eindeutiger Identifier für die Nachricht.",
        "Unique identifier for the message.",
    )

    assert check_translation_plausibility(graph) == []


def test_wildly_short_english_text_is_flagged_by_length_ratio():
    graph = Graph()
    _documented(
        graph, EX.TooShort,
        "Eindeutiger Identifier für die Nachricht, der niemals doppelt vergeben wird.",
        "ID.",
    )

    issues = check_translation_plausibility(graph)

    assert any(i.kind == "length_ratio" and i.subject_name == "Test" for i in issues)


def test_dropped_legal_reference_is_flagged_by_missing_shared_token():
    graph = Graph()
    _documented(
        graph, EX.DroppedRef,
        "Meldung nach § 45b Absatz 6 EStG.",
        "A report under the relevant provision of the tax code.",
    )

    issues = check_translation_plausibility(graph)

    assert any(i.kind == "missing_shared_token" and "45b" in i.detail for i in issues)


def test_real_stray_fragment_found_during_this_plan_is_flagged():
    # "letzten Position)." -- a real, confirmed stray German fragment this
    # plan's own design found attached to the bare name "Typ" in one real
    # PDF pass; the real English text it should have been paired with is
    # a full English sentence, so the fragment fails both heuristics.
    graph = Graph()
    _documented(
        graph, EX.StrayFragment,
        "Gibt an, ob es sich um eine Erst- oder eine Berichtigungsmeldung handelt.",
        "letzten Position).",
    )

    issues = check_translation_plausibility(graph)

    assert any(i.subject_name == "Test" for i in issues)


def test_coverage_report_counts_every_real_documented_subject():
    graph = Graph()
    matched = EX.Matched
    graph.add((matched, RDF.type, XSDO.AttributeDeclaration))
    graph.add((matched, XSDO.name, Literal("NachrichtUUID")))
    graph.add((matched, XSDO.documentation, Literal("Eindeutiger Identifier.")))

    ambiguous = EX.Ambiguous
    graph.add((ambiguous, RDF.type, XSDO.AttributeDeclaration))
    graph.add((ambiguous, XSDO.name, Literal("Bezeichnung")))
    graph.add((ambiguous, XSDO.documentation, Literal("Bezeichnung.")))

    unmatched = EX.Unmatched
    graph.add((unmatched, RDF.type, XSDO.AttributeDeclaration))
    graph.add((unmatched, XSDO.name, Literal("NotInThePdf")))
    graph.add((unmatched, XSDO.documentation, Literal("Nicht im PDF.")))

    occurrences = extract_name_occurrences(ANNEX_PDF)

    report = check_translation_coverage(graph, occurrences)

    assert report.total_documented_subjects == 3
    assert report.attached == 1
    assert report.ambiguous == 1
    assert report.unmatched == 1
