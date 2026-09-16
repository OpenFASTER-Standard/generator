import shutil

from fastapi.testclient import TestClient

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task14"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_structure_declarations_documentation_audit_endpoints_return_real_data():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        structure = client.get("/api/structure")
        assert structure.status_code == 200
        assert len(structure.json()) > 0

        declarations = client.get("/api/declarations")
        assert declarations.status_code == 200
        assert len(declarations.json()) > 0

        documentation = client.get("/api/documentation")
        assert documentation.status_code == 200
        assert set(documentation.json().keys()) == {"matched", "unmatched", "ambiguous", "englishOnly"}

        audit = client.get("/api/audit")
        assert audit.status_code == 200
        assert audit.json()["coverage"]["total"] > 0
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
