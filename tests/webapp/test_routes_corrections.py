import base64
import shutil

from fastapi.testclient import TestClient
from rdflib import Namespace

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task17"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")


def _encode(uri: str) -> str:
    return base64.urlsafe_b64encode(uri.encode()).decode()


def test_propose_then_approve_by_a_different_reviewer_succeeds():
    store_path = STORE_PATH + "_approve"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        assert proposal.status_code == 200
        correction_uri = proposal.json()["correctionUri"]

        approval = client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "looks right"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert approval.status_code == 200
        assert "decisionUri" in approval.json()
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_self_approval_returns_400():
    store_path = STORE_PATH + "_self_approval"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        correction_uri = proposal.json()["correctionUri"]

        approval = client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "self-approving"},
            headers={"X-Reviewer": "julian"},
        )
        assert approval.status_code == 400
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_reject_by_a_different_reviewer_succeeds():
    store_path = STORE_PATH + "_reject"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        correction_uri = proposal.json()["correctionUri"]

        rejection = client.post(
            f"/api/corrections/{_encode(correction_uri)}/reject",
            json={"reason": "not needed"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert rejection.status_code == 200
        assert "decisionUri" in rejection.json()
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_deciding_an_unknown_correction_returns_400_not_500():
    store_path = STORE_PATH + "_unknown"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        approval = client.post(
            f"/api/corrections/{_encode('https://example.org/does-not-exist')}/approve",
            json={"reason": "looks right"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert approval.status_code == 400
    finally:
        shutil.rmtree(store_path, ignore_errors=True)


def test_deciding_an_already_decided_correction_returns_400_not_500():
    store_path = STORE_PATH + "_already_decided"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        correction_uri = proposal.json()["correctionUri"]

        first = client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "looks right"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert first.status_code == 200

        second = client.post(
            f"/api/corrections/{_encode(correction_uri)}/reject",
            json={"reason": "changed my mind"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert second.status_code == 400
    finally:
        shutil.rmtree(store_path, ignore_errors=True)
