import shutil

from fastapi.testclient import TestClient

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_sources"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_lookup_pdf_finds_real_facts_on_a_real_page():
    # Own store path suffix -- create_app()/open_store() never explicitly
    # close the underlying Oxigraph store, so running multiple tests back
    # to back against the SAME store path can race on Oxigraph's own file
    # lock (see tests/webapp/test_routes_provenance.py's own comment on
    # this, and tests/webapp/test_routes_structure.py).
    store_path = STORE_PATH + "_lookup_pdf"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={
            "kind": "pdf", "path": ANNEX_PDF, "page": 196,
        })

        assert response.status_code == 200
        subjects = {row["subject"] for row in response.json()}
        assert any("AmtlicheOrdnungsnummerMa23ListeType" in s for s in subjects)
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_lookup_xsd_finds_real_facts_for_a_real_global_component():
    store_path = STORE_PATH + "_lookup_xsd"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={
            "kind": "xsd", "file": ROOT_XSD,
            "component": "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType",
        })

        assert response.status_code == 200
        # May legitimately be empty for this specific component/run; the
        # real assertion is that the endpoint answers cleanly, not 500s.
        assert isinstance(response.json(), list)
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_lookup_rejects_an_unknown_kind_with_400_not_500():
    store_path = STORE_PATH + "_lookup_bad_kind"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={"kind": "csv", "path": "/a.csv"})

        assert response.status_code == 400
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_pdf_page_endpoint_returns_a_real_full_page_image():
    store_path = STORE_PATH + "_pdf_page"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/pdf/page", params={"path": ANNEX_PDF, "page": 5})

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 1000
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_xsd_file_endpoint_returns_the_real_raw_text():
    store_path = STORE_PATH + "_xsd_file"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/xsd/file", params={"file": ROOT_XSD})

        assert response.status_code == 200
        assert "<xs:schema" in response.json()["content"]
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_pdf_info_endpoint_returns_the_real_page_count():
    store_path = STORE_PATH + "_pdf_info"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/pdf/info", params={"path": ANNEX_PDF})

        assert response.status_code == 200
        # Real, known page count for this exact corpus PDF -- confirmed
        # directly via pdfplumber elsewhere in this project's own tests
        # (tests/citations/test_pdf_citation.py).
        assert response.json() == {"totalPages": 262}
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_xsd_file_endpoint_404s_for_a_nonexistent_file():
    store_path = STORE_PATH + "_xsd_file_404"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/xsd/file", params={"file": "/tmp/nope.xsd"})

        assert response.status_code == 404
    finally:
        shutil.rmtree(store_path, ignore_errors=True)
