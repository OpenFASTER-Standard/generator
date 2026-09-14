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
from equivalence.structural_cases import StructuralCase, enumerate_cases

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

CONFIDENCE_NOTE = (
    "No counterexample found across an exhaustively enumerated (or "
    "rigorously pairwise-covered) structural scope, combined with exact "
    "leaf-facet boundary checking and exact identity-constraint "
    "comparison. This is not a completeness proof over all possible XML "
    "documents."
)

# The observed substring xmlschema's own error message uses when a document's
# root element isn't declared as a top-level (global) element of the schema
# at all -- as opposed to a real facet/structural difference. Confirmed live
# against xmlschema 3.x: validating a document rooted at a local (nested,
# non-global) element produces
#   "Reason: '{ns}ElementName' is not an element of the schema"
# Used to tell "we couldn't even attempt to check this element as a
# document root" apart from "we checked it and found no divergence".
ROOT_INELIGIBLE_MARKER = "is not an element of the schema"


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
    not_checked: list[str] = field(default_factory=list)
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
) -> tuple[Divergence | None, bool]:
    """Returns (divergence_or_None, is_root_ineligible). is_root_ineligible
    is True only when both sides agree the document is invalid *and* both
    error messages point at the same "this element can't stand as a
    document root" reason -- see ROOT_INELIGIBLE_MARKER."""
    official_valid, official_error = _validate(official_schema, xml_document)
    generated_valid, generated_error = _validate(generated_schema, xml_document)
    is_root_ineligible = (
        not official_valid
        and not generated_valid
        and official_error is not None
        and generated_error is not None
        and ROOT_INELIGIBLE_MARKER in official_error
        and ROOT_INELIGIBLE_MARKER in generated_error
    )
    if official_valid == generated_valid:
        return None, is_root_ineligible
    return (
        Divergence(
            element_name=element_name,
            xml_document=xml_document,
            official_verdict=official_valid,
            generated_verdict=generated_valid,
            official_error=official_error,
            generated_error=generated_error,
        ),
        is_root_ineligible,
    )


def _find_case_with_leaf_present(cases: list[StructuralCase], leaf_term: URIRef) -> StructuralCase:
    """A valid structural case in which the given leaf actually occurs at
    least once -- needed because the "first" valid case (every optional
    particle absent) would otherwise mean an optional leaf's own boundary
    values are never tested (every candidate produces the same,
    leaf-omitted document)."""
    for case in cases:
        if not case.should_be_valid:
            continue
        for occurrence in case.occurrences:
            if occurrence.term == leaf_term and occurrence.count >= 1:
                return case
    raise ValueError(f"no valid structural case has {leaf_term} present at least once")


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
    not_checked: list[str] = []

    for official_element, generated_element in match_result.matched:
        official_type = official_graph.value(official_element, XSDO.type)
        generated_type = generated_graph.value(generated_element, XSDO.type)
        element_name = str(official_graph.value(official_element, XSDO.name))

        # graph.objects(None, predicate) is a real rdflib wildcard match
        # (matches every subject in the graph) -- an ElementDeclaration
        # lacking xsdo:type would otherwise pass None through to compare()
        # and risk pulling in unrelated constraints from elsewhere in the
        # graph rather than failing cleanly, mirroring the existing
        # official_content_model-is-None guard below.
        if official_type is not None and generated_type is not None:
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
            try:
                baseline_leaf_values[leaf_term] = next(
                    c.value for c in candidates if c.should_be_valid
                )
            except StopIteration:
                raise ValueError(
                    f"no should-be-valid candidate value generated for leaf "
                    f"{leaf_term} -- leaf_values.generate must always "
                    "produce at least one valid case"
                ) from None

        element_documents_checked = 0
        element_all_root_ineligible = True

        for case in cases:
            xml_document = build(
                official_graph, official_element, namespace, case, baseline_leaf_values
            )
            divergence, root_ineligible = _check_one_document(
                element_name, xml_document, official_schema, generated_schema
            )
            element_documents_checked += 1
            element_all_root_ineligible = element_all_root_ineligible and root_ineligible
            if divergence is not None:
                divergences.append(divergence)

        # Each leaf gets its own structural case in which it actually
        # occurs at least once -- reusing one shared baseline case (always
        # the "every optional particle absent" case, since
        # _occurrence_options lists minOccurs first and itertools.product
        # yields the all-first-options combination first) would mean an
        # optional leaf's own candidate values are never tested: every
        # candidate would build into a document where that leaf is simply
        # omitted, so a real facet divergence on an optional leaf could
        # never be detected.
        for leaf_term, candidates in leaf_candidates.items():
            case_with_leaf_present = _find_case_with_leaf_present(cases, leaf_term)
            for candidate in candidates:
                leaf_values = dict(baseline_leaf_values)
                leaf_values[leaf_term] = candidate.value
                xml_document = build(
                    official_graph,
                    official_element,
                    namespace,
                    case_with_leaf_present,
                    leaf_values,
                )
                divergence, root_ineligible = _check_one_document(
                    element_name, xml_document, official_schema, generated_schema
                )
                element_documents_checked += 1
                element_all_root_ineligible = element_all_root_ineligible and root_ineligible
                if divergence is not None:
                    divergences.append(divergence)

        if element_documents_checked > 0 and element_all_root_ineligible:
            # Every document generated for this element was rejected by
            # *both* schemas for the same "this element can't stand as a
            # document root" reason -- structurally, we never managed to
            # check it at all, which must not be indistinguishable from
            # "checked and found equivalent".
            not_checked.append(element_name)

    return Report(
        divergences=divergences,
        unmatched_official=[
            str(official_graph.value(e, XSDO.name)) for e in match_result.official_only
        ],
        unmatched_generated=[
            str(generated_graph.value(e, XSDO.name)) for e in match_result.generated_only
        ],
        identity_constraint_mismatches=mismatches,
        not_checked=not_checked,
    )
