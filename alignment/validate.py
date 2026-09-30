"""Referential-integrity validation for SSSOM mappings -- a mapping's
subject and object must each resolve to something real, on their own
side, or this module raises rather than letting mappings_to_graph()
silently mint a triple pointing at nothing.
"""
from __future__ import annotations

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import OWL, SH

from alignment.sssom import Mapping


class UnresolvedSubjectError(LookupError):
    """Raised when a mapping's subject_id does not name a real
    sh:PropertyShape in the generator graph -- a typo'd or
    since-renamed citation must not silently produce an alignment
    triple that points at nothing."""


class UnresolvedObjectError(LookupError):
    """Raised when a mapping's object_id does not name a real
    owl:Class or owl:NamedIndividual in the institutional-ontology
    graph -- a typo'd or removed concept must not silently produce an
    alignment triple that points at nothing."""


def validate_mappings(
    mappings: list[Mapping], *, generator_graph: Graph, institutional_graph: Graph
) -> None:
    for mapping in mappings:
        subject = URIRef(mapping.subject_id)
        if (subject, RDF.type, SH.PropertyShape) not in generator_graph:
            raise UnresolvedSubjectError(
                f"mapping subject {mapping.subject_id!r} ({mapping.subject_label!r}) "
                "does not name a real sh:PropertyShape in the generator graph"
            )

        obj = URIRef(mapping.object_id)
        if (obj, RDF.type, OWL.Class) not in institutional_graph and (
            obj,
            RDF.type,
            OWL.NamedIndividual,
        ) not in institutional_graph:
            raise UnresolvedObjectError(
                f"mapping object {mapping.object_id!r} ({mapping.object_label!r}) "
                "does not name a real owl:Class or owl:NamedIndividual in the "
                "institutional-ontology graph"
            )
