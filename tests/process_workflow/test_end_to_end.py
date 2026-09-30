import subprocess
import sys
from pathlib import Path

from citation_workflow.add_citation import add_citation
from reference_model.cite import cite
from reference_model.model import ResolutionOutcome, Status, SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision
from review_recording.record import Verdict
from review_surfacing.summarize import DriftKind, FlaggedLeaf
from review_workflow.orchestrate import submit_review
from staleness_sweep.resolve import resolve_family_location
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

pytestmark = requires_real_corpus

SUBPROCESS_SCRIPT = Path(__file__).resolve().parent / "_complete_correction_subprocess.py"
FIRST_XPATH = "/xs:schema/xs:complexType[@name='Meldeart23']"
CORRECTED_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _real_leaf(xpath: str):
    location = resolve_family_location(REAL_CORPUS_ROOT, "MiKaDiv_FM_Meldeart23")
    subject_document = SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=location.retrieval_uri)
    return cite(subject_document, XPathSelector.create(xpath))


def test_a_rejected_review_pauses_and_a_later_correction_resumes_it_in_a_separate_process(tmp_path, monkeypatch):
    instances_dir = tmp_path / "instances"
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(instances_dir))
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")

    leaf = _real_leaf(FIRST_XPATH)
    add_revision(str(catalog_path), "e2e-key", leaf, "author", "initial", False)

    flagged = FlaggedLeaf(
        leaf=leaf, outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT, fingerprint="e2e-fingerprint",
    )
    submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "e2e-key", flagged,
        "reviewer-1", Verdict.REJECTED, "needs a real correction",
    )
    assert instances_dir.exists() and any(instances_dir.iterdir())

    add_citation(
        REAL_CORPUS_ROOT, str(catalog_path),
        family="MiKaDiv_FM_Meldeart23", xpath=CORRECTED_XPATH,
        fact_key="e2e-key", author="author", comment="corrected", is_correction=True,
    )

    # `env=None` (subprocess.run's default -- just omit the argument) is
    # the right choice here, not a restricted custom dict: it inherits
    # the *whole* current process's environment, which already has
    # monkeypatch's MIKADIV_PROCESS_INSTANCES_DIR override in it (env
    # vars set via os.environ/monkeypatch are always inherited by
    # subprocesses unless explicitly overridden) plus this venv's own
    # PATH/VIRTUAL_ENV, so the subprocess's `sys.executable` resolves
    # its imports the same way this test process does. `cwd` is still
    # set explicitly to the repo root so `process_workflow`/etc. are
    # importable regardless of where pytest itself was invoked from.
    result = subprocess.run(
        [sys.executable, str(SUBPROCESS_SCRIPT), "e2e-key", leaf.reference_id, "CONTENT", "e2e-fingerprint", "e2e-key"],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "True"
    assert not any(instances_dir.iterdir())

    second_run = subprocess.run(
        [sys.executable, str(SUBPROCESS_SCRIPT), "e2e-key", leaf.reference_id, "CONTENT", "e2e-fingerprint", "e2e-key"],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True, text=True, check=True,
    )
    assert second_run.stdout.strip() == "False"
