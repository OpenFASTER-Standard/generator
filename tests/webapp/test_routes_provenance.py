import shutil

from fastapi.testclient import TestClient
from rdflib import Literal

from provenance.record import attach_provenance
from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task15"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_provenance_endpoint_returns_a_recorded_fact_and_null_for_an_untracked_one():
    # Own store path suffix -- create_app()/open_store() never explicitly
    # close the underlying Oxigraph store, so running multiple tests back
    # to back against the SAME store path can race on Oxigraph's own file
    # lock (see tests/webapp/test_routes_structure.py's own comment on this).
    store_path = STORE_PATH + "_provenance"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        from rdflib import Namespace
        EX = Namespace("https://example.org/test#")
        attach_provenance(
            app.state.dataset, graph_uri=app.state.latest_run.graph_uri,
            subject=EX.WIdNr, predicate=EX.documentation, obj=Literal("x", lang="de"),
            source_uri="citation:xsd/frag-1", generated_at="2026-09-15T14:00:00Z",
        )
        client = TestClient(app)

        found = client.get("/api/provenance", params={
            "subject": str(EX.WIdNr), "predicate": str(EX.documentation), "value": "x", "lang": "de",
        })
        assert found.status_code == 200
        # generated_at round-trips through Oxigraph as an xsd:dateTime literal,
        # which normalizes "Z" to "+00:00" -- confirmed already-documented
        # behavior, see tests/provenance/test_record.py's own assertions on
        # this same normalization (e.g. test_generated_at_time_is_stored_as_xsd_datetime_literal).
        assert found.json() == {"sourceUri": "citation:xsd/frag-1", "generatedAt": "2026-09-15T14:00:00+00:00"}

        missing = client.get("/api/provenance", params={
            "subject": str(EX.WIdNr), "predicate": str(EX.documentation), "value": "not tracked", "lang": "de",
        })
        assert missing.status_code == 200
        assert missing.json() is None
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_pdf_citation_endpoint_returns_real_png_bytes():
    store_path = STORE_PATH + "_pdf"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/pdf", params={
            "path": ANNEX_PDF, "page": 5, "x0": 60.0, "top": 60.0, "x1": 300.0, "bottom": 120.0,
        })

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 100
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_xsd_citation_endpoint_returns_the_real_fragment_and_source_file():
    store_path = STORE_PATH + "_xsd"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/xsd", params={
            "file": ROOT_XSD,
            "type_qname": "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType",
        })

        assert response.status_code == 200
        body = response.json()
        assert "MeldepflichtigeStelleType" in body["fragment"]
        assert body["sourceFile"].endswith("MiKaDiv_FM_Personentypen_1.02.xsd")
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_xsd_citation_endpoint_resolves_a_real_global_element_not_just_types():
    # Real, confirmed bug fixed alongside the local-scope resolution work:
    # this endpoint used to check ONLY schema.maps.types, so a global
    # ELEMENT's own citation (MiKaDivFMRoot -- this corpus's one real
    # global element) 404'd even though it was never locally-scoped.
    store_path = STORE_PATH + "_xsd_element"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/xsd", params={
            "file": ROOT_XSD,
            "type_qname": "{http://www.itzbund.de/MiKaDiv/FM/1.02}MiKaDivFMRoot",
        })

        assert response.status_code == 200
        body = response.json()
        assert "MiKaDivFMRoot" in body["fragment"]
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_xsd_citation_endpoint_resolves_a_real_locally_scoped_element():
    # Real, confirmed regression anchor: AOrdNr is a local xs:element
    # declaration nested inside a global complex type -- previously
    # unconditionally unresolvable by this endpoint (dotted qnames were
    # never handled at all, not even attempted).
    store_path = STORE_PATH + "_xsd_local"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/xsd", params={
            "file": ROOT_XSD,
            "type_qname": (
                "{http://www.itzbund.de/MiKaDiv/FMMa23/1.02}"
                "AmtlicheOrdnungsnummerMa23ListeType.AOrdNr"
            ),
        })

        assert response.status_code == 200
        body = response.json()
        assert 'name="AOrdNr"' in body["fragment"]
        assert "Amtliche Ordnungsnummer" in body["fragment"]
        assert body["sourceFile"].endswith("MiKaDiv_FM_Meldeart23_1.02.xsd")
    finally:
        shutil.rmtree(store_path, ignore_errors=True)
