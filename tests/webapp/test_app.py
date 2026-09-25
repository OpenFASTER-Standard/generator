import json
from pathlib import Path

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
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
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


def test_list_pages_endpoint_reflects_the_current_not_the_first_revision(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    add_revision(str(catalog_path), "fact-1", leaf_1, "julian", "initial", False)
    add_revision(str(catalog_path), "fact-1", leaf_2, "julian", "corrected", True)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages")

    assert response.status_code == 200
    body = response.json()
    assert body["fact-1"]["revision_count"] == 2
    assert body["fact-1"]["current"]["comment"] == "corrected"
    assert body["fact-1"]["current"]["is_correction"] is True
    assert body["fact-1"]["current"]["reference"]["selector"]["value"] == ABGEF_XPATH


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


REAL_XSD_FAMILIES = {
    "MiKaDiv_FM",
    "MiKaDiv_FM_Fachtypen",
    "MiKaDiv_FM_Meldeart11",
    "MiKaDiv_FM_Meldeart13",
    "MiKaDiv_FM_Meldeart21",
    "MiKaDiv_FM_Meldeart22",
    "MiKaDiv_FM_Meldeart23",
    "MiKaDiv_FM_MeldeartErg",
    "MiKaDiv_FM_MeldeartenBasis",
    "MiKaDiv_FM_MeldeartenSonder",
    "MiKaDiv_FM_Personentypen",
    "MiKaDiv_FM_Standardtypen",
    "din-norm-91379-datatypes",
}


def _synthetic_corpus(tmp_path, xsd_content: str) -> str:
    module_root = tmp_path / "corpus"
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "test.xsd").write_text(xsd_content, encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"TestFamily": "test.xsd"}), encoding="utf-8"
    )
    (module_root / "_current").write_text("1.0", encoding="utf-8")
    return str(module_root)


_VALID_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Foo" type="xs:string"/>
</xs:schema>
"""

_XSD_WITHOUT_FOO = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
</xs:schema>
"""


def test_list_candidates_endpoint_returns_the_real_13_xsd_families():
    client = TestClient(app)
    response = client.get("/api/candidates")

    assert response.status_code == 200
    assert set(response.json().keys()) == REAL_XSD_FAMILIES


def test_add_citation_endpoint_creates_a_page_retrievable_via_get_pages(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-1",
        "author": "julian",
        "comment": "initial",
        "is_correction": False,
    })

    assert response.status_code == 200
    assert response.json()["fact_key"] == "fact-1"

    page_response = client.get("/api/pages/fact-1")
    assert page_response.status_code == 200
    assert page_response.json()["current"]["author"] == "julian"


def test_add_citation_endpoint_returns_400_for_unknown_family(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "NoSuchFamily",
        "xpath": "/x",
        "fact_key": "fact-2",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 400
    assert client.get("/api/pages/fact-2").status_code == 404


def test_add_citation_endpoint_returns_400_for_a_candidate_that_went_stale(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)
    client = TestClient(app)

    # The xpath is valid right now -- confirm the candidate genuinely
    # exists before making it stale underneath the same family.
    candidates = client.get("/api/candidates").json()
    assert any(c["xpath"] == "/xs:schema/xs:element[@name='Foo']" for c in candidates["TestFamily"])

    # Mutate the real underlying file so the same xpath no longer resolves
    # -- simulates a candidate going stale between listing and submission.
    (Path(module_root) / "1.0" / "test.xsd").write_text(_XSD_WITHOUT_FOO, encoding="utf-8")

    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-3",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 400
    assert client.get("/api/pages/fact-3").status_code == 404


def _corpus_with_one_healthy_and_one_broken_family(tmp_path) -> str:
    module_root = tmp_path / "corpus"
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "healthy.xsd").write_text(_VALID_XSD, encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"HealthyFamily": "healthy.xsd", "BrokenFamily": "does-not-exist.xsd"}),
        encoding="utf-8",
    )
    (module_root / "_current").write_text("1.0", encoding="utf-8")
    return str(module_root)


def test_add_citation_endpoint_rejects_a_blank_fact_key_without_creating_a_page(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "   ",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 422
    assert client.get("/api/pages").json() == {}


def test_add_citation_endpoint_rejects_a_blank_author_without_creating_a_page(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-x",
        "author": "   ",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 422
    assert client.get("/api/pages").json() == {}


def test_list_candidates_endpoint_returns_200_despite_one_broken_family_in_manifest(tmp_path, monkeypatch):
    module_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.get("/api/candidates")

    assert response.status_code == 200
    assert "HealthyFamily" in response.json()
    assert "BrokenFamily" not in response.json()


def test_add_citation_endpoint_succeeds_for_healthy_family_despite_unrelated_broken_family(tmp_path, monkeypatch):
    module_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "HealthyFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-7",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 200


def test_add_citation_endpoint_returns_400_for_a_non_xsd_family():
    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "khb_mikadiv_fm_de",
        "xpath": "/x",
        "fact_key": "fact-8",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 400
    assert client.get("/api/pages/fact-8").status_code == 404
