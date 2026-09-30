import pytest

from process_workflow.store import CorrectionIdentity, load_instance, process_instances_dir


def _identity(**overrides) -> CorrectionIdentity:
    fields = dict(fact_key="fact-1", leaf_reference_id="ref-1", drift_kind="CONTENT", fingerprint="fp-1")
    fields.update(overrides)
    return CorrectionIdentity(**fields)


def test_start_pending_correction_persists_on_rejected(monkeypatch, tmp_path):
    from process_workflow.orchestration import start_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity()

    start_pending_correction(identity, verdict="rejected")

    loaded = load_instance(identity)
    assert loaded is not None
    assert not loaded.is_completed()


def test_start_pending_correction_never_persists_on_approved(monkeypatch, tmp_path):
    from process_workflow.orchestration import start_pending_correction

    instances_dir = tmp_path / "process_instances"
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(instances_dir))
    identity = _identity(fact_key="fact-approved")

    start_pending_correction(identity, verdict="approved")

    assert not instances_dir.exists()


def test_complete_pending_correction_completes_an_existing_instance(monkeypatch, tmp_path):
    from process_workflow.orchestration import complete_pending_correction, start_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="fact-existing")
    start_pending_correction(identity, verdict="rejected")

    result = complete_pending_correction(identity, corrected_fact_key="fact-existing")

    assert result is True
    assert load_instance(identity) is None


def test_complete_pending_correction_returns_false_for_no_matching_instance(monkeypatch, tmp_path):
    from process_workflow.orchestration import complete_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    result = complete_pending_correction(_identity(fact_key="never-started"), corrected_fact_key="x")
    assert result is False


def test_complete_pending_correction_raises_on_a_corrupted_instance_not_returns_false(monkeypatch, tmp_path):
    # I5 (Review Focus #1, checked at the right boundary): a corrupted
    # instance must never be treated the same as "nothing owed" -- that
    # would silently discard a real, outstanding correction obligation.
    from process_workflow.orchestration import complete_pending_correction
    from process_workflow.store import CorruptedInstanceError, _instance_filename

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="corrupted-pending")
    bad_path = tmp_path / _instance_filename(identity)
    bad_path.write_text("not valid json at all {{{", encoding="utf-8")

    with pytest.raises(CorruptedInstanceError):
        complete_pending_correction(identity, corrected_fact_key="x")


def test_complete_pending_correction_error_names_the_identity(monkeypatch, tmp_path):
    # M5: NoReadyCorrectionTaskError's own message only says "found 0" --
    # unhelpful without knowing which pending correction it came from.
    from process_workflow.orchestration import complete_pending_correction, start_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="already-done")
    start_pending_correction(identity, verdict="rejected")
    assert complete_pending_correction(identity, corrected_fact_key="first") is True

    # Craft a workflow that's already complete and save it directly
    # under a fresh identity, to exercise complete_pending_correction's
    # own error-enrichment without depending on internal load/delete
    # ordering.
    from process_workflow.engine import start_citation_correction
    from process_workflow.store import save_instance

    already_complete_identity = _identity(fact_key="already-complete")
    save_instance(already_complete_identity, start_citation_correction(verdict="approved"))

    with pytest.raises(Exception) as exc_info:
        complete_pending_correction(already_complete_identity, corrected_fact_key="x")
    assert "already-complete" in str(exc_info.value)


def test_start_and_complete_pending_correction_accept_an_explicit_instances_dir(tmp_path):
    # I6: an explicit override must work end to end through the
    # orchestration layer too, independent of the env var -- a future
    # caller that already has its own catalog_path/reviews_dir-style
    # parameter shouldn't be forced through a process-global env var.
    from process_workflow.orchestration import complete_pending_correction, start_pending_correction

    identity = _identity(fact_key="explicit-orchestration")
    start_pending_correction(identity, verdict="rejected", instances_dir=tmp_path)

    result = complete_pending_correction(identity, corrected_fact_key="x", instances_dir=tmp_path)
    assert result is True
