"""Layers optional display hints onto an already-created property shape --
never creates one, and never touches the citation data annotate_xpath()/
annotate_svg() already put there (see this module's own design spec for
why clear_property_shape() from rdf.py is deliberately NOT reused here).
"""
from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SH

from annotation_model.namespaces import DASH, GEN
from annotation_model.rdf import _iri_segment


def annotate_display_hint(
    graph: Graph,
    *,
    standard: str,
    shape_name: str,
    property_name: str,
    label: str | None = None,
    order: int | None = None,
    editor: URIRef | None = None,
) -> URIRef:
    property_shape_iri = GEN[
        f"{_iri_segment(standard)}/{_iri_segment(shape_name)}/{_iri_segment(property_name)}"
    ]

    graph.remove((property_shape_iri, SH.name, None))
    graph.remove((property_shape_iri, SH.order, None))
    graph.remove((property_shape_iri, DASH.editor, None))

    if label is not None:
        graph.add((property_shape_iri, SH.name, Literal(label)))
    if order is not None:
        graph.add((property_shape_iri, SH.order, Literal(order)))
    if editor is not None:
        graph.add((property_shape_iri, DASH.editor, editor))

    return property_shape_iri
