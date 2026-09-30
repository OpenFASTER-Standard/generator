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
