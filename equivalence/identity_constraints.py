"""Direct comparison of xs:key/xs:unique/xs:keyref declarations between
two matched complex types. XSD restricts an identity constraint's
selector/field to a narrow, non-Turing-complete XPath subset, so direct
structural comparison is exact here, not heuristic -- unlike xs:assert's
arbitrary predicates, which preconditions.py refuses to handle at all.

Two things a real xs:key/xs:unique/xs:keyref can do that a naive
"one selector, one field" model misses:

- A composite key (xs:key/xs:unique with more than one xs:field child)
  is a real, common XSD pattern. Collecting only ONE field per constraint
  (via graph.value, which just returns some one object) silently drops
  every field past the first, so a mismatch in a composite key's second
  (or later) field would never be detected.
- xs:keyref's `refer` attribute (which key/unique constraint it points at)
  is part of its identity too: two keyrefs with the same selector/fields
  but different `refer` targets are not equivalent, but comparing only
  selector+fields would say they are.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class IdentityConstraintMismatch:
    constraint_kind: str
    official_selector: str | None
    generated_selector: str | None
    official_detail: str | None = None
    generated_detail: str | None = None


@dataclass(frozen=True)
class _ConstraintEntry:
    selector: str
    fields: tuple[str, ...]
    refer: str | None = None


def _constraint_entry(graph: Graph, constraint: URIRef, kind: str) -> _ConstraintEntry:
    selector = str(graph.value(constraint, XSDO.selector))
    fields = tuple(sorted(str(f) for f in graph.objects(constraint, XSDO.field)))
    refer = None
    if kind == str(XSDO.KeyRef):
        refer_value = graph.value(constraint, XSDO.refer)
        refer = str(refer_value) if refer_value is not None else None
    return _ConstraintEntry(selector=selector, fields=fields, refer=refer)


def _constraints_by_kind(graph: Graph, type_uri: URIRef) -> dict[str, list[_ConstraintEntry]]:
    result: dict[str, list[_ConstraintEntry]] = {}
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        kind = str(graph.value(constraint, RDF.type))
        result.setdefault(kind, []).append(_constraint_entry(graph, constraint, kind))
    return result


def _describe_selectors(entries: list[_ConstraintEntry]) -> str | None:
    if not entries:
        return None
    return ", ".join(sorted(entry.selector for entry in entries))


def _format_entry(entry: _ConstraintEntry) -> str:
    text = f"{entry.selector} [{', '.join(entry.fields)}]"
    if entry.refer is not None:
        text += f" refer={entry.refer}"
    return text


def _describe_detail(entries: list[_ConstraintEntry]) -> str | None:
    if not entries:
        return None
    return ", ".join(sorted(_format_entry(entry) for entry in entries))


def compare(
    official_graph: Graph,
    generated_graph: Graph,
    official_type: URIRef,
    generated_type: URIRef,
) -> list[IdentityConstraintMismatch]:
    official_constraints = _constraints_by_kind(official_graph, official_type)
    generated_constraints = _constraints_by_kind(generated_graph, generated_type)

    mismatches = []
    all_kinds = set(official_constraints) | set(generated_constraints)
    for kind in all_kinds:
        official_entries = official_constraints.get(kind, [])
        generated_entries = generated_constraints.get(kind, [])
        if set(official_entries) != set(generated_entries):
            mismatches.append(
                IdentityConstraintMismatch(
                    constraint_kind=kind,
                    official_selector=_describe_selectors(official_entries),
                    generated_selector=_describe_selectors(generated_entries),
                    official_detail=_describe_detail(official_entries),
                    generated_detail=_describe_detail(generated_entries),
                )
            )
    return mismatches
