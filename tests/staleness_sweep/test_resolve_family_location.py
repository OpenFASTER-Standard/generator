import json

import pytest

from staleness_sweep.resolve import (
    CorpusIntegrityError,
    FamilyLocation,
    list_current_families,
    resolve_family_location,
)

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _corpus_with_one_healthy_and_one_broken_family(tmp_path):
    module_root = tmp_path / "corpus"
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "healthy.xsd").write_text("<real/>", encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"HealthyFamily": "healthy.xsd", "BrokenFamily": "does-not-exist.xsd"}),
        encoding="utf-8",
    )
    (module_root / "_current").write_text("1.0", encoding="utf-8")
    return str(module_root)


def test_resolve_family_location_resolves_a_real_family():
    location = resolve_family_location(REAL_MODULE_ROOT, "MiKaDiv_FM_Meldeart23")
    assert isinstance(location, FamilyLocation)
    assert location.version == "1.02"
    assert location.retrieval_uri.endswith("MiKaDiv_FM_Meldeart23_1.02.xsd")


def test_resolve_family_location_returns_none_for_unknown_family():
    assert resolve_family_location(REAL_MODULE_ROOT, "NoSuchFamilyEver") is None


def test_resolve_family_location_returns_none_when_no_current_pointer(tmp_path):
    assert resolve_family_location(str(tmp_path), "AnyFamily") is None


def test_resolve_family_location_resolves_a_healthy_family_despite_an_unrelated_broken_sibling(tmp_path):
    module_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)

    location = resolve_family_location(module_root, "HealthyFamily")

    assert location.family == "HealthyFamily"
    assert location.retrieval_uri.endswith("healthy.xsd")


def test_resolve_family_location_raises_when_that_specific_familys_entry_is_broken(tmp_path):
    module_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)

    with pytest.raises(CorpusIntegrityError):
        resolve_family_location(module_root, "BrokenFamily")


def test_list_current_families_returns_sorted_names_even_with_a_broken_entry(tmp_path):
    module_root = _corpus_with_one_healthy_and_one_broken_family(tmp_path)

    assert list_current_families(module_root) == ["BrokenFamily", "HealthyFamily"]


def test_list_current_families_returns_empty_list_when_no_current_pointer(tmp_path):
    assert list_current_families(str(tmp_path)) == []
