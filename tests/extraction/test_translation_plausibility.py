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


def test_structural_pdf_artifact_leaking_into_english_text_is_flagged():
    # Real, confirmed-live text (pre-fix) for the real name "Ergebnis": a
    # "simpleType" heading-detection gap in extraction.annex_pdf let a
    # neighboring simpleType section's own heading/documentation lines
    # silently concatenate onto this name's correct English sentence. This
    # test grounds the structural-artifact check's token choices in that
    # real corrupted text rather than a synthetic guess, and exists as
    # defense-in-depth: it must still catch this shape of corruption even
    # though the root cause is now fixed in extraction.annex_pdf.
    graph = Graph()
    _documented(
        graph, EX.StructuralLeak,
        "Rückgabewert zur Prüfung dieser Person.",
        "Return value for verifying this person. simpleType AuslandSteuerNr "
        "Namespace http://www.itzbund.de/MiKaDiv/FMStd/1.02 Type restriction "
        "ofstd:NameType Attributes PersonNatAuslandStNrType/@AuslandIdNr The "
        "person's tax identification number assigned by the country of "
        "residence.",
    )

    issues = check_translation_plausibility(graph)

    assert any(i.kind == "structural_artifact" and i.subject_name == "Test" for i in issues)


def test_genuine_prose_is_not_flagged_as_a_structural_artifact():
    graph = Graph()
    _documented(
        graph, EX.GenuineProse,
        "Die Namensangabe des Wertpapiers muss eindeutig sein.",
        "The name specification of the security must be unambiguous.",
    )

    issues = check_translation_plausibility(graph)

    assert not any(i.kind == "structural_artifact" for i in issues)


def test_extra_english_only_token_is_flagged_by_extra_shared_token():
    # Fix 2 (final whole-branch review): the reverse-direction counterpart
    # to missing_shared_token -- reconstructs the real page-footer bug's
    # shape (a stray trailing page number appended only to the English
    # text, e.g. real pre-fix "Official serial number. 196").
    graph = Graph()
    _documented(
        graph, EX.StrayPageNumber,
        "Amtliche Ordnungsnummer.",
        "Official serial number. 196",
    )

    issues = check_translation_plausibility(graph)

    assert any(
        i.kind == "extra_shared_token" and i.subject_name == "Test" and "196" in i.detail
        for i in issues
    )


def test_extra_shared_token_stays_silent_on_genuine_matched_prose():
    graph = Graph()
    _documented(
        graph, EX.GenuineProse,
        "Meldung nach § 45b Absatz 6 EStG.",
        "Report pursuant to section 45b (6) EStG.",
    )

    issues = check_translation_plausibility(graph)

    assert not any(i.kind == "extra_shared_token" for i in issues)


def test_byte_identical_untranslated_pair_is_flagged():
    # Fix 4 (final whole-branch review): a real, confirmed-live untranslated
    # source entry -- BruttoBescheinigteSteuern's real German sentence,
    # attached verbatim (still German) as if it were the English text.
    graph = Graph()
    _documented(
        graph, EX.Untranslated,
        "Liste aller Bruttobeträge bescheinigter Steuern.",
        "Liste aller Bruttobeträge bescheinigter Steuern.",
    )

    issues = check_translation_plausibility(graph)

    assert any(i.kind == "untranslated" and i.subject_name == "Test" for i in issues)


def test_acronym_shaped_identical_pair_is_not_flagged_as_untranslated():
    # COAF is a real, confirmed exception: its own real German
    # xs:documentation is already the English phrase "Corporate Action
    # Event Reference." (an untranslated technical loanword, not a gap) --
    # confirmed directly in MiKaDiv_FM_Fachtypen_1.02.xsd.
    graph = Graph()
    subject = EX.Coaf
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("COAF")))
    graph.add((subject, XSDO.documentation, Literal("Corporate Action Event Reference.")))
    graph.add(
        (subject, XSDO.documentation, Literal("Corporate Action Event Reference.", lang="en"))
    )

    issues = check_translation_plausibility(graph)

    assert not any(i.kind == "untranslated" for i in issues)


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
