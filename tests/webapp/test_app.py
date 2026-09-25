from fastapi.testclient import TestClient

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision
from webapp.app import app

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def test_list_pages_endpoint_returns_empty_object_when_catalog_is_empty(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages")

    assert response.status_code == 200
    assert response.json() == {}


def test_list_pages_endpoint_returns_real_pages_built_via_add_revision(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(str(catalog_path), "fact-1", leaf, "julian", "initial", False)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages")

    assert response.status_code == 200
    body = response.json()
    assert body["fact-1"]["revision_count"] == 1
    assert body["fact-1"]["current"]["author"] == "julian"
    assert body["fact-1"]["current"]["comment"] == "initial"


def test_get_page_endpoint_returns_full_history_for_a_real_page(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(str(catalog_path), "fact-1", leaf_1, "julian", "first", False)
    add_revision(str(catalog_path), "fact-1", leaf_1, "julian", "second", True)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages/fact-1")

    assert response.status_code == 200
    body = response.json()
    assert body["fact_key"] == "fact-1"
    assert len(body["history"]) == 2
    assert body["current"]["comment"] == "second"
    assert body["current"]["is_correction"] is True


def test_get_page_endpoint_returns_404_for_an_unknown_fact_key(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages/no-such-fact")

    assert response.status_code == 404


def test_list_pages_endpoint_returns_a_server_error_when_catalog_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "does-not-exist.json"))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/pages")

    assert response.status_code == 500


def test_static_index_page_is_served_at_root():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_old_references_endpoint_no_longer_exists():
    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 404
