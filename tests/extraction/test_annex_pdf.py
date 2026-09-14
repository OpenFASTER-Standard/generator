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
