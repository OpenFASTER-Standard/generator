import pytest
from pathlib import Path

from process_workflow.store import DEFAULT_PROCESS_INSTANCES_DIR, process_instances_dir


def test_default_path_with_no_env_var(monkeypatch):
    monkeypatch.delenv("MIKADIV_PROCESS_INSTANCES_DIR", raising=False)
    assert process_instances_dir() == Path(DEFAULT_PROCESS_INSTANCES_DIR)


def test_env_var_override_is_read_at_call_time_not_import_time(monkeypatch):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/first")
    assert process_instances_dir() == Path("/tmp/first")
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/second")
    assert process_instances_dir() == Path("/tmp/second")


from process_workflow.engine import start_citation_correction
from process_workflow.store import CorrectionIdentity, load_instance, save_instance


def _identity(**overrides) -> CorrectionIdentity:
    fields = dict(fact_key="fact-1", leaf_reference_id="ref-1", drift_kind="CONTENT", fingerprint="fp-1")
    fields.update(overrides)
    return CorrectionIdentity(**fields)


def test_save_then_load_returns_a_resumable_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")

    save_instance(_identity(), wf)
    loaded = load_instance(_identity())

    assert loaded is not None
    from SpiffWorkflow.task import TaskState
    ready = loaded.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"


def test_load_for_a_never_saved_identity_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    assert load_instance(_identity(fact_key="never-saved")) is None


def test_load_for_a_corrupted_file_raises_named_error(monkeypatch, tmp_path):
    from process_workflow.store import CorruptedInstanceError, _instance_filename

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="corrupted")
    bad_path = tmp_path / _instance_filename(identity)
    bad_path.write_text("not valid json at all {{{", encoding="utf-8")

    with pytest.raises(CorruptedInstanceError) as exc_info:
        load_instance(identity)
    assert str(bad_path) in str(exc_info.value)


def test_delete_removes_the_file_and_a_second_delete_does_not_raise(monkeypatch, tmp_path):
    from process_workflow.store import delete_instance

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")
    identity = _identity(fact_key="to-delete")
    save_instance(identity, wf)
    assert load_instance(identity) is not None

    delete_instance(identity)
    assert load_instance(identity) is None
    delete_instance(identity)  # must not raise


def test_different_identities_never_collide_on_the_same_filename():
    from process_workflow.store import _instance_filename

    a = _identity(fact_key="alice|bob")  # contains the real join separator
    b = _identity(fact_key="alice", leaf_reference_id="bob|ref-1")  # shifted fields
    assert _instance_filename(a) != _instance_filename(b)
