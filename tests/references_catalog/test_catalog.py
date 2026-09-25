import json
from pathlib import Path

import pytest

import references_catalog.catalog as catalog_module
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import (
    CatalogLoadError,
    add_revision,
    get_current_revision,
    get_history,
    list_pages,
    load_catalog,
)

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def _empty_catalog(tmp_path) -> str:
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    return str(catalog_path)


def test_add_revision_creates_a_page_with_one_revision(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    revision = add_revision(catalog_path, "fact-1", leaf, "julian", "initial citation", False)

    history = get_history(catalog_path, "fact-1")
    assert len(history) == 1
    assert history[0].revision_id == revision.revision_id
    assert history[0].reference == to_json_dict(leaf)
    assert history[0].author == "julian"
    assert history[0].comment == "initial citation"
    assert history[0].is_correction is False


def test_add_revision_appends_a_second_revision_and_becomes_current(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "initial citation", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf_2, "julian", "corrected the citation", True)

    history = get_history(catalog_path, "fact-1")
    assert len(history) == 2
    assert history[1].revision_id == revision_2.revision_id
    assert history[1].is_correction is True

    current = get_current_revision(catalog_path, "fact-1")
    assert current.revision_id == revision_2.revision_id
    assert current.reference == to_json_dict(leaf_2)


def test_add_revision_preserves_other_pages(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first fact", False)
    add_revision(catalog_path, "fact-2", leaf_2, "julian", "second fact", False)

    assert len(get_history(catalog_path, "fact-1")) == 1
    assert len(get_history(catalog_path, "fact-2")) == 1
    assert get_current_revision(catalog_path, "fact-1").reference == to_json_dict(leaf_1)
    assert get_current_revision(catalog_path, "fact-2").reference == to_json_dict(leaf_2)


def test_get_current_revision_returns_none_for_untouched_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert get_current_revision(catalog_path, "never-touched") is None


def test_get_history_returns_empty_list_for_untouched_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert get_history(catalog_path, "never-touched") == []


def test_revision_ids_are_unique_across_calls(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    revision_1 = add_revision(catalog_path, "fact-1", leaf, "julian", "same args", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf, "julian", "same args", False)

    assert revision_1.revision_id != revision_2.revision_id


def test_add_revision_writes_pretty_printed_sorted_json_with_trailing_newline(tmp_path):
    catalog_path = Path(_empty_catalog(tmp_path))
    leaf_1 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    add_revision(catalog_path, "z-fact", leaf_1, "julian", "z", False)
    add_revision(catalog_path, "a-fact", leaf_2, "julian", "a", False)

    raw = catalog_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "\n" in raw
    assert raw.index('"a-fact"') < raw.index('"z-fact"')

    # The raw file, re-parsed, matches json.dumps(<same content>, indent=2,
    # sort_keys=True) + "\n" exactly -- an exact structural check on
    # formatting, not a weak proxy, without needing to hand-predict the
    # dynamic revision_id/created_at values.
    parsed = json.loads(raw)
    reformatted = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert raw == reformatted


def test_add_revision_raises_when_catalog_file_does_not_exist(tmp_path):
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    missing_path = tmp_path / "does-not-exist.json"

    with pytest.raises(FileNotFoundError):
        add_revision(str(missing_path), "fact-1", leaf, "julian", "x", False)

    assert not missing_path.exists()


def test_add_revision_on_malformed_catalog_raises_without_writing(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("[]", encoding="utf-8")
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    with pytest.raises(CatalogLoadError):
        add_revision(str(catalog_path), "fact-1", leaf, "julian", "x", False)

    assert catalog_path.read_text(encoding="utf-8") == "[]"


def test_add_revision_leaves_original_file_intact_if_write_is_interrupted(tmp_path, monkeypatch):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first", False)
    before = Path(catalog_path).read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(catalog_module.os, "replace", _boom)

    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    with pytest.raises(OSError):
        add_revision(catalog_path, "fact-2", leaf_2, "julian", "second", False)

    after = Path(catalog_path).read_text(encoding="utf-8")
    assert after == before


def test_add_revision_leaves_no_leftover_temp_file(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    add_revision(catalog_path, "fact-1", leaf, "julian", "x", False)

    leftover = list(Path(tmp_path).glob("*.tmp"))
    assert leftover == []


def test_load_catalog_raises_catalog_load_error_on_malformed_json(tmp_path):
    catalog_path = tmp_path / "bad.json"
    catalog_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CatalogLoadError, match="not valid JSON"):
        load_catalog(str(catalog_path))


def test_load_catalog_raises_catalog_load_error_on_non_object_json(tmp_path):
    catalog_path = tmp_path / "array.json"
    catalog_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(CatalogLoadError, match="expected a JSON object"):
        load_catalog(str(catalog_path))


def test_list_pages_summarizes_every_page_with_correct_revision_count_and_current(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first version", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf_2, "julian", "second version", True)
    add_revision(catalog_path, "fact-2", leaf_1, "julian", "only version", False)

    pages = list_pages(catalog_path)

    assert pages["fact-1"].revision_count == 2
    assert pages["fact-1"].current.revision_id == revision_2.revision_id
    assert pages["fact-2"].revision_count == 1


def test_list_pages_on_empty_catalog_returns_empty_dict(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert list_pages(catalog_path) == {}
