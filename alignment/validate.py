"""Referential-integrity validation for SSSOM mappings -- a mapping's
subject and object must each resolve to something real, on their own
side, or this module raises rather than letting mappings_to_graph()
silently mint a triple pointing at nothing.
"""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import OWL, SH

from alignment.sssom import Mapping, load_sssom_mappings


class UnresolvedSubjectError(LookupError):
    """Raised when one or more mappings' subject_id does not name a real
    sh:PropertyShape in the generator graph -- a typo'd or
    since-renamed citation must not silently produce an alignment
    triple that points at nothing. Names every bad subject found, not
    just the first, so a curator fixing a many-row file sees every
    failure in one pass."""


class UnresolvedObjectError(LookupError):
    """Raised when one or more mappings' object_id does not name a real
    owl:Class or owl:NamedIndividual in the institutional-ontology
    graph -- a typo'd or removed concept must not silently produce an
    alignment triple that points at nothing. Names every bad object
    found, not just the first."""


class EmptyInstitutionalGraphError(ValueError):
    """Raised when institutional_graph has zero owl:Class/
    owl:NamedIndividual triples at all -- indistinguishable, by content
    alone, from "the caller forgot to call load_institutional_ontology()"
    rather than a real mapping pointing at a genuinely missing concept.
    Distinct from UnresolvedObjectError so a caller sees "you didn't load
    anything" instead of the more alarming "your mappings are wrong."""


def validate_mappings(
    mappings: list[Mapping], *, generator_graph: Graph, institutional_graph: Graph
) -> None:
    # Two full passes rather than raising on the first bad mapping: all
    # subjects are checked (and reported together) before any object is
    # checked, so a mapping with both a bad subject and a bad object
    # still raises UnresolvedSubjectError first, deterministically --
    # matching the existing contract that a bad-subject mapping always
    # raises UnresolvedSubjectError regardless of its object.
    bad_subjects = [
        mapping
        for mapping in mappings
        if (URIRef(mapping.subject_id), RDF.type, SH.PropertyShape) not in generator_graph
    ]
    if bad_subjects:
        raise UnresolvedSubjectError(
            "; ".join(
                f"mapping subject {m.subject_id!r} ({m.subject_label!r}) does not name a "
                "real sh:PropertyShape in the generator graph"
                for m in bad_subjects
            )
        )

    if (None, RDF.type, OWL.Class) not in institutional_graph and (
        None,
        RDF.type,
        OWL.NamedIndividual,
    ) not in institutional_graph:
        raise EmptyInstitutionalGraphError(
            "institutional_graph has no owl:Class or owl:NamedIndividual triples at all -- "
            "did you forget to call load_institutional_ontology()?"
        )

    bad_objects = [
        mapping
        for mapping in mappings
        if (URIRef(mapping.object_id), RDF.type, OWL.Class) not in institutional_graph
        and (URIRef(mapping.object_id), RDF.type, OWL.NamedIndividual) not in institutional_graph
    ]
    if bad_objects:
        raise UnresolvedObjectError(
            "; ".join(
                f"mapping object {m.object_id!r} ({m.object_label!r}) does not name a real "
                "owl:Class or owl:NamedIndividual in the institutional-ontology graph"
                for m in bad_objects
            )
        )


def load_and_validate_mappings(
    path: Path | str, *, generator_graph: Graph, institutional_graph: Graph
) -> list[Mapping]:
    """Load a SSSOM TSV and validate it in one call -- the real,
    designed pipeline (load -> validate -> mint triples) is easy to
    forget to compose by hand; this is the one function a consumer
    should copy instead of reassembling load_sssom_mappings() +
    validate_mappings() themselves."""
    mappings = load_sssom_mappings(path)
    validate_mappings(mappings, generator_graph=generator_graph, institutional_graph=institutional_graph)
    return mappings
