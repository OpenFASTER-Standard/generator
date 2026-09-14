"""(structural case, leaf value choices) -> a real, well-formed,
namespace-qualified XML fragment, for validating one complex type's
shape independently of the rest of a real document.
"""
from __future__ import annotations

from lxml import etree
from rdflib import Graph, Namespace, URIRef

from equivalence.structural_cases import StructuralCase

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


def build(
    graph: Graph,
    root_element: URIRef,
    target_namespace: str,
    case: StructuralCase,
    leaf_values: dict[URIRef, str],
) -> bytes:
    nsmap = {"tns": target_namespace}
    root_name = str(graph.value(root_element, XSDO.name))
    root = etree.Element(f"{{{target_namespace}}}{root_name}", nsmap=nsmap)

    for occurrence in case.occurrences:
        term_name = str(graph.value(occurrence.term, XSDO.name))
        for _ in range(occurrence.count):
            child = etree.SubElement(root, f"{{{target_namespace}}}{term_name}")
            if occurrence.term in leaf_values:
                child.text = leaf_values[occurrence.term]

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
