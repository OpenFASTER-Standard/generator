"""Emits Web Annotation + PROV-O + SHACL triples for a resolved citation."""
from __future__ import annotations

from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.namespaces import GEN, OA


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
) -> URIRef:
    node_shape_iri = GEN[f"{standard}/{shape_name}"]
    property_shape_iri = GEN[f"{standard}/{shape_name}/{property_name}"]
    path_iri = GEN[f"{standard}/{shape_name}/{property_name}/path"]
    annotation_iri = GEN[f"{standard}/{shape_name}/{property_name}/annotation"]

    if (node_shape_iri, RDF.type, SH.NodeShape) not in graph:
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
    svg_value = f"<svg:polygon points='{points}' xmlns:svg='http://www.w3.org/2000/svg'/>"
    return _annotate(
        graph,
        standard=standard,
        shape_name=shape_name,
        property_name=property_name,
        source_uri=f"{source_uri}#page={page}",
        content_hash=content_hash,
        selector_type=OA.SvgSelector,
        selector_value=svg_value,
    )
