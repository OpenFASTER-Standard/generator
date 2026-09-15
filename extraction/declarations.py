"""Element and attribute declaration extraction: xsdo:name, xsdo:type,
xsdo:defaultValue/xsdo:fixedValue, and xsdo:documentation in both real
forms this project's modules use -- FM's own untagged German
xs:documentation, and MiKaDiv-VIB/KaFE's xml:lang-tagged pairs --
captured uniformly via RDF's own native language-tagged literal, not a
custom shape.

An element's anonymous COMPLEX type is deliberately not handled here
alone (see this module's own NotImplementedError below) -- Task 5's
extraction.complex_types supplies the missing piece via a callback,
since a complex type's own extraction needs this module's functions in
turn. This is genuine mutual recursion between "a type's content is
elements" and "an element's type can be an inline complex type",
resolved via dependency injection instead of a circular import.

extract_documentation is exported (not module-private) so
extraction.complex_types/simple_types/identity_constraints can reuse
the exact same xs:documentation logic for xsdo:ComplexTypeDefinition/
xsdo:SimpleTypeDefinition/xsdo:Key/xsdo:Unique/xsdo:KeyRef subjects,
instead of duplicating it -- see the final-fix-report's Fix 3.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, Graph, Literal, URIRef

from extraction.documentation import XSDO, extract_documentation
from extraction.simple_types import extract_simple_type
from extraction.uris import type_uri

__all__ = [
    "XSDO",
    "extract_documentation",
    "extract_attribute_declaration",
    "extract_element_declaration",
]


def _is_complex(xsd_type) -> bool:
    return isinstance(xsd_type, xmlschema.validators.complex_types.XsdComplexType)


def _extract_type_reference(
    graph: Graph, uri: URIRef, xsd_component, extract_anonymous_complex_type
) -> None:
    referenced_type = xsd_component.type
    referenced_uri = type_uri(referenced_type, uri)
    graph.add((uri, XSDO.type, referenced_uri))

    if referenced_type.name is not None:
        return  # named type -- extracted independently at the top level

    if _is_complex(referenced_type):
        if extract_anonymous_complex_type is None:
            raise NotImplementedError(
                "anonymous complex types need extract_anonymous_complex_type "
                "(see extraction/complex_types.py, which supplies this)"
            )
        extract_anonymous_complex_type(graph, referenced_type, referenced_uri)
        return

    extract_simple_type(graph, referenced_type, referenced_uri)


def extract_element_declaration(
    graph: Graph, xsd_element, uri: URIRef, extract_anonymous_complex_type=None
) -> None:
    graph.add((uri, RDF.type, XSDO.ElementDeclaration))
    graph.add((uri, XSDO.name, Literal(xsd_element.local_name)))
    _extract_type_reference(graph, uri, xsd_element, extract_anonymous_complex_type)
    if xsd_element.default is not None:
        graph.add((uri, XSDO.defaultValue, Literal(xsd_element.default)))
    if xsd_element.fixed is not None:
        graph.add((uri, XSDO.fixedValue, Literal(xsd_element.fixed)))
    extract_documentation(graph, uri, xsd_element)


def extract_attribute_declaration(
    graph: Graph, xsd_attribute, uri: URIRef, extract_anonymous_complex_type=None
) -> None:
    graph.add((uri, RDF.type, XSDO.AttributeDeclaration))
    graph.add((uri, XSDO.name, Literal(xsd_attribute.local_name)))
    _extract_type_reference(graph, uri, xsd_attribute, extract_anonymous_complex_type)
    if xsd_attribute.default is not None:
        graph.add((uri, XSDO.defaultValue, Literal(xsd_attribute.default)))
    if xsd_attribute.fixed is not None:
        graph.add((uri, XSDO.fixedValue, Literal(xsd_attribute.fixed)))
    extract_documentation(graph, uri, xsd_attribute)
