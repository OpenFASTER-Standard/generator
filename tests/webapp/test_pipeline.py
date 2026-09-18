import shutil

from rdflib import URIRef

from store.database import open_store
from store.runs import list_runs, read_run_audit
from webapp.pipeline import run_pipeline_and_store

STORE_PATH = "/tmp/test_webapp_store_task13"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_run_pipeline_and_store_produces_a_real_run_with_real_audit_data():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T18:00:00Z", created_at="2026-09-15T18:00:00Z",
        )

        assert info.run_id == "2026-09-15T18:00:00Z"
        assert list_runs(dataset) == [info]

        attachment, coverage, issues = read_run_audit(dataset, "2026-09-15T18:00:00Z")
        assert coverage.total_documented_subjects > 0
        assert len(attachment.attached) > 0
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


from provenance.record import get_provenance
from rdflib import Literal
from extraction.annex_pdf import XSDO


def test_run_pipeline_and_store_attaches_real_provenance_for_matched_english_text():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T19:00:00Z", created_at="2026-09-15T19:00:00Z",
        )

        graph = dataset.graph(URIRef(info.graph_uri))
        # WIdNrTwo is a real, confirmed subject with attached English text.
        subject = next(
            s for s in graph.subjects(XSDO.name, Literal("WIdNr"))
            if any(o.language == "en" for o in graph.objects(s, XSDO.documentation))
        )
        english = next(o for o in graph.objects(subject, XSDO.documentation) if o.language == "en")

        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, english)

        assert record is not None
        assert "citation:pdf" in record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_run_pipeline_and_store_attaches_real_xsd_provenance_for_a_global_construct():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T19:00:00Z", created_at="2026-09-15T19:00:00Z",
        )

        graph = dataset.graph(URIRef(info.graph_uri))
        subject = URIRef(
            "http://www.itzbund.de/MiKaDiv/FMPers/1.02#PersonNatIdAusland45bType"
        )
        german = next(
            (o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")),
            None,
        )
        assert german is not None, "fixture assumption: this real global type has German documentation"

        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, german)

        assert record is not None
        assert "citation:xsd" in record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_run_pipeline_and_store_attaches_real_german_provenance_for_a_locally_scoped_declaration():
    # Real, confirmed regression anchor: AmtlicheOrdnungsnummerMa23ListeType.AOrdNr
    # is a local xs:element declaration (nested inside a global complex
    # type, not itself globally named) -- its German documentation used
    # to be unconditionally skipped by pipeline.py's own "." in fragment
    # check, reported as "no source recorded" in the live UI even though
    # its English documentation (a separate, PDF-based attachment path)
    # always resolved correctly. resolve_xsd_component
    # (citations/xsd_citation.py) closes this gap.
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-18T09:00:00Z", created_at="2026-09-18T09:00:00Z",
        )

        graph = dataset.graph(URIRef(info.graph_uri))
        subject = URIRef(
            "http://www.itzbund.de/MiKaDiv/FMMa23/1.02#AmtlicheOrdnungsnummerMa23ListeType.AOrdNr"
        )
        german = next(
            (o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")),
            None,
        )
        assert german is not None, "fixture assumption: this real local element has German documentation"
        assert str(german) == "Amtliche Ordnungsnummer"

        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, german)

        assert record is not None
        # attach_provenance percent-encodes source_uri before storing it as
        # a real URIRef (curly braces aren't valid unescaped URI
        # characters) -- pre-existing behavior, not introduced here; every
        # XSD citation's qname has braces, so this applied to the
        # already-working global-construct case too, just never asserted
        # on the full string before.
        assert record.source_uri == (
            "citation:xsd?file=/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
            "&component=%7Bhttp://www.itzbund.de/MiKaDiv/FMMa23/1.02%7DAmtlicheOrdnungsnummerMa23ListeType.AOrdNr"
        )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_run_pipeline_and_store_produces_the_same_source_uris_as_before_the_locator_refactor():
    # Real, confirmed regression anchor from this plan's own spec work:
    # AOrdNr's English citation is exactly this page/bbox on the real PDF.
    # This must stay byte-identical after routing source_uri construction
    # through citations.locator, since no store migration is planned --
    # every fact Plans A-D already recorded must keep resolving.
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-17T00:00:00Z", created_at="2026-09-17T00:00:00Z",
        )
        graph = dataset.graph(URIRef(info.graph_uri))
        subject = next(
            s for s in graph.subjects(XSDO.name, Literal("AOrdNr"))
            if any(o.language == "en" for o in graph.objects(s, XSDO.documentation))
        )
        english = next(o for o in graph.objects(subject, XSDO.documentation) if o.language == "en")
        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, english)
        assert record.source_uri == (
            "citation:pdf?path=/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
            "&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179"
        )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
