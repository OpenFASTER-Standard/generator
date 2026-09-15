"""Walks an already-extracted xsdo: rdflib.Graph into a plain,
JSON-serializable dict for the HTML report's client-side renderer.

Real construct shapes this module reads are exactly what extraction/
already produces (verified directly against the merged source, not
guessed) -- see this plan's own Global Constraints for the full list.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_FACET_PREDICATES = {
    "length": XSDO.length,
    "minLength": XSDO.minLength,
    "maxLength": XSDO.maxLength,
    "whiteSpace": XSDO.whiteSpace,
    "minInclusive": XSDO.minInclusive,
    "maxInclusive": XSDO.maxInclusive,
    "minExclusive": XSDO.minExclusive,
    "maxExclusive": XSDO.maxExclusive,
    "totalDigits": XSDO.totalDigits,
    "fractionDigits": XSDO.fractionDigits,
}


def _json_safe_facet_value(value):
    """Coerce RDF facet value to a JSON-safe Python type.

    Keeps int/bool as-is (already JSON-safe), converts all other types
    (Decimal, date, datetime, etc.) to strings to avoid json.dumps errors.
    """
    python_value = value.toPython()
    if isinstance(python_value, (int, bool)):
        return python_value
    return str(python_value)


def _target_namespace_of(uri: str) -> str:
    return uri.split("#", 1)[0]


def _build_content_model(graph: Graph, group_node) -> dict:
    kind = "Choice" if (group_node, RDF.type, XSDO.Choice) in graph else "Sequence"
    particles = sorted(
        graph.objects(group_node, XSDO.hasParticle),
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )
    return {"kind": kind, "particles": [_build_particle(graph, p) for p in particles]}


def _build_particle(graph: Graph, particle_node) -> dict:
    min_occurs = int(graph.value(particle_node, XSDO.minOccurs))
    unbounded = graph.value(particle_node, XSDO.maxOccursUnbounded)
    if unbounded is not None:
        max_occurs: int | str = "unbounded"
    else:
        max_occurs = int(graph.value(particle_node, XSDO.maxOccurs))
    term = graph.value(particle_node, XSDO["term"])
    is_nested_group = (term, RDF.type, XSDO.Sequence) in graph or (
        term, RDF.type, XSDO.Choice
    ) in graph
    if is_nested_group:
        term_data = {"nested": _build_content_model(graph, term)}
    else:
        term_data = {"ref": str(term)}
    return {"minOccurs": min_occurs, "maxOccurs": max_occurs, "term": term_data}


def _build_attribute_uses(graph: Graph, type_uri: URIRef) -> list[dict]:
    uses = []
    for use in graph.objects(type_uri, XSDO.hasAttributeUse):
        required = bool(graph.value(use, XSDO.required))
        term = graph.value(use, XSDO["term"])
        uses.append({"required": required, "ref": str(term)})
    return uses


def _identity_constraint_kind(graph: Graph, constraint) -> str:
    for kind in ("Key", "Unique", "KeyRef"):
        if (constraint, RDF.type, XSDO[kind]) in graph:
            return kind
    raise ValueError(f"unknown identity constraint kind for {constraint}")


def _build_identity_constraints(graph: Graph, type_uri: URIRef) -> list[dict]:
    constraints = []
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        fields = [str(f) for f in graph.objects(constraint, XSDO.field)]
        refer = graph.value(constraint, XSDO.refer)
        constraints.append(
            {
                "kind": _identity_constraint_kind(graph, constraint),
                "selector": str(graph.value(constraint, XSDO.selector)),
                "fields": fields,
                "refer": str(refer) if refer is not None else None,
            }
        )
    return constraints


def _build_complex_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    extends = graph.value(type_uri, XSDO.extends)
    content_node = graph.value(type_uri, XSDO.contentModel)
    if content_node is None:
        raise ValueError(f"{type_uri} has no xsdo:contentModel")
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "abstract": bool(graph.value(type_uri, XSDO.abstract)),
        "extends": str(extends) if extends is not None else None,
        "contentModel": _build_content_model(graph, content_node),
        "attributeUses": _build_attribute_uses(graph, type_uri),
        "identityConstraints": _build_identity_constraints(graph, type_uri),
    }


def _build_simple_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    facets = {}
    for label, predicate in _FACET_PREDICATES.items():
        value = graph.value(type_uri, predicate)
        if value is not None:
            facets[label] = _json_safe_facet_value(value)
    enumeration = [
        str(graph.value(value_node, XSDO.literalValue))
        for value_node in graph.objects(type_uri, XSDO.hasEnumerationValue)
    ]
    patterns = [str(p) for p in graph.objects(type_uri, XSDO.pattern)]
    union_members = [str(m) for m in graph.objects(type_uri, XSDO.hasUnionMember)]
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "facets": facets,
        "enumeration": enumeration,
        "patterns": patterns,
        "unionMembers": union_members,
    }


def build_structure(graph: Graph) -> dict:
    structure: dict[str, dict[str, list]] = {}

    for type_uri in graph.subjects(RDF.type, XSDO.ComplexTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["complexTypes"].append(_build_complex_type(graph, type_uri))

    for type_uri in graph.subjects(RDF.type, XSDO.SimpleTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["simpleTypes"].append(_build_simple_type(graph, type_uri))

    return structure
