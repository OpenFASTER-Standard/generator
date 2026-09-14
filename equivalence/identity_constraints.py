"""Direct comparison of xs:key/xs:unique/xs:keyref declarations between
two matched complex types. XSD restricts an identity constraint's
selector/field to a narrow, non-Turing-complete XPath subset, so direct
structural comparison is exact here, not heuristic -- unlike xs:assert's
arbitrary predicates, which preconditions.py refuses to handle at all.
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


def _constraints_by_kind(graph: Graph, type_uri: URIRef) -> dict[str, list[tuple[str, str]]]:
    result = {}
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        kind = str(graph.value(constraint, RDF.type))
        selector = str(graph.value(constraint, XSDO.selector))
        field_path = str(graph.value(constraint, XSDO.field))
        if kind not in result:
            result[kind] = []
        result[kind].append((selector, field_path))
    return result


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
        official_set = set(official_constraints.get(kind, []))
        generated_set = set(generated_constraints.get(kind, []))
        if official_set != generated_set:
            official_selectors = ", ".join(sorted(selector for selector, _ in official_set)) if official_set else None
            generated_selectors = ", ".join(sorted(selector for selector, _ in generated_set)) if generated_set else None
            mismatches.append(
                IdentityConstraintMismatch(
                    constraint_kind=kind,
                    official_selector=official_selectors,
                    generated_selector=generated_selectors,
                )
            )
    return mismatches
