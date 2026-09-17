"""Every previously-raw-500 path across all four webapp/routes_*.py
modules, now translated to a clean status by the single app-level
handler set in webapp/errors.py.

These four route modules each accumulated their own version of the same
gap during Tasks 14-17 (no handling at all in routes_structure, an
unguarded xmlschema/pdfplumber call in routes_provenance, a bare
ValueError in routes_runs, a missing `except` on propose in
routes_corrections). They are tested together, in one file, on purpose:
the fix is deliberately ONE mechanism shared by all of them rather than
four per-module `except` ladders, so the regression guard belongs in one
place too -- and any future route module gets covered by the same
handler without a new test file.

One module-scoped app (not one per test): create_app() runs the real
full pipeline -- a whole XSD family plus a 262-page PDF -- so a
per-test app would multiply this file's runtime by its test count for
no added coverage. It also sidesteps the Oxigraph store-lock race the
other webapp test modules work around with per-test store paths (see
tests/webapp/test_routes_structure.py's own comment), since only one
store is ever opened here.
"""
import base64
import shutil

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph, Literal, Namespace

from store.runs import write_run
from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_error_handling"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")

# A real, confirmed global type in this corpus -- the happy-path control
# for the two XSD-citation failure cases below.
REAL_QNAME = "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType"


@pytest.fixture(scope="module")
def client():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
    # raise_server_exceptions=False is what makes this file a real
    # regression guard: with the default (True), an UNHANDLED exception is
    # re-raised into the test instead of becoming a response, so a test
    # asserting "not 500" would error out rather than fail with a useful
    # diff. With it off, an unhandled exception surfaces as the actual 500
    # these assertions are guarding against.
    yield TestClient(app, raise_server_exceptions=False)
    shutil.rmtree(STORE_PATH, ignore_errors=True)


def _pdf_params(**overrides):
    params = {"path": ANNEX_PDF, "page": 5, "x0": 60.0, "top": 60.0, "x1": 300.0, "bottom": 120.0}
    params.update(overrides)
    return params


# --- routes_provenance.py -------------------------------------------------


def test_xsd_citation_for_an_unknown_component_is_404_not_500(client):
    response = client.get("/api/citations/xsd", params={"file": ROOT_XSD, "type_qname": "{urn:nope}Nope"})
    assert response.status_code == 404
    assert "unknown XSD component" in response.json()["detail"]


def test_xsd_citation_for_a_nonexistent_file_is_400_not_500(client):
    response = client.get("/api/citations/xsd", params={"file": "/tmp/nope.xsd", "type_qname": REAL_QNAME})
    assert response.status_code == 400


def test_xsd_citation_for_a_file_that_is_not_a_schema_is_400_not_500(client):
    # A real file that really exists but really is not an XSD -- this is a
    # different xmlschema exception (XMLResourceParseError) from the
    # missing-file case above (XMLResourceOSError), and both must land on
    # the same clean status.
    response = client.get("/api/citations/xsd", params={"file": ANNEX_PDF, "type_qname": REAL_QNAME})
    assert response.status_code == 400


def test_pdf_citation_for_a_nonexistent_path_is_404_not_500(client):
    response = client.get("/api/citations/pdf", params=_pdf_params(path="/tmp/nope.pdf"))
    assert response.status_code == 404


def test_pdf_citation_for_a_file_that_is_not_a_pdf_is_400_not_500(client):
    response = client.get("/api/citations/pdf", params=_pdf_params(path=ROOT_XSD))
    assert response.status_code == 400
    assert "invalid PDF source" in response.json()["detail"]


def test_pdf_citation_for_an_out_of_range_page_is_400_not_500(client):
    response = client.get("/api/citations/pdf", params=_pdf_params(page=99999))
    assert response.status_code == 400


def test_provenance_for_a_malformed_subject_iri_is_400_not_500(client):
    # A real SPARQL-injection-shaped payload. It was already confirmed
    # non-exploitable (rdflib refuses to serialize it long before any
    # query text is built, see webapp.errors.validated_iri) -- but rdflib
    # signals that with a BARE `Exception`, which no type-based handler
    # can catch without swallowing genuine bugs, so it used to surface as
    # a raw 500. The boundary check turns it into the 400 it always was.
    response = client.get("/api/provenance", params={
        "subject": "urn:a> ?p ?o } ; DROP ALL ; SELECT * WHERE { <x",
        "predicate": "urn:p", "value": "v",
    })
    assert response.status_code == 400
    assert "not a valid IRI" in response.json()["detail"]


def test_provenance_for_a_malformed_language_tag_is_400_not_500(client):
    response = client.get("/api/provenance", params={
        "subject": str(EX.A), "predicate": str(EX.doc), "value": "v", "lang": "not a lang",
    })
    assert response.status_code == 400


def test_provenance_still_answers_a_well_formed_but_untracked_fact_with_null(client):
    # Guard against the handlers above over-reaching: "no provenance
    # recorded" is a legitimate 200/null answer, not an error.
    response = client.get("/api/provenance", params={
        "subject": str(EX.A), "predicate": str(EX.doc), "value": "v", "lang": "de",
    })
    assert response.status_code == 200
    assert response.json() is None


# --- routes_runs.py -------------------------------------------------------


def test_diffing_an_unknown_run_id_is_4xx_not_500(client):
    response = client.get("/api/runs/no-such-run/diff/also-no-such-run")
    assert 400 <= response.status_code < 500
    assert "no run with run_id" in response.json()["detail"]


# --- routes_corrections.py ------------------------------------------------


def test_proposing_with_a_malformed_target_iri_is_400_not_500(client):
    response = client.post("/api/corrections", json={
        "targetSubject": "urn:a> ?p ?o } #", "targetPredicate": str(EX.doc),
        "targetLanguage": "de", "proposedValue": "x", "priorValue": "y", "reason": "r",
    }, headers={"X-Reviewer": "alice"})
    assert response.status_code == 400
    assert "not a valid IRI" in response.json()["detail"]


def test_proposing_with_a_malformed_language_tag_is_400_not_500(client):
    # The concrete gap the task-level reviews flagged: propose() had no
    # `except ValueError` guard at all, unlike approve()/reject().
    response = client.post("/api/corrections", json={
        "targetSubject": str(EX.A), "targetPredicate": str(EX.doc),
        "targetLanguage": "not a lang", "proposedValue": "x", "priorValue": "y", "reason": "r",
    }, headers={"X-Reviewer": "alice"})
    assert response.status_code == 400


def test_deciding_with_a_garbage_base64_path_segment_is_400_not_500(client):
    response = client.post("/api/corrections/!!!not-base64!!!/approve",
                           json={"reason": "r"}, headers={"X-Reviewer": "bob"})
    assert response.status_code == 400


def test_approve_and_reject_still_return_400_after_losing_their_own_try_except(client):
    # approve()/reject() used to catch ValueError themselves; that guard was
    # removed in favour of the shared handler. This is the regression guard
    # that the shared handler really does cover what they used to.
    encoded = base64.urlsafe_b64encode(b"https://example.org/does-not-exist").decode()
    for outcome in ("approve", "reject"):
        response = client.post(f"/api/corrections/{encoded}/{outcome}",
                               json={"reason": "r"}, headers={"X-Reviewer": "bob"})
        assert response.status_code == 400, outcome


# --- routes_structure.py --------------------------------------------------


def test_all_four_structure_endpoints_stay_200_under_the_shared_handler(client):
    # routes_structure.py's four endpoints take no caller input at all --
    # every parameter they use comes from app.state -- so unlike the other
    # three modules they have no reachable 4xx path to assert. What they DO
    # need guarding is the opposite direction: that installing app-level
    # handlers for ValueError/OSError/TypeError did not start swallowing
    # their real, successful responses.
    for path in ("/api/structure", "/api/declarations", "/api/documentation", "/api/audit"):
        assert client.get(path).status_code == 200, path


def test_a_run_with_no_stored_audit_is_an_honest_500_not_a_misleading_400(client):
    """`read_run_audit` raises `json.JSONDecodeError` -- a `ValueError`
    subclass -- when a run was written by `write_run` alone, with no
    `write_run_audit` alongside it (real and reachable: any run created
    outside `webapp.pipeline`). The generic `ValueError -> 400` rule would
    blame the caller for what is purely server-side state, so
    `webapp.errors` gives that one exception its own explicit 500.
    """
    app = client.app
    graph = Graph()
    graph.add((EX.NewSubject, EX.newFact, Literal("no audit for this run")))
    info = write_run(app.state.dataset, run_id="audit-less-run", graph=graph,
                     xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF, created_at="2026-09-18T00:00:00Z")
    previous = app.state.latest_run
    app.state.latest_run = info
    try:
        response = client.get("/api/audit")
        assert response.status_code == 500
        assert "no stored audit artifacts" in response.json()["detail"]
    finally:
        app.state.latest_run = previous
