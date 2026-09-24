import json
from pathlib import Path

import pytest

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import DuplicateFactKeyError, load_catalog, save_reference

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


def test_save_reference_writes_a_real_leaf(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    save_reference(catalog_path, "fact-1", leaf)

    catalog = load_catalog(catalog_path)
    assert catalog == {"fact-1": to_json_dict(leaf)}


def test_save_reference_raises_on_duplicate_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    save_reference(catalog_path, "fact-1", leaf)

    with pytest.raises(DuplicateFactKeyError):
        save_reference(catalog_path, "fact-1", leaf)


def test_save_reference_duplicate_rejection_leaves_file_byte_for_byte_unchanged(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    save_reference(catalog_path, "fact-1", leaf)
    before = Path(catalog_path).read_text(encoding="utf-8")

    with pytest.raises(DuplicateFactKeyError):
        save_reference(catalog_path, "fact-1", leaf)

    after = Path(catalog_path).read_text(encoding="utf-8")
    assert after == before


def test_save_reference_preserves_existing_entries_when_adding_a_new_one(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    save_reference(catalog_path, "fact-1", leaf_1)
    save_reference(catalog_path, "fact-2", leaf_2)

    catalog = load_catalog(catalog_path)
    assert catalog == {"fact-1": to_json_dict(leaf_1), "fact-2": to_json_dict(leaf_2)}


def test_load_catalog_returns_all_entries_from_a_hand_written_multi_entry_catalog(tmp_path):
    fixture = {
        "fact-a": {"reference_id": "aaa"},
        "fact-b": {"reference_id": "bbb"},
    }
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps(fixture), encoding="utf-8")

    assert load_catalog(str(catalog_path)) == fixture


def test_save_reference_writes_pretty_printed_sorted_json(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    save_reference(catalog_path, "z-fact", leaf_1)
    save_reference(catalog_path, "a-fact", leaf_2)

    raw = Path(catalog_path).read_text(encoding="utf-8")
    assert "\n" in raw  # pretty-printed, not a single line
    assert raw.index('"a-fact"') < raw.index('"z-fact"')  # sorted regardless of insertion order


def test_save_reference_raises_when_catalog_file_does_not_exist(tmp_path):
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    with pytest.raises(FileNotFoundError):
        save_reference(str(tmp_path / "does-not-exist.json"), "fact-1", leaf)
