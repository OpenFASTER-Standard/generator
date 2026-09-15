"""Fix 5 (final whole-branch review): a real, automated whole-corpus
regression test.

Before this file, every plausibility/coverage test used a small,
synthetic 1-3-subject graph -- the only whole-corpus verification was a
manual step in the plan (Task 8 Step 5) that a human/agent had to
remember to run by hand. All 3 of this branch's worst bugs (two
regressions found during Task 7, and the cross-task content-model
duplication bug found during the final review's own whole-corpus scan)
were found by manual whole-corpus runs, never by a unit test.

This test runs the FULL real pipeline -- extraction.extract.extract on
the real MiKaDiv_FM_1.02.xsd, extraction.annex_pdf.attach_english_documentation
against the real Annex PDF, then check_translation_coverage/
check_translation_plausibility -- and asserts real, meaningful
properties of the result against a real, reviewed post-fix baseline
(computed directly from this branch's own final-fix-report, NOT the
stale pre-fix numbers in the sub-project's ledger).

The 32 plausibility issues asserted below were reviewed individually
during the final fix wave (see final-fix-report.md's Fix 5 section) and
confirmed to be genuine, pre-existing real-source quirks -- legitimate
translation differences (e.g. German "JJJJ"/English "YYYY" date-format
placeholders, "BMF" spelled out in English as "Federal Ministry of
Finance", numeric vs. spelled-out dates) or real word-spacing artifacts
already present in the official Annex PDF's own rendering (e.g. "length
of45" merging "of" and "45" with no space) -- not bugs introduced by, or
fixable from, this extraction package. If a future change to the real
XSD/PDF fixtures or to extraction code changes this list, that's a
signal to re-review, not to blindly update the assertion.
"""
from __future__ import annotations

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.translation_plausibility import (
    check_translation_coverage,
    check_translation_plausibility,
)

ROOT_XSD = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"

# Real, reviewed post-fix baseline (kind, xsdo:name) pairs -- see this
# module's own docstring. Anything NOT in this set is a new, unreviewed
# issue and must fail loudly rather than being silently absorbed into a
# vague "some issues exist" assertion.
_KNOWN_REVIEWED_ISSUES = {
    ("extra_shared_token", "AuszahlendeStelle"),
    ("extra_shared_token", "LEIType"),
    ("extra_shared_token", "Meldejahr"),
    ("length_ratio", "WIdNr"),
    ("missing_shared_token", "LEIType"),
    ("missing_shared_token", "Meldejahr"),
    ("missing_shared_token", "Name256Type"),
    ("missing_shared_token", "Name45Type"),
    ("missing_shared_token", "StueckzahlKapitalertraege"),
    ("missing_shared_token", "StueckzahlKompensationszahlungenBelastet"),
    ("missing_shared_token", "StueckzahlKompensationszahlungenGutgeschrieben"),
    ("missing_shared_token", "StueckzahlMitFinanzvereinbarung"),
    ("missing_shared_token", "StueckzahlOhneFinanzvereinbarung"),
    ("untranslated", "AusschuettendeGesellschaft"),
    ("untranslated", "BruttoBescheinigteSteuern"),
    ("untranslated", "DepotfuehrendeStellePositionType"),
    ("untranslated", "ErtragsGruppe45cType"),
    ("untranslated", "GemeldeteSteuern"),
    ("untranslated", "Hinterlegungsstelle"),
    ("untranslated", "KapEStRechtsgrundlage"),
    ("untranslated", "KapEStSteuersatz"),
    ("untranslated", "KapitalertragType"),
    ("untranslated", "Paymentline45BBasisType"),
    ("untranslated", "PaymentlineBasisType"),
    ("untranslated", "PaymentlineListeMa11ErgType"),
    ("untranslated", "PaymentlineMa11ErgType"),
    ("untranslated", "SolzSteuersatz"),
    ("untranslated", "SteuerangabenMitSteuersatzUndRechtsgrundlageType"),
    ("untranslated", "SteuerangabenType"),
    ("untranslated", "StueckzahlenType"),
    ("untranslated", "VerwahrketteType"),
    ("untranslated", "Wertpapier"),
}


def test_whole_real_corpus_pipeline_end_to_end():
    graph = extract(ROOT_XSD)
    report = attach_english_documentation(graph, ANNEX_PDF)
    occurrences = extract_name_occurrences(ANNEX_PDF)
    coverage = check_translation_coverage(graph, occurrences)
    issues = check_translation_plausibility(graph)

    # Real post-fix coverage baseline (final whole-branch review, Fix 5).
    # Fix 3 (type/identity-constraint documentation + xsdo:name) roughly
    # doubled `attached` versus the pre-fix ledger by newly reaching
    # type-level English descriptions that were already sitting unattached
    # in the PDF's parsed output; Fix 2 (page-footer numbers) additionally
    # resolved 4 real names that used to be falsely ambiguous.
    assert len(report.attached) == 294
    assert len(report.ambiguous) == 68
    assert len(report.unmatched) == 53
    assert coverage.total_documented_subjects == 380
    assert coverage.attached == 294
    assert coverage.ambiguous == 68
    assert coverage.unmatched == 18

    actual_pairs = {(issue.kind, issue.subject_name) for issue in issues}
    unexpected = actual_pairs - _KNOWN_REVIEWED_ISSUES
    assert not unexpected, f"new, unreviewed plausibility issue(s): {sorted(unexpected)}"

    resolved = _KNOWN_REVIEWED_ISSUES - actual_pairs
    assert not resolved, (
        f"previously-known issue(s) no longer reproduce -- if genuinely "
        f"fixed, remove from _KNOWN_REVIEWED_ISSUES: {sorted(resolved)}"
    )

    assert len(issues) == len(_KNOWN_REVIEWED_ISSUES) == 32
