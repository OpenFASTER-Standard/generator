"""Runs a registered transformation end to end against a graph."""
from __future__ import annotations

from typing import Any

from rdflib import Graph

from annotation_model.transform.registry import get


class TransformationError(RuntimeError):
    """A named stage (query, min_rows, renderer) of a registered
    transformation failed -- carries the transformation's name and which
    stage failed, so a caller never sees a bare underlying exception with
    no indication of which transformation or step it came from.

    Note: rdflib's own SPARQL error semantics can make an expression
    error inside the query (e.g. a division by zero in a BIND) surface
    here as a zero-row result rather than a query-stage failure -- that
    is rdflib's behavior, not a bug in this wrapping, but it means "0
    rows" can sometimes mean "the query's expressions are wrong," not
    just "the graph genuinely has no matches."
    """


def apply_transformation(graph: Graph, name: str) -> Any:
    transformation = get(name)

    try:
        results = graph.query(transformation.query)
        if results.type != "SELECT":
            raise TransformationError(
                f"transformation {name!r} query must be a SELECT, got {results.type}"
            )
        rows = [row.asdict() for row in results]
    except TransformationError:
        raise
    except Exception as exc:
        raise TransformationError(
            f"transformation {name!r} query failed: {type(exc).__name__}: {exc}"
        ) from exc

    if len(rows) < transformation.min_rows:
        raise TransformationError(
            f"transformation {name!r} returned {len(rows)} row(s), "
            f"expected at least {transformation.min_rows}"
        )

    try:
        return transformation.renderer(rows)
    except Exception as exc:
        raise TransformationError(
            f"transformation {name!r} renderer failed: {type(exc).__name__}: {exc}"
        ) from exc
