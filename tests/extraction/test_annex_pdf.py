"""Tests for English documentation extraction from the real Annex PDF,
matched by name against an already-extracted graph -- including the
real ambiguity-safety gate: a name whose real PDF occurrences
genuinely disagree is reported, never guessed."""
from rdflib import Graph, Literal, Namespace, RDF

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.uris import global_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
ROOT_XSD = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"

FM = "http://www.itzbund.de/MiKaDiv/FM/1.02"


def test_root_elements_english_documentation_is_attached_alongside_german():
    graph = extract(ROOT_XSD)
    root_uri = global_uri(FM, "MiKaDivFMRoot")

    report = attach_english_documentation(graph, ANNEX_PDF)

    docs = {(str(d), d.language) for d in graph.objects(root_uri, XSDO.documentation)}
    assert ("Root-Element für die Nutzdaten.", None) in docs
    assert ("Root element for the user data.", "en") in docs
    assert "MiKaDivFMRoot" in report.attached


def test_wrapped_multi_line_documentation_is_joined_into_one_string():
    graph = extract(ROOT_XSD)
    # NachrichtUUID is a local attribute of the anonymous MeldungListe45bType
    # extension chain -- easiest to locate via a fresh, minimal fixture graph
    # instead of threading through the real nesting. It is also, per the
    # real corpus, one name repeated identically across many real sections
    # (7 real occurrences, all "Unique identifier for the message.") -- a
    # real, confirmed *non*-ambiguous repeat, distinct from the genuinely
    # ambiguous names this task must instead refuse to attach.
    subject = global_uri(FM, "NachrichtUUID")
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("NachrichtUUID")))

    report = attach_english_documentation(graph, ANNEX_PDF)

    english_docs = [d for d in graph.objects(subject, XSDO.documentation) if d.language == "en"]
    assert len(english_docs) == 1
    assert str(english_docs[0]) == "Unique identifier for the message."
    assert "NachrichtUUID" in report.attached


def test_a_name_not_present_in_the_pdf_gets_no_english_documentation():
    graph = Graph()
    subject = global_uri(FM, "SomeNameNotInThePdf")
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("SomeNameNotInThePdf")))

    report = attach_english_documentation(graph, ANNEX_PDF)

    assert list(graph.objects(subject, XSDO.documentation)) == []
    assert "SomeNameNotInThePdf" in report.unmatched


def test_a_name_with_genuinely_conflicting_real_text_is_not_attached():
    # Bezeichnung is real, confirmed ambiguous: mostly "The non-natural
    # person's name." but also genuinely "Designation of the class of
    # securities." elsewhere in the real corpus -- two different real
    # meanings sharing one bare local name.
    graph = Graph()
    subject = global_uri(FM, "Bezeichnung")
    graph.add((subject, RDF.type, XSDO.AttributeDeclaration))
    graph.add((subject, XSDO.name, Literal("Bezeichnung")))

    report = attach_english_documentation(graph, ANNEX_PDF)

    assert list(graph.objects(subject, XSDO.documentation)) == []
    assert "Bezeichnung" in report.ambiguous


def test_extract_name_occurrences_keeps_every_distinct_real_text_uncollapsed():
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert set(occurrences["NachrichtUUID"]) == {"Unique identifier for the message."}
    assert len(occurrences["Bezeichnung"]) > 1
    assert len(set(occurrences["Bezeichnung"])) > 1


def test_two_line_wrapped_element_headings_still_resolve_to_their_real_name():
    # Real artifact confirmed on pages 213-214: a long element path doesn't
    # fit on its own heading line and wraps onto the very next visual line
    # at the same left margin instead ("element" alone, then
    # "SelbststaendigeMeldungMitOrdnungsnummerType/KontoListe/
    # BescheinigteSteuern" on the next line, and likewise for .../Konto/
    # Paymentlines). Before the fix, this crashed extract_name_occurrences
    # with an IndexError in _heading_trailing_name (heading == "element",
    # no name to split off) -- confirmed exactly 2 real occurrences of this
    # wrap across the whole 262-page document, both asserted here.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert occurrences["BescheinigteSteuern"] == ["List of all certified taxes."]
    assert "Paymentlines" in occurrences


def test_identity_constraints_table_header_is_not_misread_as_an_attributes_header():
    # Real artifact confirmed on page 163 (element Meldeart13/KontoListe's own
    # unique constraint "EindeutigesKonto"): an Identity-constraints table's
    # own header line ("Name Refer Selector Field(s) Documentation") contains
    # both "Name" and "Documentation" just like a real Attributes table header
    # ("Name Type Use Default Documentation") does -- a bare "Name" + has-
    # "Documentation" check can't tell the two apart, and would wrongly start
    # reading the identity-constraint's own field rows as attribute rows,
    # fabricating a spurious "EindeutigesKonto" occurrence out of the
    # constraint's own free-text description ("A constraint that ensures
    # that the type of securities account and the account number together
    # are unique.") -- confirmed by reproducing the bug directly against a
    # copy of this module with the old, looser header condition.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert "EindeutigesKonto" not in occurrences
    assert occurrences["KontoListe"] == [
        "Type for a list of up to 20 accounts.",
        "Type for a list of up to 20 accounts.",
    ]


def test_attributes_header_is_still_recognized_when_use_and_default_are_split_across_lines():
    # Real artifact confirmed on at least 17 real pages (170, 172, 187, 191,
    # 202, 218, 226, 240, 242, 245, 257, 258, 259 among them): a real
    # Attributes table header ("Name Type Use Default Documentation") can
    # have "Use"/"Default"/"Documentation" truncated on the header's own
    # line (e.g. "Us"/"Defa"/"Documentation", or "Us"/"Defaul"/"Documentati")
    # with the missing suffix fragments ("e"/"ult", "t"/"on", etc.) landing
    # on the very next visual line, past an intervening "Attributes" label
    # line -- same species of rendering bug as the already-known
    # "Documentatio"+"n" split, just hitting different words. Requiring the
    # literal tokens "Type"/"Use" in the header line (the fix for the
    # Identity-constraints false-positive) would otherwise never recognize
    # these real Attributes headers at all, silently dropping every real
    # attribute on those pages into AttachmentReport.unmatched. Both
    # "HinterlegungsstelleMelder" (pages 172/226/242) and "Verhaeltnis"
    # (page 226) are real attributes only reachable if this split header is
    # still correctly recognized as a real Attributes table.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert occurrences["HinterlegungsstelleMelder"] == [
        'If "HinterlegungsstelleM elder" is true, the "Hinterlegungsstelle" '
        'element must not be specified. If False, "Hinterlegungsstelle" must '
        "be provided."
    ] * 3
    assert occurrences["Verhaeltnis"] == [
        "The ratio of depositary receipts stipulated in the issue conditions "
        "of the depositary receipt (page 1) to the domestic securities stored "
        "by the German depositary (x-page must be specified here)."
    ] * 3


def test_a_real_attribute_row_split_across_two_lines_is_not_read_as_two_names():
    # Real artifact confirmed on pages 173/226/243: a real attribute row's
    # own Name (and Type) column value can itself be split across two
    # lines, the same rendering bug as the header-word splits above, just
    # hitting a row's own data instead: "HinterlegungsscheineGesamtz" +
    # "ahl" -> "HinterlegungsscheineGesamtzahl". Before this fix, the
    # lowercase continuation fragment "ahl" was misread as the *name* of a
    # brand new row, silently discarding the real (truncated, still-doc-less)
    # "HinterlegungsscheineGesamtz" row and instead filing the row's real
    # documentation under the garbage key "ahl".
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert occurrences["HinterlegungsscheineGesamtzahl"] == [
        "Total number of depositary receipts issued at the date of the "
        "profit distribution resolution."
    ] * 3
    assert "ahl" not in occurrences
    assert "HinterlegungsscheineGesamtz" not in occurrences


def test_simpletype_headings_start_their_own_section_instead_of_being_swallowed():
    # Real, confirmed-live corruption found by Task 8's own plausibility
    # audit (translation_plausibility.py): the heading-detection branch only
    # recognized "element"/"complexType" as heading-start tokens, never
    # "simpleType" -- even though the real PDF has 44 real simpleType
    # headings (pages 63-75, 155-156, 205, 215, 259-260). A simpleType
    # heading that was never recognized as a section boundary fell through
    # into the TRAILING_DOC branch and got silently appended onto the
    # *prior* heading's own documentation instead of starting fresh.
    #
    # Two real, confirmed-corrupted names before this fix:
    # - "Ergebnis" (a real simpleType, own real German doc is "Rückgabewert
    #   zur Prüfung dieser Person.", 39 chars): its correct one-sentence
    #   English text ("Return value for verifying this person.") had ~30
    #   unrelated subsequent simpleType sections' headings and documentation
    #   silently concatenated onto it, growing to 7951 chars.
    # - "Zugang" (never itself a real simpleType/element/complexType heading
    #   in this PDF -- the name never legitimately occurs in occurrences at
    #   all): before this fix it wrongly picked up 741 chars of unrelated
    #   text about KnotenpositionType/WertpapierArtType/WertpapierhandelArtType
    #   that had spilled out of a neighboring, wrongly-unbounded accumulation.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert occurrences["Ergebnis"] == ["Return value for verifying this person."]
    assert "Zugang" not in occurrences

    # The simpleType sections whose content used to leak into "Ergebnis" now
    # each keep their own, correctly short, un-concatenated documentation.
    assert occurrences["AuslandSteuerNr"][0] == (
        "The person's tax identification number assigned by the country "
        "of residence."
    )
    assert occurrences["KnotenpositionType"] == [
        "Non-negative, numeric integer value for specifying positions "
        "within a custody chain.."
    ]
    assert occurrences["WertpapierArtType"] == [
        "Type used to define the type of securities."
    ]


def test_page_footer_page_numbers_no_longer_leak_into_attached_documentation():
    # Fix 2 (final whole-branch review, Critical bug): TRAILING_DOC's own
    # accumulation didn't recognize a page's own footer (a lone page-number
    # line near the bottom of the page) and appended it straight onto the
    # current heading's documentation -- confirmed real, pre-fix corrupted
    # text for at least 13 real names, 3 of them asserted directly here.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    assert occurrences["AOrdNr"] == ["Official serial number."]
    assert occurrences["Abgaenge"] == ["Information on securities sold."]
    assert occurrences["AbgefKapitalertragsteuer"] == [
        "Withheld capital income tax pursuant to section 44 (1a) EStG."
    ]


def test_names_that_only_differed_by_a_trailing_page_number_are_no_longer_falsely_ambiguous():
    # Fix 2: before the page-footer fix, these real names' otherwise
    # byte-identical occurrences disagreed only in their trailing page
    # number, fabricating false ambiguity -- attach_english_documentation
    # would refuse to attach a real, genuinely unambiguous translation.
    occurrences = extract_name_occurrences(ANNEX_PDF)

    for name in ("Adresse", "Anschrift", "Miteigentuemer", "NichtNatAuslandNoStNr"):
        distinct_texts = set(occurrences[name])
        assert len(distinct_texts) == 1, f"{name} unexpectedly still ambiguous: {distinct_texts}"
