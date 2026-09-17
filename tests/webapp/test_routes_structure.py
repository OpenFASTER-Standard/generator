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


def test_documentation_endpoint_classifies_a_genuinely_ambiguous_name_as_ambiguous_not_unmatched():
    # Bezeichnung is real, confirmed ambiguous in this corpus (see
    # tests/extraction/test_annex_pdf.py): its real PDF occurrences genuinely
    # disagree (3+ distinct real texts), so attach_english_documentation
    # never attaches English documentation to any subject named Bezeichnung,
    # and build_documentation_texts must classify it as "ambiguous" -- but
    # only if it is given the REAL occurrence data. Passing an empty
    # occurrences dict (the bug this test guards against) makes
    # len(set([])) > 1 always False, silently misclassifying every such
    # subject as "unmatched" instead.
    #
    # Uses its own store path (not STORE_PATH) -- create_app()/open_store()
    # never explicitly close the underlying Oxigraph store, so running two
    # tests back to back against the SAME store path can race on Oxigraph's
    # own file lock (confirmed live: "IO error: lock hold by current
    # process... No locks available") depending on exactly when Python
    # garbage-collects the previous test's Dataset/app objects.
    store_path = STORE_PATH + "_ambiguous"
    shutil.rmtree(store_path, ignore_errors=True)
    try:
        app = create_app(store_path, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        documentation = client.get("/api/documentation")
        assert documentation.status_code == 200
        body = documentation.json()

        ambiguous_names = {entry["name"] for entry in body["ambiguous"]}
        unmatched_names = {entry["name"] for entry in body["unmatched"]}
        assert "Bezeichnung" in ambiguous_names
        assert "Bezeichnung" not in unmatched_names
    finally:
        shutil.rmtree(store_path, ignore_errors=True)
