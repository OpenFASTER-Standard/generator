"""Emits Web Annotation + PROV-O + SHACL triples for a resolved citation."""
from __future__ import annotations

from urllib.parse import quote

from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.namespaces import GEN, OA


def _iri_segment(value: str) -> str:
    # Percent-encode each IRI segment independently (not the joined
    # path) so a "/" inside e.g. shape_name can never be mistaken for a
    # path separator -- without this, ("A", "B/C", "D") and
    # ("A", "B", "C/D") would mint the identical IRI.
    return quote(value, safe="")


def clear_property_shape(graph: Graph, property_shape_iri: URIRef) -> None:
    """Removes every triple a prior annotate_*() call asserted for this
    exact property shape -- its own triples, its annotation, and that
    annotation's target/selector blank nodes -- so re-annotating (or
    re-merging a store's file with an updated in-memory graph) never
    leaves two contradictory versions of the same property shape.
    Deliberately never touches the node shape itself.
    """
    annotation_iri = next(graph.objects(property_shape_iri, PROV.wasDerivedFrom), None)
    if annotation_iri is not None:
        for target in list(graph.objects(annotation_iri, OA.hasTarget)):
            for selector in list(graph.objects(target, OA.hasSelector)):
                graph.remove((selector, None, None))
            graph.remove((target, None, None))
        graph.remove((annotation_iri, None, None))
    graph.remove((property_shape_iri, None, None))


def _annotate(
    graph: Graph,
    *,
    standard: str,
    shape_name: str,
    property_name: str,
    source_uri: str,
    content_hash: str,
    selector_type: URIRef,
    selector_value: str,
    page: int | None = None,
) -> URIRef:
    standard_seg = _iri_segment(standard)
    shape_seg = _iri_segment(shape_name)
    property_seg = _iri_segment(property_name)

    node_shape_iri = GEN[f"{standard_seg}/{shape_seg}"]
    property_shape_iri = GEN[f"{standard_seg}/{shape_seg}/{property_seg}"]
    path_iri = GEN[f"{standard_seg}/{shape_seg}/{property_seg}/path"]
    annotation_iri = GEN[f"{standard_seg}/{shape_seg}/{property_seg}/annotation"]

    # Upsert: clear any previous version of this exact property before
    # adding the new one -- see clear_property_shape's own docstring.
    clear_property_shape(graph, property_shape_iri)

    # rdflib.Graph has set semantics -- re-adding an already-present triple
    # is a no-op either way, so this isn't what prevents duplication (that's
    # clear_property_shape() above); it's just clearer to read as intent.
    graph.add((node_shape_iri, RDF.type, SH.NodeShape))
    graph.add((node_shape_iri, SH.property, property_shape_iri))

    graph.add((property_shape_iri, RDF.type, SH.PropertyShape))
    graph.add((property_shape_iri, SH.path, path_iri))
    graph.add((property_shape_iri, PROV.wasDerivedFrom, annotation_iri))
    graph.add((property_shape_iri, GEN.contentHash, Literal(content_hash)))

    target = BNode()
    graph.add((annotation_iri, RDF.type, OA.Annotation))
    graph.add((annotation_iri, OA.hasTarget, target))
    graph.add((target, OA.hasSource, URIRef(source_uri)))
    if page is not None:
        # A dedicated property, not a "#page=N" fragment on hasSource --
        # that would make hasSource differ per page of the same document,
        # breaking "all annotations of document X" as a single triple
        # pattern. hasSource always identifies the document itself.
        graph.add((target, GEN.page, Literal(page)))

    selector = BNode()
    graph.add((target, OA.hasSelector, selector))
    graph.add((selector, RDF.type, selector_type))
    graph.add((selector, RDF.value, Literal(selector_value)))

    return property_shape_iri


def annotate_xpath(
    graph: Graph,
    *,
    standard: str,
    shape_name: str,
    property_name: str,
    xpath: str,
    source_uri: str,
    content_hash: str,
) -> URIRef:
    return _annotate(
        graph,
        standard=standard,
        shape_name=shape_name,
        property_name=property_name,
        source_uri=source_uri,
        content_hash=content_hash,
        selector_type=OA.XPathSelector,
        selector_value=xpath,
    )


def annotate_svg(
    graph: Graph,
    *,
    standard: str,
    shape_name: str,
    property_name: str,
    page: int,
    points: str,
    source_uri: str,
    content_hash: str,
) -> URIRef:
    from annotation_model.selectors.svg import _parse_points  # validation only

    _parse_points(points)  # raises ValueError for a malformed polygon now, not later
    svg_value = f"<svg:polygon points='{points}' xmlns:svg='http://www.w3.org/2000/svg'/>"
    return _annotate(
        graph,
        standard=standard,
        shape_name=shape_name,
        property_name=property_name,
        source_uri=source_uri,
        content_hash=content_hash,
        selector_type=OA.SvgSelector,
        selector_value=svg_value,
        page=page,
    )
