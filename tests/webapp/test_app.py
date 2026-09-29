import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus
from webapp.app import app

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
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


@requires_real_corpus
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


@requires_real_corpus
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


@requires_real_corpus
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


def test_spa_shell_is_served_at_root():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Asserts it's genuinely the built React SPA shell, not just any HTML --
    # webapp/static/index.html (a now-deleted, superseded vanilla-JS page)
    # used to also satisfy the weaker "returns text/html" check this test
    # had before, which is exactly how it went undetected as dead code.
    assert 'id="root"' in response.text


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
    corpus_root = tmp_path / "corpus"
    snapshot_dir = corpus_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "test.xsd").write_text(xsd_content, encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"TestFamily": "test.xsd"}), encoding="utf-8"
    )
    (corpus_root / "_current").write_text("1.0", encoding="utf-8")
    return str(corpus_root)


_VALID_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Foo" type="xs:string"/>
</xs:schema>
"""

_XSD_WITHOUT_FOO = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
</xs:schema>
"""


@requires_real_corpus
def test_list_candidates_endpoint_returns_the_real_13_xsd_families(monkeypatch):
    # Explicit, not relying on DEFAULT_CORPUS_ROOT happening to already
    # equal REAL_CORPUS_ROOT (which itself is overridable via
    # MIKADIV_CORPUS_ROOT) -- this test's whole point is real data, so it
    # says so directly rather than coincidentally getting it from a default.
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", REAL_CORPUS_ROOT)
    client = TestClient(app)
    response = client.get("/api/candidates")

    assert response.status_code == 200
    # <=, not ==: the real corpus is a separate repo this one doesn't
    # control -- an upstream family addition shouldn't break this test.
    assert REAL_XSD_FAMILIES <= set(response.json().keys())
    for family_result in response.json().values():
        assert set(family_result.keys()) == {"candidates", "excluded"}


def test_list_candidates_endpoint_surfaces_excluded_candidates(tmp_path, monkeypatch):
    corpus_root = _synthetic_corpus(
        tmp_path,
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:vendor="urn:vendor">'
        '<wrapper><xs:element name="Decoy" type="xs:string"/></wrapper>'
        '<vendor:wrapper><xs:element name="Decoy" type="xs:string"/></vendor:wrapper>'
        "</xs:schema>",
    )
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)
    client = TestClient(app)

    response = client.get("/api/candidates")

    body = response.json()["TestFamily"]
    assert len(body["candidates"]) == 1
    assert len(body["excluded"]) == 1
    assert body["excluded"][0]["name"] == "Decoy"


def test_add_citation_endpoint_creates_a_page_retrievable_via_get_pages(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    corpus_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

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
    corpus_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

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
    corpus_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)
    client = TestClient(app)

    # The xpath is valid right now -- confirm the candidate genuinely
    # exists before making it stale underneath the same family.
    candidates = client.get("/api/candidates").json()
    assert any(c["xpath"] == "/xs:schema/xs:element[@name='Foo']" for c in candidates["TestFamily"]["candidates"])

    # Mutate the real underlying file so the same xpath no longer resolves
    # -- simulates a candidate going stale between listing and submission.
    (Path(corpus_root) / "1.0" / "test.xsd").write_text(_XSD_WITHOUT_FOO, encoding="utf-8")

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
    corpus_root = tmp_path / "corpus"
    snapshot_dir = corpus_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "healthy.xsd").write_text(_VALID_XSD, encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"HealthyFamily": "healthy.xsd", "BrokenFamily": "does-not-exist.xsd"}),
        encoding="utf-8",
    )
    (corpus_root / "_current").write_text("1.0", encoding="utf-8")
    return str(corpus_root)


def test_add_citation_endpoint_rejects_a_blank_fact_key_without_creating_a_page(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    corpus_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

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
    corpus_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

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
    corpus_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

    client = TestClient(app)
    response = client.get("/api/candidates")

    assert response.status_code == 200
    assert "HealthyFamily" in response.json()
    assert "BrokenFamily" not in response.json()


def test_add_citation_endpoint_succeeds_for_healthy_family_despite_unrelated_broken_family(tmp_path, monkeypatch):
    corpus_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", corpus_root)

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


@requires_real_corpus
def test_add_citation_endpoint_returns_400_for_a_non_xsd_family(monkeypatch):
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", REAL_CORPUS_ROOT)
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


def test_get_review_returns_deserialization_failures_separately(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps({
        "bad-key": [{
            "revision_id": "x", "reference": {"not": "real"},
            "author": "a", "comment": "c", "is_correction": False, "created_at": "2026-01-01T00:00:00+00:00",
        }]
    }))
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.get("/api/review")

    assert response.status_code == 200
    assert response.json()["deserialization_failures"] == ["bad-key"]


def test_post_reviews_rejects_a_leaf_reference_id_that_is_not_currently_flagged(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.post("/api/reviews", json={
        "fact_key": "no-such-key", "leaf_reference_id": "does-not-exist",
        "reviewer": "r", "verdict": "approved", "reasoning": "x",
    })

    assert response.status_code == 404


def test_post_reviews_rejects_an_invalid_verdict_string(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "references.json"))
    (tmp_path / "references.json").write_text("{}")
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.post("/api/reviews", json={
        "fact_key": "k", "leaf_reference_id": "r", "reviewer": "r", "verdict": "maybe", "reasoning": "x",
    })

    assert response.status_code == 400


def test_post_reviews_rejects_a_blank_reviewer_or_reasoning(tmp_path, monkeypatch):
    # A review's whole point is accountability -- a blank reviewer or
    # reasoning would permanently suppress a drift finding with no record
    # of who did it or why. AddCitationRequest already rejects a blank
    # author for the same reason (see its own _reject_blank validator);
    # SubmitReviewRequest must too.
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "references.json"))
    (tmp_path / "references.json").write_text("{}")
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    blank_reviewer = client.post("/api/reviews", json={
        "fact_key": "k", "leaf_reference_id": "r", "reviewer": "  ", "verdict": "approved", "reasoning": "x",
    })
    assert blank_reviewer.status_code == 422

    blank_reasoning = client.post("/api/reviews", json={
        "fact_key": "k", "leaf_reference_id": "r", "reviewer": "r", "verdict": "approved", "reasoning": "   ",
    })
    assert blank_reasoning.status_code == 422


def test_a_generator_error_maps_uniformly_to_its_own_http_status_with_a_real_detail_message(tmp_path, monkeypatch):
    # 2026-09-29 audit finding: only POST /api/citations mapped its domain
    # errors to a meaningful HTTP status; every other endpoint either
    # 500'd generically (masking a message like "<path>: not valid JSON")
    # or didn't map at all. GeneratorError's single exception_handler fixes
    # this for every endpoint at once -- exercised here via a corrupted
    # reviews_dir file reaching GET /api/review, which is not
    # POST /api/citations' own special-cased path.
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir()
    (reviews_dir / "corrupt.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(reviews_dir))
    client = TestClient(app)

    response = client.get("/api/review")

    assert response.status_code == 500
    assert "not valid JSON" in response.json()["detail"]


def test_get_candidates_maps_a_corpus_integrity_error_to_500_with_a_real_detail_message(tmp_path, monkeypatch):
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    (corpus_root / "_current").write_text("../escapes-module-root", encoding="utf-8")
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", str(corpus_root))
    client = TestClient(app)

    response = client.get("/api/candidates")

    assert response.status_code == 500
    assert "escapes corpus_root" in response.json()["detail"]


@requires_real_corpus
def test_get_review_serializes_a_real_content_drift_leaf_without_500(tmp_path, monkeypatch):
    # Real bug, found during manual Playwright verification: for an
    # XPathSelector, ResolutionOutcome.raw_content on a RESOLVED/CONTENT-drift
    # leaf is a real lxml Element (see xpath_selector.resolve()) --
    # dataclasses.asdict(FlaggedLeaf) leaves that object in place, and
    # FastAPI/pydantic then can't serialize it, so this endpoint 500s for
    # every genuine CONTENT-drift XPath finding, not just a contrived one.
    corpus_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_CORPUS_ROOT, corpus_root)
    xsd_path = corpus_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd"
    original = xsd_path.read_text(encoding="utf-8")
    # Change an attribute's documentation text -- the element named by the
    # xpath still resolves (no structural drift), but its canonical content
    # hash changes, which is exactly what produces a CONTENT-drift FlaggedLeaf.
    mutated = original.replace(
        'name="AOrdNr"', 'name="AOrdNr" fixed="drift-test"', 1
    )
    assert mutated != original
    xsd_path.write_text(mutated, encoding="utf-8")

    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(str(catalog_path), "fact-drift", leaf, "julian", "initial", False)

    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_CORPUS_ROOT", str(corpus_root))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.get("/api/review")

    assert response.status_code == 200
    flagged = response.json()["flagged"]["fact-drift"]
    assert len(flagged) == 1
    assert flagged[0]["drift_kind"] == "CONTENT"


def test_get_review_isolates_one_unexpected_check_failure_from_every_other_page(tmp_path, monkeypatch):
    # Real regression found in a whole-branch review: staleness_sweep.sweep()
    # had no per-reference error isolation, so an unexpected exception
    # while checking ANY ONE page (the exact shape of the real C14NError
    # bug the same review found) 500'd this endpoint for every OTHER,
    # healthy page too.
    from dataclasses import dataclass

    from reference_model.model import ContentHash, Leaf, ResolutionOutcome, Status, compute_leaf_reference_id
    from reference_model.registry import Resolver, register, unregister

    @dataclass(frozen=True)
    class _ExplodingSelector:
        type: str
        value: str

    register(
        "ExplodingSelectorForWebappTest",
        Resolver(
            resolve=lambda s, u: ResolutionOutcome(status=Status.RESOLVED, raw_content="x"),
            canonicalize_and_hash=lambda c: (_ for _ in ()).throw(RuntimeError("boom")),
            selector_cls=_ExplodingSelector,
        ),
    )
    try:
        catalog_path = tmp_path / "references.json"
        catalog_path.write_text("{}", encoding="utf-8")
        healthy_leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
        add_revision(str(catalog_path), "healthy-fact", healthy_leaf, "julian", "initial", False)

        exploding_selector = _ExplodingSelector(type="ExplodingSelectorForWebappTest", value="/x")
        exploding_leaf = Leaf(
            reference_id=compute_leaf_reference_id("MiKaDiv_FM_Meldeart23", exploding_selector),
            subject_document=_subject_document(),
            selector=exploding_selector,
            content_hash=ContentHash(algorithm="sha256", digest="0" * 64),
            captured_at="2026-01-01T00:00:00Z",
        )
        add_revision(str(catalog_path), "exploding-fact", exploding_leaf, "julian", "initial", False)

        monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
        monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
        client = TestClient(app)

        response = client.get("/api/review")

        assert response.status_code == 200
        assert "exploding-fact" in [f["key"] for f in response.json()["check_failures"]]
        # The healthy page is entirely unaffected -- neither flagged nor excluded.
        assert "healthy-fact" not in response.json()["flagged"]
        assert "healthy-fact" not in response.json()["excluded_keys"]
    finally:
        unregister("ExplodingSelectorForWebappTest")


def test_a_real_api_404_is_not_masked_by_the_spa_fallback(tmp_path, monkeypatch):
    # Explicit tmp_path catalog like every other test in this file, rather
    # than silently depending on the real committed catalog file existing
    # (and being valid JSON) at DEFAULT_CATALOG_PATH -- this test's own
    # behavior (a missing fact_key 404s as JSON, not HTML) doesn't need
    # real content at all.
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    client = TestClient(app)
    response = client.get("/api/pages/does-not-exist-at-all")
    assert response.status_code == 404
    assert response.json()["detail"]  # a real JSON error body, not HTML


def test_an_unknown_non_api_path_gets_the_spa_shell():
    # No catalog/corpus fixture needed here (unlike its neighbor above) --
    # the SPA-fallback route never touches either; it only serves the
    # already-built frontend_dist/index.html straight off disk.
    client = TestClient(app)
    response = client.get("/pages/whatever-react-router-will-own")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
