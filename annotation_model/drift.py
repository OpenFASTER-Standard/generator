"""Detects drift by re-resolving a stored annotation's selector."""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from annotation_model.namespaces import GEN, OA
from annotation_model.outcomes import Status
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath


@dataclass(frozen=True)
class DriftResult:
    changed: bool
    current_status: Status


def check_xpath_drift(graph: Graph, *, property_shape_iri: URIRef, retrieval_uri: str) -> DriftResult:
    stored_hash = str(next(graph.objects(property_shape_iri, GEN.contentHash)))
    annotation_iri = next(graph.objects(property_shape_iri, PROV.wasDerivedFrom))
    target = next(graph.objects(annotation_iri, OA.hasTarget))
    selector = next(graph.objects(target, OA.hasSelector))
    xpath = str(next(graph.objects(selector, RDF.value)))

    outcome = resolve_xpath(retrieval_uri, xpath)
    if outcome.status != Status.RESOLVED:
        return DriftResult(changed=True, current_status=outcome.status)

    current_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    return DriftResult(changed=current_hash != stored_hash, current_status=Status.RESOLVED)
