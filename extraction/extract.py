"""Top-level orchestration: extract(xsd_path) -> rdflib.Graph. Walks
every global complex/simple type plus the real family's own global
element(s) (confirmed: exactly one, MiKaDivFMRoot -- every other real
element is a local particle, reached recursively via
extraction.complex_types's own content-model walk, not this loop).
"""
from __future__ import annotations

import xmlschema
from rdflib import Graph

from extraction.complex_types import extract_complex_type, extract_element_declaration_with_recursion
from extraction.simple_types import extract_simple_type
from extraction.uris import global_uri

_XS_NAMESPACE_PREFIX = "{http://www.w3.org/2001/XMLSchema}"


def extract(xsd_path: str) -> Graph:
    schema = xmlschema.XMLSchema(xsd_path)
    graph = Graph()

    for name, xsd_type in schema.maps.types.items():
        if name.startswith(_XS_NAMESPACE_PREFIX):
            continue
        uri = global_uri(xsd_type.target_namespace, xsd_type.local_name)
        if isinstance(xsd_type, xmlschema.validators.complex_types.XsdComplexType):
            extract_complex_type(graph, xsd_type, uri)
        elif isinstance(xsd_type, xmlschema.validators.simple_types.XsdSimpleType):
            extract_simple_type(graph, xsd_type, uri)

    for name, xsd_element in schema.maps.elements.items():
        if name.startswith(_XS_NAMESPACE_PREFIX):
            continue
        uri = global_uri(xsd_element.target_namespace, xsd_element.local_name)
        extract_element_declaration_with_recursion(graph, xsd_element, uri)

    return graph
