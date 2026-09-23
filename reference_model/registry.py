"""Selector-type registry. Adding a new source format means writing a
resolve()/canonicalize_and_hash() pair and registering it here -- nothing
else in this package, or any future consumer, needs to change or even be
aware a new format was added.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from reference_model.model import ResolutionOutcome

ResolveFn = Callable[[Any, str], ResolutionOutcome]
CanonicalizeAndHashFn = Callable[[Any], str]


@dataclass(frozen=True)
class Resolver:
    resolve: ResolveFn
    canonicalize_and_hash: CanonicalizeAndHashFn


_REGISTRY: dict[str, Resolver] = {}


def register(selector_type: str, resolver: Resolver, *, replace: bool = False) -> None:
    if not replace and selector_type in _REGISTRY:
        raise ValueError(
            f"selector type {selector_type!r} is already registered; "
            "pass replace=True to intentionally override it"
        )
    _REGISTRY[selector_type] = resolver


def unregister(selector_type: str) -> None:
    _REGISTRY.pop(selector_type, None)


def get_resolver(selector_type: str) -> Resolver:
    try:
        return _REGISTRY[selector_type]
    except KeyError:
        raise KeyError(
            f"no resolver registered for selector type {selector_type!r}; "
            f"known types: {sorted(_REGISTRY)}"
        ) from None
