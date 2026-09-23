import json
from pathlib import Path

import pytest

from reference_model.model import Status
from staleness_sweep.resolve import CorpusIntegrityError, resolve_current_location

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def test_resolves_a_real_family_to_its_real_current_path():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "MiKaDiv_FM_Meldeart23")
    assert outcome.status == Status.RESOLVED
    expected = str(Path(REAL_MODULE_ROOT) / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd")
    assert outcome.raw_content == expected
    assert Path(outcome.raw_content).exists()


def test_resolves_the_unversioned_din_family_too():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "din-norm-91379-datatypes")
    assert outcome.status == Status.RESOLVED
    assert Path(outcome.raw_content).exists()


def test_unknown_family_is_not_found():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "NoSuchFamilyEver")
    assert outcome.status == Status.NOT_FOUND


def test_missing_current_pointer_is_not_found(tmp_path):
    outcome = resolve_current_location(str(tmp_path), "AnyFamily")
    assert outcome.status == Status.NOT_FOUND


def test_current_pointer_with_trailing_whitespace_is_handled(tmp_path):
    snapshot_dir = tmp_path / "1.0"
    snapshot_dir.mkdir()
    (tmp_path / "_current").write_text("1.0\n")
    (snapshot_dir / "file.xsd").write_text("<real/>")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"Family": "file.xsd"}))

    outcome = resolve_current_location(str(tmp_path), "Family")
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == str(snapshot_dir / "file.xsd")


def test_missing_manifest_for_the_pointed_at_snapshot_raises(tmp_path):
    (tmp_path / "_current").write_text("9.99")
    (tmp_path / "9.99").mkdir()
    with pytest.raises(CorpusIntegrityError, match="9.99"):
        resolve_current_location(str(tmp_path), "AnyFamily")


def test_manifest_naming_a_nonexistent_file_raises(tmp_path):
    snapshot_dir = tmp_path / "1.0"
    snapshot_dir.mkdir()
    (tmp_path / "_current").write_text("1.0")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"GhostFamily": "xsd/does-not-exist.xsd"}))

    with pytest.raises(CorpusIntegrityError, match="does-not-exist"):
        resolve_current_location(str(tmp_path), "GhostFamily")


def test_manifest_entry_escaping_the_snapshot_directory_is_rejected(tmp_path):
    module_root = tmp_path / "module"
    module_root.mkdir()
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir()
    (module_root / "_current").write_text("1.0")

    outside_file = tmp_path / "outside.xsd"  # sibling of module_root, not under it
    outside_file.write_text("<outside/>")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"EscapingFamily": "../../outside.xsd"}))

    with pytest.raises(CorpusIntegrityError, match="escapes"):
        resolve_current_location(str(module_root), "EscapingFamily")


def test_a_second_synthetic_snapshot_resolves_independently(tmp_path):
    snap1 = tmp_path / "1.0"
    snap1.mkdir()
    (snap1 / "file-v1.xsd").write_text("<old/>")
    (snap1 / "_manifest.json").write_text(json.dumps({"Family": "file-v1.xsd"}))

    snap2 = tmp_path / "2.0"
    snap2.mkdir()
    (snap2 / "file-v2.xsd").write_text("<new/>")
    (snap2 / "_manifest.json").write_text(json.dumps({"Family": "file-v2.xsd"}))

    (tmp_path / "_current").write_text("2.0")

    outcome = resolve_current_location(str(tmp_path), "Family")
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == str(snap2 / "file-v2.xsd")
