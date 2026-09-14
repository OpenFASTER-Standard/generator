"""Orchestrator: ties preconditions, type correspondence, leaf values,
structural cases, document building, and identity constraints together
into one equivalence check, producing a Report with a concrete
counterexample for every divergence found.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import xmlschema
from rdflib import RDF, Graph, Namespace, URIRef

from equivalence import identity_constraints, preconditions, type_correspondence
from equivalence.document_builder import build
from equivalence.leaf_values import generate as generate_leaf_values
from equivalence.structural_cases import enumerate_cases

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

CONFIDENCE_NOTE = (
    "No counterexample found across an exhaustively enumerated (or "
    "rigorously pairwise-covered) structural scope, combined with exact "
    "leaf-facet boundary checking and exact identity-constraint "
    "comparison. This is not a completeness proof over all possible XML "
    "documents."
)


@dataclass(frozen=True)
class Divergence:
    element_name: str
    xml_document: bytes
    official_verdict: bool
    generated_verdict: bool
    official_error: str | None
    generated_error: str | None


@dataclass(frozen=True)
class Report:
    divergences: list[Divergence] = field(default_factory=list)
    unmatched_official: list[str] = field(default_factory=list)
    unmatched_generated: list[str] = field(default_factory=list)
    identity_constraint_mismatches: list = field(default_factory=list)
    confidence_note: str = CONFIDENCE_NOTE


def _target_namespace(graph: Graph, type_uri: URIRef) -> str:
    ns = graph.value(type_uri, XSDO.targetNamespace)
    return str(ns) if ns is not None else ""


def _leaf_children(graph: Graph, content_model: URIRef) -> list[URIRef]:
    """Direct child ElementDeclarations of a Sequence content model that
    are themselves simple-typed (leaves, not nested complex types)."""
    leaves = []
    for particle in graph.objects(content_model, XSDO.hasParticle):
        # XSDO["term"], not XSDO.term: rdflib.Namespace has a real
        # built-in .term() method, which attribute access resolves to
        # instead of building a URIRef -- a real bug Task 3 hit and
        # documented (see its report). Bracket access avoids it.
        term = graph.value(particle, XSDO["term"])
        term_type = graph.value(term, XSDO.type)
        if term_type is not None and (term_type, RDF.type, XSDO.SimpleTypeDefinition) in graph:
            leaves.append(term)
    return leaves


def _validate(schema: xmlschema.XMLSchema, xml_document: bytes) -> tuple[bool, str | None]:
    """True/None on success. On failure, get a human-readable message by
    calling validate() (which raises) only on the already-known failure
    path -- cheap, and never assumes an exact exception class name."""
    if schema.is_valid(xml_document):
        return True, None
    try:
        schema.validate(xml_document)
    except Exception as error:
        return False, str(error)
    return False, "invalid, but validate() raised no exception"


def _check_one_document(
    element_name: str,
    xml_document: bytes,
    official_schema: xmlschema.XMLSchema,
    generated_schema: xmlschema.XMLSchema,
) -> Divergence | None:
    official_valid, official_error = _validate(official_schema, xml_document)
    generated_valid, generated_error = _validate(generated_schema, xml_document)
    if official_valid == generated_valid:
        return None
    return Divergence(
        element_name=element_name,
        xml_document=xml_document,
        official_verdict=official_valid,
        generated_verdict=generated_valid,
        official_error=official_error,
        generated_error=generated_error,
    )


def check_equivalence(
    official_xsd_path: str,
    generated_xsd_path: str,
    official_graph: Graph,
    generated_graph: Graph,
) -> Report:
    preconditions.check(official_graph)
    preconditions.check(generated_graph)

    official_schema = xmlschema.XMLSchema(official_xsd_path)
    generated_schema = xmlschema.XMLSchema(generated_xsd_path)

    match_result = type_correspondence.match(official_graph, generated_graph)

    divergences: list[Divergence] = []
    mismatches = []

    for official_element, generated_element in match_result.matched:
        official_type = official_graph.value(official_element, XSDO.type)
        generated_type = generated_graph.value(generated_element, XSDO.type)
        element_name = str(official_graph.value(official_element, XSDO.name))

        mismatches.extend(
            identity_constraints.compare(
                official_graph, generated_graph, official_type, generated_type
            )
        )

        official_content_model = official_graph.value(official_type, XSDO.contentModel)
        if official_content_model is None:
            continue  # a simple-typed root element has no structure to vary

        cases = enumerate_cases(official_graph, official_content_model)
        leaf_terms = _leaf_children(official_graph, official_content_model)
        namespace = _target_namespace(official_graph, official_type)

        # One-factor-at-a-time boundary testing, not a full cross-product
        # of every structural case with every leaf's every candidate
        # value (which would both explode combinatorially and, worse,
        # would still risk under-testing if reduced naively). Two passes:
        # (1) vary structural cases while every leaf sits at its own
        # baseline (first should-be-valid) value; (2) vary each leaf's
        # own full candidate set (including its rejection-boundary
        # values) one leaf at a time, holding structure at a single
        # baseline case. A leaf-value bug (e.g. a maxLength mismatch)
        # would never surface if only ever tested at its baseline value
        # -- this is what pass (2) exists to catch.
        leaf_candidates: dict[URIRef, list] = {}
        baseline_leaf_values: dict[URIRef, str] = {}
        for leaf_term in leaf_terms:
            leaf_type = official_graph.value(leaf_term, XSDO.type)
            candidates = generate_leaf_values(official_graph, leaf_type)
            leaf_candidates[leaf_term] = candidates
            baseline_leaf_values[leaf_term] = next(
                c.value for c in candidates if c.should_be_valid
            )

        for case in cases:
            xml_document = build(
                official_graph, official_element, namespace, case, baseline_leaf_values
            )
            divergence = _check_one_document(
                element_name, xml_document, official_schema, generated_schema
            )
            if divergence is not None:
                divergences.append(divergence)

        baseline_case = next(c for c in cases if c.should_be_valid)
        for leaf_term, candidates in leaf_candidates.items():
            for candidate in candidates:
                leaf_values = dict(baseline_leaf_values)
                leaf_values[leaf_term] = candidate.value
                xml_document = build(
                    official_graph, official_element, namespace, baseline_case, leaf_values
                )
                divergence = _check_one_document(
                    element_name, xml_document, official_schema, generated_schema
                )
                if divergence is not None:
                    divergences.append(divergence)

    return Report(
        divergences=divergences,
        unmatched_official=[
            str(official_graph.value(e, XSDO.name)) for e in match_result.official_only
        ],
        unmatched_generated=[
            str(generated_graph.value(e, XSDO.name)) for e in match_result.generated_only
        ],
        identity_constraint_mismatches=mismatches,
    )
