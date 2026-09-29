import pytest
from reference_model.cite import cite, cite_union
from reference_model.deserialize import ReferenceDeserializationError, from_json_dict
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from staleness_sweep.resolve import resolve_current_location

MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _real_leaf(xpath: str):
    outcome = resolve_current_location(MODULE_ROOT, "MiKaDiv_FM_Meldeart23")
    subject_document = SubjectDocument(
        family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=outcome.raw_content
    )
    return cite(subject_document, XPathSelector.create(xpath))


def test_leaf_round_trips_through_json():
    leaf = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    assert from_json_dict(to_json_dict(leaf)) == leaf


def test_union_round_trips_through_json_with_matching_reference_id_and_content_hash():
    leaf_a = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    leaf_b = _real_leaf(
        "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent/xs:extension/xs:sequence"
        "/xs:element[@name='AbgefKapitalertragsteuer']"
    )
    union = cite_union([leaf_a, leaf_b])
    result = from_json_dict(to_json_dict(union))
    assert result == union
    assert result.reference_id == union.reference_id
    assert result.content_hash == union.content_hash


def test_missing_field_raises_deserialization_error():
    leaf = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    data = to_json_dict(leaf)
    del data["captured_at"]
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict(data)


def test_unknown_selector_type_raises_deserialization_error():
    leaf = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    data = to_json_dict(leaf)
    data["selector"]["type"] = "NotARealSelector"
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict(data)


def test_non_dict_input_raises_deserialization_error():
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict("not a dict")


def test_malformed_union_parts_raises_deserialization_error():
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict({"parts": "not a list"})
