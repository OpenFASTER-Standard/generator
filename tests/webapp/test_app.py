import json

from fastapi.testclient import TestClient

from webapp.app import app


def test_returns_empty_object_when_catalog_is_empty(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 200
    assert response.json() == {}


def test_returns_the_catalogs_real_content_when_populated(tmp_path, monkeypatch):
    fixture = {
        "fact-1": {
            "reference_id": "abc123",
            "subject_document": {
                "family": "MiKaDiv_FM_Meldeart23",
                "version": "1.02",
                "retrieval_uri": "/some/path.xsd",
            },
            "selector": {"type": "XPathSelector", "value": "/xs:schema"},
            "content_hash": {"algorithm": "sha256", "digest": "deadbeef"},
            "captured_at": "2026-09-24T00:00:00+00:00",
        }
    }
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 200
    assert response.json() == fixture


def test_returns_a_server_error_when_catalog_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "does-not-exist.json"))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/references")

    assert response.status_code == 500


def test_static_index_page_is_served_at_root():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
