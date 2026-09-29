import pytest
from reference_model.cite import cite, cite_union
from reference_model.deserialize import ReferenceDeserializationError, from_json_dict
from reference_model.model import ResolutionOutcome, Status, SubjectDocument
from reference_model.registry import Resolver, get_resolver, register, unregister
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from staleness_sweep.resolve import resolve_family_location
from tests.corpus_fixtures import REAL_CORPUS_ROOT as CORPUS_ROOT, requires_real_corpus


def _real_leaf(xpath: str):
    location = resolve_family_location(CORPUS_ROOT, "MiKaDiv_FM_Meldeart23")
    subject_document = SubjectDocument(
        family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=location.retrieval_uri
    )
    return cite(subject_document, XPathSelector.create(xpath))


@requires_real_corpus
def test_leaf_round_trips_through_json():
    leaf = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    assert from_json_dict(to_json_dict(leaf)) == leaf


@requires_real_corpus
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


@requires_real_corpus
def test_missing_field_raises_deserialization_error():
    leaf = _real_leaf("/xs:schema/xs:complexType[@name='Meldeart23']")
    data = to_json_dict(leaf)
    del data["captured_at"]
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict(data)


@requires_real_corpus
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


def test_from_json_dict_reconstructs_a_newly_registered_selector_type_without_any_code_change():
    # Adding a new source format means writing a resolve()/
    # canonicalize_and_hash() pair and registering it -- registry.py's own
    # documented promise. from_json_dict() must honor that promise too: it
    # looks the selector class up via the registry (selector_cls), not a
    # second, hand-maintained dict that a new format's author could forget.
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _DummyDeserializeSelector:
        type: str
        value: str

    register(
        "DummyDeserializeTest",
        Resolver(
            resolve=lambda s, u: ResolutionOutcome(status=Status.RESOLVED, raw_content=s.value),
            canonicalize_and_hash=lambda c: f"hash-of-{c}",
            selector_cls=_DummyDeserializeSelector,
        ),
    )
    try:
        data = {
            "reference_id": "ref-1",
            "subject_document": {"family": "F", "version": "1", "retrieval_uri": "/x"},
            "selector": {"type": "DummyDeserializeTest", "value": "hello"},
            "content_hash": {"algorithm": "sha256", "digest": "abc"},
            "captured_at": "2026-01-01T00:00:00Z",
        }
        result = from_json_dict(data)
        assert result.selector == _DummyDeserializeSelector(type="DummyDeserializeTest", value="hello")
    finally:
        unregister("DummyDeserializeTest")


def test_a_registered_type_with_no_selector_cls_raises_a_clear_deserialization_error():
    register(
        "DummyNoSelectorClsTest",
        Resolver(resolve=lambda s, u: None, canonicalize_and_hash=lambda c: ""),
    )
    try:
        data = {
            "reference_id": "ref-1",
            "subject_document": {"family": "F", "version": "1", "retrieval_uri": "/x"},
            "selector": {"type": "DummyNoSelectorClsTest", "value": "hello"},
            "content_hash": {"algorithm": "sha256", "digest": "abc"},
            "captured_at": "2026-01-01T00:00:00Z",
        }
        with pytest.raises(ReferenceDeserializationError, match="DummyNoSelectorClsTest"):
            from_json_dict(data)
    finally:
        unregister("DummyNoSelectorClsTest")
