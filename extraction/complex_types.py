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

from extraction.declarations import extract_attribute_declaration, extract_element_declaration
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

    if xsd_type.base_type is not None:
        graph.add((uri, XSDO.extends, type_uri(xsd_type.base_type, uri)))

    content_node = _extract_content_model(graph, xsd_type.content, uri)
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


def _extract_content_model(graph: Graph, group, owner_uri: URIRef) -> BNode:
    if group.model == "all":
        raise NotImplementedError(
            "xs:all is confirmed absent from every real file this extractor "
            "targets -- see the extraction design spec's census"
        )

    group_node = BNode()
    graph.add(
        (group_node, RDF.type, XSDO.Choice if group.model == "choice" else XSDO.Sequence)
    )

    for position, particle in enumerate(group.iter_model(), start=1):
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
