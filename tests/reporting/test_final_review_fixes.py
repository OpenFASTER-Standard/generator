"""Regression tests for the 5 findings from the final whole-branch review
of docs/plans/2026-09-15-generator-output-report.md (see that plan's own
.superpowers/sdd/.../progress.md ledger for the full write-up of each
finding). Only the 3 findings with real, testable Python-side logic get
tests here (Fix 1, Fix 2, Fix 5) -- Fix 3 (search) and Fix 4 (unreferenced
declarations) are pure reporting/assets/report.js changes, verified
instead via a real-browser Playwright check against the real regenerated
report (see the final fix report for that evidence).

Fix 5's own mitigation was later replaced: PlausibilityIssue gained a real
subject_uri field (a follow-up requested directly by the operator, who
wanted the ambiguity resolved precisely rather than worked around), so
these tests assert the new, precise per-URI attribution instead of the
old per-name ambiguity-avoidance behavior.
"""
import json

from rdflib import RDF, Graph, Literal, Namespace

from extraction.annex_pdf import AttachmentReport
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue
from reporting.data import (
    XSDO,
    build_audit,
    build_documentation_texts,
    build_report_data,
)

EX = Namespace("https://example.org/test#")


def _documented(graph, uri, name, german=None, english=None):
    graph.add((uri, XSDO.name, Literal(name)))
    if german is not None:
        graph.add((uri, XSDO.documentation, Literal(german)))
    if english is not None:
        graph.add((uri, XSDO.documentation, Literal(english, lang="en")))


# --- Fix 1: English-only subjects must not be silently dropped -------------


def test_english_only_subject_appears_in_new_group_not_dropped():
    graph = Graph()
    _documented(graph, EX.EnglishOnly, "EnglishOnly", german=None, english="Documentati on")
    _documented(graph, EX.Matched, "Matched", german="Deutsch.", english="English.")

    texts = build_documentation_texts(graph, occurrences={}, plausibility_issues=[])

    assert "englishOnly" in texts
    assert texts["englishOnly"] == [
        {
            "uri": str(EX.EnglishOnly), "name": "EnglishOnly",
            "languages": {"en": "Documentati on"},
        }
    ]
    # It must not also show up, or otherwise vanish from, any other group.
    assert texts["englishOnly"] not in (texts["matched"], texts["unmatched"], texts["ambiguous"])
    all_names = {p["name"] for group in texts.values() for p in group}
    assert "EnglishOnly" in all_names


def test_documentation_texts_group_counts_reconcile_with_total_documented_subjects():
    """Every real subject with ANY xsdo:documentation triple (the same
    universe check_translation_coverage's own CoverageReport.total_documented_subjects
    counts) must land in exactly one of the 4 groups -- this is the real
    §2/§3 numeric-reconciliation bug from the final review (377 rendered
    vs 380 real)."""
    graph = Graph()
    _documented(graph, EX.M, "M", german="Deutsch.", english="English.")
    _documented(graph, EX.U, "U", german="Nur Deutsch.")
    _documented(graph, EX.A1, "A", german="Mehrdeutig.")
    _documented(graph, EX.EO, "EnglishOnly", german=None, english="Only English.")

    occurrences = {"A": ["Meaning one.", "Meaning two."]}
    texts = build_documentation_texts(graph, occurrences, plausibility_issues=[])

    total_in_groups = sum(len(v) for v in texts.values())
    documented_subjects = set(graph.subjects(XSDO.documentation, None))
    assert total_in_groups == len(documented_subjects) == 4


# --- Fix 2: deterministic ordering ------------------------------------------


def test_documentation_texts_groups_are_sorted_by_name_then_uri():
    graph = Graph()
    # Insert in deliberately non-alphabetical order.
    _documented(graph, EX.Zebra, "Zebra", german="Z.", english="Z.")
    _documented(graph, EX.Apple, "Apple", german="A.", english="A.")
    _documented(graph, EX.Mango, "Mango", german="M.", english="M.")

    texts = build_documentation_texts(graph, occurrences={}, plausibility_issues=[])

    names = [p["name"] for p in texts["matched"]]
    assert names == sorted(names) == ["Apple", "Mango", "Zebra"]


def test_build_audit_issues_are_sorted_by_subject_name_then_kind():
    attachment = AttachmentReport()
    coverage = CoverageReport(0, 0, 0, 0)
    issues = [
        PlausibilityIssue("length_ratio", "Zebra", "z"),
        PlausibilityIssue("untranslated", "Apple", "a2"),
        PlausibilityIssue("empty", "Apple", "a1"),
    ]

    audit = build_audit(attachment, coverage, issues)

    ordered = [(i["subjectName"], i["kind"]) for i in audit["issues"]]
    assert ordered == sorted(ordered)
    assert ordered == [("Apple", "empty"), ("Apple", "untranslated"), ("Zebra", "length_ratio")]


def test_build_report_data_is_byte_identical_across_repeated_calls():
    """Calling build_report_data twice on the exact same inputs, in the
    same process, must produce byte-identical JSON. (A weaker guard than
    a cross-process/cross-PYTHONHASHSEED run -- see the final fix report
    for that stronger, manually-run verification -- but a real, cheap,
    always-on regression test that would have caught a re-introduced
    unsorted set() iteration if the sets involved had non-trivial size.)
    """
    graph = Graph()
    for i in range(10):
        _documented(graph, EX[f"Subj{i}"], f"Subj{i}", german=f"DE{i}", english=f"EN{i}")
    graph.add((EX.T, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.T, XSDO.name, Literal("T")))

    issues = [
        PlausibilityIssue("length_ratio", f"Subj{i}", f"ratio {i}", subject_uri=str(EX[f"Subj{i}"]))
        for i in range(10)
    ]
    coverage = CoverageReport(10, 10, 0, 0)
    attachment = AttachmentReport(attached=[f"Subj{i}" for i in range(10)])

    first = build_report_data(graph, occurrences={}, plausibility_issues=issues,
                               coverage=coverage, attachment=attachment)
    second = build_report_data(graph, occurrences={}, plausibility_issues=issues,
                                coverage=coverage, attachment=attachment)

    assert json.dumps(first, sort_keys=False) == json.dumps(second, sort_keys=False)


# --- Fix 5 (superseded): an issue for a name shared by 2+ matched subjects --
# PlausibilityIssue now carries a real subject_uri (a follow-up requested
# directly by the operator instead of the original name-based mitigation
# below), so these tests assert precise, correct per-URI attribution.


def test_issue_with_a_real_subject_uri_attaches_to_exactly_the_right_subject():
    """Real-corpus shape: WIdNr names 2 distinct matched subjects
    (MeldepflichtigeStelleType.@WIdNr, IdMerkmalNNPType.@WIdNr) with
    different real text lengths. Now that PlausibilityIssue carries a real
    URI, the one real length_ratio issue must attach to exactly the
    subject it's actually about, not to both and not to neither."""
    graph = Graph()
    _documented(graph, EX.WIdNrOne, "WIdNr", german="Kurze Wirtschafts-ID.",
                english="Short economic ID.")
    _documented(graph, EX.WIdNrTwo, "WIdNr",
                german="Eine viel, viel, viel laengere Wirtschafts-Identifikationsnummer.",
                english="A much, much, much longer economic identification number.")
    issues = [
        PlausibilityIssue("length_ratio", "WIdNr", "ratio=9.99", subject_uri=str(EX.WIdNrOne))
    ]

    texts = build_documentation_texts(graph, occurrences={}, plausibility_issues=issues)

    by_uri = {p["uri"]: p for p in texts["matched"]}
    assert by_uri[str(EX.WIdNrOne)]["issues"] == [{"kind": "length_ratio", "detail": "ratio=9.99"}]
    assert by_uri[str(EX.WIdNrTwo)]["issues"] == []

    # The flat §3 issue list is unaffected -- it never claimed per-subject
    # scoping on its own, so the real issue must still be visible there too.
    audit = build_audit(AttachmentReport(), CoverageReport(2, 2, 0, 0), issues)
    assert audit["issues"] == [
        {
            "kind": "length_ratio", "subjectName": "WIdNr", "detail": "ratio=9.99",
            "subjectUri": str(EX.WIdNrOne),
        }
    ]


def test_issue_for_a_uniquely_named_matched_subject_is_still_attached():
    """Sanity check: a name held by exactly one matched subject must still
    get its real issue(s)."""
    graph = Graph()
    _documented(graph, EX.Solo, "Solo", german="Deutsch.", english="English.")
    issues = [PlausibilityIssue("length_ratio", "Solo", "ratio=9.99", subject_uri=str(EX.Solo))]

    texts = build_documentation_texts(graph, occurrences={}, plausibility_issues=issues)

    assert texts["matched"] == [
        {
            "uri": str(EX.Solo), "name": "Solo", "languages": {"de": "Deutsch.", "en": "English."},
            "issues": [{"kind": "length_ratio", "detail": "ratio=9.99"}],
        }
    ]
