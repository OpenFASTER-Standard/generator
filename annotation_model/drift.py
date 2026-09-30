"""Detects drift by re-resolving a stored annotation's selector."""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from annotation_model.namespaces import GEN, OA
from annotation_model.outcomes import Status
from annotation_model.selectors.svg import canonicalize_and_hash_text, extract_points, resolve_svg_region
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath


@dataclass(frozen=True)
class DriftResult:
    changed: bool
    current_status: Status


def _require(value, message: str):
    if value is None:
        raise ValueError(message)
    return value


def _selector_link(graph: Graph, property_shape_iri: URIRef):
    """Walks property_shape -> annotation -> target -> selector, raising a
    specific ValueError at whichever link is missing instead of a bare
    StopIteration (which, crossing a generator boundary, becomes an
    opaque RuntimeError under PEP 479 -- undiagnosable either way)."""
    stored_hash = _require(
        next(graph.objects(property_shape_iri, GEN.contentHash), None),
        f"{property_shape_iri} has no gen:contentHash",
    )
    annotation_iri = _require(
        next(graph.objects(property_shape_iri, PROV.wasDerivedFrom), None),
        f"{property_shape_iri} has no prov:wasDerivedFrom",
    )
    target = _require(
        next(graph.objects(annotation_iri, OA.hasTarget), None),
        f"annotation {annotation_iri} has no oa:hasTarget",
    )
    selector = _require(
        next(graph.objects(target, OA.hasSelector), None),
        f"target {target} has no oa:hasSelector",
    )
    selector_type = _require(
        next(graph.objects(selector, RDF.type), None),
        f"selector {selector} has no rdf:type",
    )
    return str(stored_hash), target, selector, selector_type


def check_xpath_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult:
    stored_hash, _target, selector, selector_type = _selector_link(graph, property_shape_iri)
    if selector_type != OA.XPathSelector:
        raise ValueError(
            f"{property_shape_iri} is not an XPath-selector shape (found {selector_type}); "
            "use check_svg_drift or check_drift instead"
        )
    xpath = str(next(graph.objects(selector, RDF.value)))

    outcome = resolve_xpath(retrieval_uri, xpath)
    if outcome.status != Status.RESOLVED:
        return DriftResult(changed=True, current_status=outcome.status)

    current_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    return DriftResult(changed=current_hash != stored_hash, current_status=Status.RESOLVED)


def check_svg_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult:
    stored_hash, target, selector, selector_type = _selector_link(graph, property_shape_iri)
    if selector_type != OA.SvgSelector:
        raise ValueError(
            f"{property_shape_iri} is not an SVG-selector shape (found {selector_type}); "
            "use check_xpath_drift or check_drift instead"
        )
    page_literal = _require(next(graph.objects(target, GEN.page), None), f"target {target} has no gen:page")
    svg_value = str(next(graph.objects(selector, RDF.value)))
    points = extract_points(svg_value)

    outcome = resolve_svg_region(retrieval_uri, int(page_literal), points)
    if outcome.status != Status.RESOLVED:
        return DriftResult(changed=True, current_status=outcome.status)

    current_hash = "sha256:" + canonicalize_and_hash_text(outcome.raw_content)
    return DriftResult(changed=current_hash != stored_hash, current_status=Status.RESOLVED)


def check_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult:
    """Dispatches to check_xpath_drift/check_svg_drift by the stored
    selector's rdf:type, so a caller sweeping a mixed store never has to
    know (or guess) which kind a given property shape is -- and no future
    selector type can ship without a drift path, since adding one here is
    the only way to make it resolvable."""
    _stored_hash, _target, _selector, selector_type = _selector_link(graph, property_shape_iri)
    if selector_type == OA.XPathSelector:
        return check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=retrieval_uri)
    if selector_type == OA.SvgSelector:
        return check_svg_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=retrieval_uri)
    raise ValueError(f"no drift checker registered for selector type {selector_type} on {property_shape_iri}")
