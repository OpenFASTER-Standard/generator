from dataclasses import dataclass

import pytest

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, get_resolver, register


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
    register("DummyForRegistryTest", resolver)

    fetched = get_resolver("DummyForRegistryTest")
    selector = _DummySelector(type="DummyForRegistryTest", value="hello")
    outcome = fetched.resolve(selector, "/does/not/matter")
    assert outcome.status == Status.RESOLVED
    assert fetched.canonicalize_and_hash(outcome.raw_content) == "hash-of-hello"


def test_get_resolver_raises_for_unknown_type():
    with pytest.raises(KeyError, match="NoSuchSelectorType"):
        get_resolver("NoSuchSelectorType")
