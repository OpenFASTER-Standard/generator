"""Transformation registry. Adding a new transformation means writing a
(query, renderer) pair and registering it here -- nothing else in this
package, or any future consumer, needs to change or even be aware a new
transformation was added.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Transformation:
    name: str
    query: str
    renderer: Callable[[list[dict]], Any]
    min_rows: int = 1


_REGISTRY: dict[str, Transformation] = {}


def register(transformation: Transformation, *, replace: bool = False) -> None:
    if not replace and transformation.name in _REGISTRY:
        raise ValueError(
            f"transformation {transformation.name!r} is already registered; "
            "pass replace=True to intentionally override it"
        )
    _REGISTRY[transformation.name] = transformation


def get(name: str) -> Transformation:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"no transformation registered for name {name!r}; "
            f"known names: {sorted(_REGISTRY)}"
        ) from None
