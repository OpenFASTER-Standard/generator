import json

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.json_selector import JsonSelector

FIXTURE = {
    "verdict": "approved",
    "nested": {"reasoning": "looks fine"},
    "items": ["a", "b", "c"],
    "flags": {"is_null": None, "is_false": False, "is_zero": 0},
    "weird/key": "slash-in-key",
    "tilde~key": "tilde-in-key",
}


def _write_fixture(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(FIXTURE), encoding="utf-8")
    return str(path)


def _resolver():
    return get_resolver("JsonSelector")


def test_resolves_a_nested_object_field(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/nested/reasoning"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "looks fine"


def test_resolves_an_array_index(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/items/1"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "b"


def test_resolves_null_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_null"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content is None


def test_resolves_false_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_false"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content is False


def test_resolves_zero_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_zero"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == 0


def test_resolves_escaped_slash_in_key(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/weird~1key"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "slash-in-key"


def test_resolves_escaped_tilde_in_key(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/tilde~0key"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "tilde-in-key"


def test_empty_pointer_resolves_whole_document(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create(""), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == FIXTURE


def test_missing_key_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/nonexistent"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_out_of_range_index_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/items/99"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_indexing_into_a_scalar_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/verdict/oops"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_missing_file_is_not_found():
    outcome = _resolver().resolve(JsonSelector.create("/verdict"), "/nonexistent/does-not-exist.json")
    assert outcome.status == Status.NOT_FOUND


def test_malformed_json_is_not_found(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text("{not valid json", encoding="utf-8")
    outcome = _resolver().resolve(JsonSelector.create("/verdict"), str(path))
    assert outcome.status == Status.NOT_FOUND


def test_hash_is_reproducible_and_sensitive_to_different_values(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    resolver = _resolver()

    outcome_1 = resolver.resolve(JsonSelector.create("/verdict"), fixture_path)
    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)
    outcome_2 = resolver.resolve(JsonSelector.create("/verdict"), fixture_path)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)
    assert digest_1 == digest_2
    assert len(digest_1) == 64

    other_outcome = resolver.resolve(JsonSelector.create("/nested/reasoning"), fixture_path)
    other_digest = resolver.canonicalize_and_hash(other_outcome.raw_content)
    assert other_digest != digest_1
