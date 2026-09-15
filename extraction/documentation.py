"""Shared xs:documentation -> xsdo:documentation extraction, used by
every extraction module that can carry real xs:annotation/
xs:documentation content: element/attribute declarations
(extraction.declarations), complex/simple types (extraction.complex_types/
extraction.simple_types), and identity constraints
(extraction.identity_constraints).

Split into its own module (rather than left private inside
extraction.declarations, or imported cross-module some other way) to
avoid a circular import: extraction.declarations already imports
extraction.simple_types (for an attribute/element's own anonymous
simple type), and extraction.simple_types needs this same helper too
(Fix 3, final review) -- declarations.py -> simple_types.py ->
declarations.py would be circular if this stayed there.

Two real forms, both handled uniformly via RDF's own native
language-tagged literal, not a custom shape: FM's own 410 real
xs:documentation blocks are untagged (no xml:lang, German-only);
MiKaDiv-VIB's and KaFE's real documentation is xml:lang="en"/"de"-tagged
instead.
"""
from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def extract_documentation(graph: Graph, uri: URIRef, xsd_component) -> None:
    annotation = xsd_component.annotation
    if annotation is None:
        return
    for doc in annotation.documentation:
        text = (doc.text or "").strip()
        if not text:
            continue
        lang = doc.attrib.get(_XML_LANG)
        literal = Literal(text, lang=lang) if lang else Literal(text)
        graph.add((uri, XSDO.documentation, literal))
