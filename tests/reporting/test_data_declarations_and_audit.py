"""Tests for build_declarations, build_documentation_pairs, build_audit,
and the combining build_report_data."""
from rdflib import RDF, Graph, Literal, Namespace

from extraction.annex_pdf import AttachmentReport
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue
from reporting.data import (
    XSDO,
    build_audit,
    build_declarations,
    build_documentation_pairs,
    build_report_data,
)

EX = Namespace("https://example.org/test#")


def test_build_declarations_covers_elements_and_attributes():
    graph = Graph()
    graph.add((EX.Elem, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.Elem, XSDO.name, Literal("Elem")))
    graph.add((EX.Elem, XSDO.type, EX.SomeType))
    graph.add((EX.Elem, XSDO.documentation, Literal("Deutsch.")))
    graph.add((EX.Elem, XSDO.documentation, Literal("English.", lang="en")))

    graph.add((EX.Attr, RDF.type, XSDO.AttributeDeclaration))
    graph.add((EX.Attr, XSDO.name, Literal("Attr")))
    graph.add((EX.Attr, XSDO.type, EX.SomeType))
    graph.add((EX.Attr, XSDO.defaultValue, Literal("false")))

    declarations = build_declarations(graph)

    assert declarations[str(EX.Elem)] == {
        "name": "Elem", "kind": "Element", "type": str(EX.SomeType),
        "default": None, "fixed": None,
        "documentation": {"de": "Deutsch.", "en": "English."},
    }
    assert declarations[str(EX.Attr)] == {
        "name": "Attr", "kind": "Attribute", "type": str(EX.SomeType),
        "default": "false", "fixed": None,
        "documentation": {"de": None, "en": None},
    }


def _documented(graph, uri, name, german, english=None):
    graph.add((uri, XSDO.name, Literal(name)))
    graph.add((uri, XSDO.documentation, Literal(german)))
    if english is not None:
        graph.add((uri, XSDO.documentation, Literal(english, lang="en")))


def test_documentation_pairs_groups_matched_unmatched_and_ambiguous():
    graph = Graph()
    _documented(graph, EX.Matched, "Matched", "Deutsch.", "English.")
    _documented(graph, EX.Unmatched, "Unmatched", "Nur Deutsch.")
    _documented(graph, EX.Ambiguous, "Ambiguous", "Mehrdeutig.")

    occurrences = {
        "Matched": ["English."],
        "Ambiguous": ["Meaning one.", "Meaning two."],
    }
    issues = [PlausibilityIssue("length_ratio", "Matched", "ratio=9.99")]

    pairs = build_documentation_pairs(graph, occurrences, issues)

    assert pairs["matched"] == [
        {
            "uri": str(EX.Matched), "name": "Matched", "de": "Deutsch.",
            "en": "English.", "issues": [{"kind": "length_ratio", "detail": "ratio=9.99"}],
        }
    ]
    assert pairs["unmatched"] == [
        {"uri": str(EX.Unmatched), "name": "Unmatched", "de": "Nur Deutsch."}
    ]
    assert pairs["ambiguous"] == [
        {
            "uri": str(EX.Ambiguous), "name": "Ambiguous", "de": "Mehrdeutig.",
            "candidates": ["Meaning one.", "Meaning two."],
        }
    ]


def test_build_audit_reshapes_the_already_computed_reports():
    attachment = AttachmentReport(attached=["A", "B"], ambiguous=["C"], unmatched=["D", "E", "F"])
    coverage = CoverageReport(total_documented_subjects=6, attached=2, ambiguous=1, unmatched=3)
    issues = [PlausibilityIssue("untranslated", "A", "identical text")]

    audit = build_audit(attachment, coverage, issues)

    assert audit == {
        "attachment": {"attached": 2, "ambiguous": 1, "unmatched": 3},
        "coverage": {"total": 6, "attached": 2, "ambiguous": 1, "unmatched": 3},
        "issues": [{"kind": "untranslated", "subjectName": "A", "detail": "identical text"}],
    }


def test_build_report_data_combines_all_four_sections():
    graph = Graph()
    graph.add((EX.T, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.T, XSDO.name, Literal("T")))

    data = build_report_data(
        graph,
        occurrences={},
        plausibility_issues=[],
        coverage=CoverageReport(0, 0, 0, 0),
        attachment=AttachmentReport(),
    )

    assert set(data.keys()) == {"structure", "declarations", "documentationPairs", "audit"}
    assert data["structure"]["https://example.org/test"]["simpleTypes"][0]["name"] == "T"
