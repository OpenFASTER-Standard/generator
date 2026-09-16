import shutil

from store.database import open_store
from store.runs import list_runs, read_run_audit
from webapp.pipeline import run_pipeline_and_store

STORE_PATH = "/tmp/test_webapp_store_task13"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_run_pipeline_and_store_produces_a_real_run_with_real_audit_data():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T18:00:00Z", created_at="2026-09-15T18:00:00Z",
        )

        assert info.run_id == "2026-09-15T18:00:00Z"
        assert list_runs(dataset) == [info]

        attachment, coverage, issues = read_run_audit(dataset, "2026-09-15T18:00:00Z")
        assert coverage.total_documented_subjects > 0
        assert len(attachment.attached) > 0
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
