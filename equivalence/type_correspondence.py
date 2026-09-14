"""Matches xsdo:ElementDeclarations across two graphs by their real XSD
element name -- not by type name, since the generated graph is allowed
to organize/name its types differently than the official schema. Any
official element with no same-named counterpart, or vice versa, is
reported explicitly, never silently skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class MatchResult:
    matched: list[tuple[URIRef, URIRef]] = field(default_factory=list)
    official_only: list[URIRef] = field(default_factory=list)
    generated_only: list[URIRef] = field(default_factory=list)


def _elements_by_name(graph: Graph) -> dict[str, URIRef]:
    result = {}
    for element in graph.subjects(RDF.type, XSDO.ElementDeclaration):
        name = graph.value(element, XSDO.name)
        result[str(name)] = element
    return result


def match(official_graph: Graph, generated_graph: Graph) -> MatchResult:
    official_by_name = _elements_by_name(official_graph)
    generated_by_name = _elements_by_name(generated_graph)

    matched = []
    official_only = []
    for name, official_element in official_by_name.items():
        if name in generated_by_name:
            matched.append((official_element, generated_by_name[name]))
        else:
            official_only.append(official_element)

    generated_only = [
        element
        for name, element in generated_by_name.items()
        if name not in official_by_name
    ]

    return MatchResult(matched=matched, official_only=official_only, generated_only=generated_only)
