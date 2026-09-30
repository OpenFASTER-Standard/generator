import unicodedata
from pathlib import Path

import pytest
from SpiffWorkflow.task import TaskState

from generator_errors import GeneratorError
from process_workflow.engine import start_citation_correction
from process_workflow.store import (
    DEFAULT_PROCESS_INSTANCES_DIR,
    CorrectionIdentity,
    CorruptedInstanceError,
    _instance_filename,
    delete_instance,
    load_instance,
    process_instances_dir,
    save_instance,
)


def _identity(**overrides) -> CorrectionIdentity:
    fields = dict(fact_key="fact-1", leaf_reference_id="ref-1", drift_kind="CONTENT", fingerprint="fp-1")
    fields.update(overrides)
    return CorrectionIdentity(**fields)


def test_default_path_with_no_env_var(monkeypatch):
    monkeypatch.delenv("MIKADIV_PROCESS_INSTANCES_DIR", raising=False)
    assert process_instances_dir() == Path(DEFAULT_PROCESS_INSTANCES_DIR)


def test_env_var_override_is_read_at_call_time_not_import_time(monkeypatch):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/first")
    assert process_instances_dir() == Path("/tmp/first")
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/second")
    assert process_instances_dir() == Path("/tmp/second")


def test_save_then_load_returns_a_resumable_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")

    save_instance(_identity(), wf)
    loaded = load_instance(_identity())

    assert loaded is not None
    ready = loaded.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"


def test_load_for_a_never_saved_identity_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    assert load_instance(_identity(fact_key="never-saved")) is None


def test_load_for_a_corrupted_file_raises_named_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="corrupted")
    bad_path = tmp_path / _instance_filename(identity)
    bad_path.write_text("not valid json at all {{{", encoding="utf-8")

    with pytest.raises(CorruptedInstanceError) as exc_info:
        load_instance(identity)
    assert str(bad_path) in str(exc_info.value)


def test_delete_removes_the_file_and_a_second_delete_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")
    identity = _identity(fact_key="to-delete")
    save_instance(identity, wf)
    assert load_instance(identity) is not None

    delete_instance(identity)
    assert load_instance(identity) is None
    delete_instance(identity)  # must not raise


def test_different_identities_never_collide_on_the_same_filename():
    a = _identity(fact_key="alice|bob")  # contains the real join separator
    b = _identity(fact_key="alice", leaf_reference_id="bob|ref-1")  # shifted fields
    assert _instance_filename(a) != _instance_filename(b)


def test_unicode_normalization_form_does_not_change_the_filename():
    # M9: fact_key is free text a human types into a form -- an NFC vs
    # NFD-encoded accented character must hash identically, or a
    # re-typed key silently produces "nothing owed" instead of a match.
    nfc = unicodedata.normalize("NFC", "Vornameé")  # precomposed é
    nfd = unicodedata.normalize("NFD", "Vornameé")  # combining accent
    assert nfc != nfd  # sanity: these really are different byte sequences
    assert _instance_filename(_identity(fact_key=nfc)) == _instance_filename(_identity(fact_key=nfd))


def test_corrupted_instance_error_is_a_generator_error_with_http_500():
    # I4: consistent with this project's own established GeneratorError
    # contract -- every domain error a future webapp endpoint can raise
    # derives from it so the existing exception handler maps it uniformly.
    assert issubclass(CorruptedInstanceError, GeneratorError)
    assert CorruptedInstanceError.http_status == 500


def test_save_instance_is_attributable_and_readable_as_a_pending_correction(monkeypatch, tmp_path):
    # I2: a persisted instance file must record which identity it
    # belongs to -- otherwise an operator (or a future webapp) looking at
    # a file on disk has no way to tell what correction it represents,
    # and a filename-scheme bug could silently hand back the WRONG
    # workflow instead of failing loudly.
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="attributable")
    wf = start_citation_correction(verdict="rejected")
    save_instance(identity, wf)

    path = tmp_path / _instance_filename(identity)
    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["identity"] == {
        "fact_key": "attributable", "leaf_reference_id": "ref-1",
        "drift_kind": "CONTENT", "fingerprint": "fp-1",
    }


def test_load_instance_raises_if_the_stored_identity_does_not_match(monkeypatch, tmp_path):
    # I2: guards against a real class of bug the ledger already proved
    # is possible (a filename-scheme collision) -- if two different
    # identities ever land on the same file, loading it under the WRONG
    # identity must fail loudly, never silently return that workflow.
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="mismatch-target")
    wf = start_citation_correction(verdict="rejected")
    save_instance(identity, wf)

    path = tmp_path / _instance_filename(identity)
    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["identity"]["fact_key"] = "someone-elses-key"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(CorruptedInstanceError):
        load_instance(identity)


def test_save_instance_leaves_original_file_intact_if_write_is_interrupted(monkeypatch, tmp_path):
    # I3: matches references_catalog/catalog.py's own established atomic
    # write pattern and its own test for it -- a process killed mid-write
    # must leave the original file untouched, never truncated.
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="atomic")
    first_wf = start_citation_correction(verdict="rejected")
    save_instance(identity, first_wf)
    path = tmp_path / _instance_filename(identity)
    before = path.read_text(encoding="utf-8")

    import os

    import process_workflow.store as store_module

    def _boom(*args, **kwargs):
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(store_module.os, "replace", _boom)

    second_wf = start_citation_correction(verdict="rejected")
    with pytest.raises(OSError):
        save_instance(identity, second_wf)

    after = path.read_text(encoding="utf-8")
    assert after == before
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_instance_leaves_no_leftover_temp_file(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")
    save_instance(_identity(fact_key="no-leftover"), wf)
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_load_delete_accept_an_explicit_instances_dir_override(tmp_path):
    # I6: an explicit override must work independently of the env var,
    # so a caller who already has a specific directory in hand (e.g. a
    # test, or a future caller with its own path parameter) isn't forced
    # through the process-global env var to get an isolated location.
    identity = _identity(fact_key="explicit-dir")
    wf = start_citation_correction(verdict="rejected")

    save_instance(identity, wf, instances_dir=tmp_path)
    loaded = load_instance(identity, instances_dir=tmp_path)
    assert loaded is not None

    delete_instance(identity, instances_dir=tmp_path)
    assert load_instance(identity, instances_dir=tmp_path) is None
