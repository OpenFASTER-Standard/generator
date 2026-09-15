"""Complex-type extraction: xsdo:extends/xsdo:abstract, the recursive
Sequence/Choice content model (including nested groups and anonymous
complex types -- both real, confirmed in this corpus:
MiKaDiv_FM_Personentypen's PersonType nests a Choice inside a Sequence;
MiKaDiv_FM_Meldeart13's KontoListe/Konto nests an anonymous complex
type three levels deep), and xsdo:hasAttributeUse.

This module and extraction.declarations are mutually recursive by
nature (a type's content is elements; an element's type can itself be
an anonymous complex type) -- resolved via dependency injection:
extract_element_declaration_with_recursion below supplies this
module's own extract_complex_type as declarations.py's
extract_anonymous_complex_type callback, instead of a circular import.

Per this plan's Global Constraints, xsdo:hasIdentityConstraint attaches
to the URI of the type that governs the element the constraint is
declared on -- computed the same way as that element's own xsdo:type
link -- not to whatever type's content model happens to contain the
element as a particle. Required for compatibility with the already-
built equivalence checker, whose identity_constraints.compare() reads
this property from a type URI.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from extraction.declarations import (
    extract_attribute_declaration,
    extract_documentation,
    extract_element_declaration,
)
from extraction.identity_constraints import extract_identity_constraints
from extraction.uris import child_uri, type_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


def extract_element_declaration_with_recursion(
    graph: Graph, xsd_element, uri: URIRef
) -> None:
    extract_element_declaration(
        graph, xsd_element, uri, extract_anonymous_complex_type=extract_complex_type
    )
    if xsd_element.identities:
        constraint_owner_uri = type_uri(xsd_element.type, uri)
        extract_identity_constraints(graph, xsd_element, constraint_owner_uri)


def extract_complex_type(graph: Graph, xsd_type, uri: URIRef) -> None:
    graph.add((uri, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((uri, XSDO.targetNamespace, Literal(xsd_type.target_namespace)))
    graph.add((uri, XSDO.abstract, Literal(bool(xsd_type.abstract))))
    if xsd_type.name is not None:
        graph.add((uri, XSDO.name, Literal(xsd_type.local_name)))
    extract_documentation(graph, uri, xsd_type)

    if xsd_type.base_type is not None:
        graph.add((uri, XSDO.extends, type_uri(xsd_type.base_type, uri)))

    content_node = _extract_content_model(
        graph, xsd_type.content, uri, skip_particle_ids=_base_particle_ids(xsd_type)
    )
    graph.add((uri, XSDO.contentModel, content_node))

    base_attribute_names = set(xsd_type.attributes.base_attributes or ())
    for name, attribute in xsd_type.attributes.items():
        if name in base_attribute_names:
            continue
        attribute_uri = child_uri(uri, f"@{attribute.local_name}")
        extract_attribute_declaration(
            graph, attribute, attribute_uri, extract_anonymous_complex_type=extract_complex_type
        )
        use_node = BNode()
        graph.add((uri, XSDO.hasAttributeUse, use_node))
        graph.add((use_node, XSDO.required, Literal(attribute.use == "required")))
        graph.add((use_node, XSDO["term"], attribute_uri))


def _base_particle_ids(xsd_type) -> frozenset[int]:
    """Identities of the particles xsd_type.content.iter_model() returns
    that actually belong to the base type, not to this type's own
    additional content.

    Real, confirmed xmlschema behavior (see this module's own docstring
    and the extraction design spec): for an xs:extension type,
    .content.iter_model() returns ONLY the type's own additional
    particles *when it actually adds any* (e.g. DLZertifiziert, which
    adds its own <xs:sequence>). But when an extension adds ONLY
    attributes (no new element content of its own) -- or is genuinely
    empty -- xmlschema falls back to returning the BASE type's own
    content group, whose particles are the exact same Python objects
    (verified live: identity-equal, not just equal) as
    base_type.content.iter_model()'s. Left unfiltered, those particles
    get re-extracted and re-minted under the EXTENDING type's own URI
    too, duplicating them (confirmed real for 29/53 real extension
    types in this corpus, e.g. PersonNatDatenType re-duplicating
    PersonBasisType's own Anschrift, and Meldeart11 -- a genuinely empty
    extension -- duplicating SelbststaendigeMeldungMitOrdnungsnummerType's
    entire Verwahrkette/Kontopersonen/KontoListe subtree, identity
    constraints included).

    This mirrors exactly how extract_complex_type already handles the
    same real duplication risk for attributes, via
    xsd_type.attributes.base_attributes.
    """
    base_type = xsd_type.base_type
    if base_type is None:
        return frozenset()
    return frozenset(id(p) for p in base_type.content.iter_model())


def _extract_content_model(
    graph: Graph, group, owner_uri: URIRef, skip_particle_ids: frozenset[int] = frozenset()
) -> BNode:
    if group.model == "all":
        raise NotImplementedError(
            "xs:all is confirmed absent from every real file this extractor "
            "targets -- see the extraction design spec's census"
        )

    group_node = BNode()
    graph.add(
        (group_node, RDF.type, XSDO.Choice if group.model == "choice" else XSDO.Sequence)
    )

    position = 0
    for particle in group.iter_model():
        if id(particle) in skip_particle_ids:
            continue  # inherited from the base type -- not this type's own
        position += 1
        particle_node = BNode()
        graph.add((group_node, XSDO.hasParticle, particle_node))
        graph.add((particle_node, XSDO.particlePosition, Literal(position)))
        graph.add((particle_node, XSDO.minOccurs, Literal(particle.min_occurs)))
        if particle.max_occurs is None:
            graph.add((particle_node, XSDO.maxOccursUnbounded, Literal(True)))
        else:
            graph.add((particle_node, XSDO.maxOccurs, Literal(particle.max_occurs)))

        if isinstance(particle, xmlschema.validators.groups.XsdGroup):
            nested_node = _extract_content_model(graph, particle, owner_uri)
            graph.add((particle_node, XSDO["term"], nested_node))
        else:
            element_uri = child_uri(owner_uri, particle.local_name)
            extract_element_declaration_with_recursion(graph, particle, element_uri)
            graph.add((particle_node, XSDO["term"], element_uri))

    return group_node
