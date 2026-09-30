"""Runs a registered transformation end to end against a graph."""
from __future__ import annotations

from typing import Any

from rdflib import Graph

from annotation_model.transform.registry import get


class TransformationError(RuntimeError):
    """A named stage (query, min_rows, renderer) of a registered
    transformation failed -- carries the transformation's name and which
    stage failed, so a caller never sees a bare underlying exception with
    no indication of which transformation or step it came from."""


def apply_transformation(graph: Graph, name: str) -> Any:
    transformation = get(name)

    try:
        results = graph.query(transformation.query)
    except Exception as exc:
        raise TransformationError(f"transformation {name!r} query failed: {exc}") from exc

    rows = [row.asdict() for row in results]

    if len(rows) < transformation.min_rows:
        raise TransformationError(
            f"transformation {name!r} returned {len(rows)} row(s), "
            f"expected at least {transformation.min_rows}"
        )

    try:
        return transformation.renderer(rows)
    except Exception as exc:
        raise TransformationError(f"transformation {name!r} renderer failed: {exc}") from exc
