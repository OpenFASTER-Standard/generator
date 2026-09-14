"""(structural case, leaf value choices) -> a real, well-formed,
namespace-qualified XML fragment, for validating one complex type's
shape independently of the rest of a real document.
"""
from __future__ import annotations

from lxml import etree
from rdflib import RDF, Graph, Namespace, URIRef

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
        if (occurrence.term, RDF.type, XSDO.ElementDeclaration) not in graph:
            # The Sequence-only MVP scope cut only checks the *content
            # model* itself (structural_cases.enumerate_cases raises for
            # a non-Sequence content model) -- it never checked each
            # particle's own *term*. A Sequence containing a nested
            # xsdo:Choice/xsdo:All group as one of its particles would
            # otherwise silently fall through to str(None) below and
            # build a literal "<tns:None/>" element instead of loudly
            # refusing, which both schemas then (correctly) reject --
            # reported as "no divergence", a silent wrong "pass" rather
            # than the loud failure this scope cut is supposed to produce.
            actual_type = graph.value(occurrence.term, RDF.type)
            raise NotImplementedError(
                "document_builder only builds particles whose term is an "
                f"xsdo:ElementDeclaration, got {actual_type} for term "
                f"{occurrence.term}"
            )
        term_name = str(graph.value(occurrence.term, XSDO.name))
        for _ in range(occurrence.count):
            child = etree.SubElement(root, f"{{{target_namespace}}}{term_name}")
            if occurrence.term in leaf_values:
                child.text = leaf_values[occurrence.term]

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
