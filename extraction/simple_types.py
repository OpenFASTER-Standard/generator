"""Facet and xs:union extraction for xsdo:SimpleTypeDefinition -- the
complete, closed set of 12 standard XSD constraining facets, not just
the subset this project's own census happened to observe (matches this
project's established principle: maxExclusive stays supported even
though unobserved, exactly like xs:key/xs:keyref in identity
constraints -- see the extraction design spec).
"""
from __future__ import annotations

from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from extraction.uris import type_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_XS = "{http://www.w3.org/2001/XMLSchema}"

_SCALAR_FACETS = {
    f"{_XS}length": XSDO.length,
    f"{_XS}minLength": XSDO.minLength,
    f"{_XS}maxLength": XSDO.maxLength,
    f"{_XS}whiteSpace": XSDO.whiteSpace,
    f"{_XS}minInclusive": XSDO.minInclusive,
    f"{_XS}maxInclusive": XSDO.maxInclusive,
    f"{_XS}minExclusive": XSDO.minExclusive,
    f"{_XS}maxExclusive": XSDO.maxExclusive,
    f"{_XS}totalDigits": XSDO.totalDigits,
    f"{_XS}fractionDigits": XSDO.fractionDigits,
}
_ENUMERATION_KEY = f"{_XS}enumeration"
_PATTERN_KEY = f"{_XS}pattern"


def extract_simple_type(graph: Graph, xsd_type, uri: URIRef) -> None:
    graph.add((uri, RDF.type, XSDO.SimpleTypeDefinition))

    facets = getattr(xsd_type, "facets", None) or {}

    for facet_key, predicate in _SCALAR_FACETS.items():
        facet = facets.get(facet_key)
        if facet is not None:
            graph.add((uri, predicate, Literal(facet.value)))

    enumeration_facet = facets.get(_ENUMERATION_KEY)
    if enumeration_facet is not None:
        for value in enumeration_facet.enumeration:
            value_node = BNode()
            graph.add((uri, XSDO.hasEnumerationValue, value_node))
            graph.add((value_node, XSDO.literalValue, Literal(value)))

    pattern_facet = facets.get(_PATTERN_KEY)
    if pattern_facet is not None:
        for regexp in pattern_facet.regexps:
            graph.add((uri, XSDO.pattern, Literal(regexp)))

    member_types = getattr(xsd_type, "member_types", None)
    if member_types is not None:
        for member in member_types:
            member_uri = type_uri(member, uri)
            graph.add((uri, XSDO.hasUnionMember, member_uri))
            if member.name is None:
                extract_simple_type(graph, member, member_uri)
