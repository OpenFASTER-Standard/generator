from dataclasses import dataclass

import pytest

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, get_resolver, register, unregister


@dataclass(frozen=True)
class _DummySelector:
    type: str
    value: str


def test_register_and_get_resolver_round_trip():
    def resolve(selector, retrieval_uri):
        return ResolutionOutcome(status=Status.RESOLVED, raw_content=selector.value)

    def canonicalize_and_hash(raw_content):
        return f"hash-of-{raw_content}"

    resolver = Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash)
    try:
        register("DummyForRegistryTest", resolver)

        fetched = get_resolver("DummyForRegistryTest")
        selector = _DummySelector(type="DummyForRegistryTest", value="hello")
        outcome = fetched.resolve(selector, "/does/not/matter")
        assert outcome.status == Status.RESOLVED
        assert fetched.canonicalize_and_hash(outcome.raw_content) == "hash-of-hello"
    finally:
        unregister("DummyForRegistryTest")


def test_get_resolver_raises_for_unknown_type():
    with pytest.raises(KeyError, match="NoSuchSelectorType"):
        get_resolver("NoSuchSelectorType")


def test_register_raises_on_duplicate_registration():
    # Prevents an import-order accident or a name collision between two
    # independently authored selector modules from silently swapping
    # resolution behavior for an already-registered type.
    resolver = Resolver(resolve=lambda s, u: None, canonicalize_and_hash=lambda c: "")
    try:
        register("DummyDuplicateTest", resolver)
        with pytest.raises(ValueError, match="DummyDuplicateTest"):
            register("DummyDuplicateTest", resolver)
    finally:
        unregister("DummyDuplicateTest")


def test_register_with_replace_true_overrides_intentionally():
    resolver_a = Resolver(resolve=lambda s, u: None, canonicalize_and_hash=lambda c: "a")
    resolver_b = Resolver(resolve=lambda s, u: None, canonicalize_and_hash=lambda c: "b")
    try:
        register("DummyReplaceTest", resolver_a)
        register("DummyReplaceTest", resolver_b, replace=True)
        assert get_resolver("DummyReplaceTest").canonicalize_and_hash(None) == "b"
    finally:
        unregister("DummyReplaceTest")


def test_unregister_is_a_no_op_for_an_unknown_type():
    unregister("NoSuchSelectorTypeEverRegistered")  # must not raise
