"""Layers optional display hints onto an already-created property shape --
never creates one, and never touches the citation data annotate_xpath()/
annotate_svg() already put there (see this module's own design spec for
why clear_property_shape() from rdf.py is deliberately NOT reused here).
"""
from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import SH

from annotation_model.namespaces import DASH, GEN
from annotation_model.rdf import _iri_segment


class PropertyShapeNotFoundError(LookupError):
    """Raised when annotate_display_hint() is given a (standard,
    shape_name, property_name) that does not already name a real
    sh:PropertyShape -- this function only ever adds to an existing
    property shape and must never silently create an orphan hint-only
    subject for a typo'd or since-renamed citation."""


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

    if (property_shape_iri, RDF.type, SH.PropertyShape) not in graph:
        raise PropertyShapeNotFoundError(
            f"no sh:PropertyShape at {property_shape_iri} for "
            f"(standard={standard!r}, shape_name={shape_name!r}, property_name={property_name!r}) "
            "-- annotate_display_hint() only adds to an existing citation, it never creates one"
        )

    # Each hint predicate is cleared and re-added only when the caller
    # actually supplies a value for it -- omitting one on a later call
    # must leave that hint exactly as it was, not delete it.
    if label is not None:
        graph.remove((property_shape_iri, SH.name, None))
        graph.add((property_shape_iri, SH.name, Literal(label)))
    if order is not None:
        graph.remove((property_shape_iri, SH.order, None))
        graph.add((property_shape_iri, SH.order, Literal(order)))
    if editor is not None:
        graph.remove((property_shape_iri, DASH.editor, None))
        graph.add((property_shape_iri, DASH.editor, editor))

    return property_shape_iri
