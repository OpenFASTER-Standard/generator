"""Tests for build_structure: walking a real xsdo:-shaped graph into a
plain, JSON-serializable structure tree. Uses small, hand-built graphs
with the exact real predicates extraction/ produces -- not mocks."""
from rdflib import RDF, BNode, Graph, Literal, Namespace

from reporting.data import XSDO, build_structure

# Namespace deliberately ends with "#", not "/" -- matching the real shape
# extraction.uris.global_uri always produces (f"{target_namespace}#{name}"),
# since build_structure's own namespace-grouping splits on "#".
EX = Namespace("https://example.org/test#")
NS = "https://example.org/test"


def test_abstract_base_and_extending_type_with_nested_choice():
    graph = Graph()

    # Abstract base type with one element particle.
    graph.add((EX.BaseType, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.BaseType, XSDO.name, Literal("BaseType")))
    graph.add((EX.BaseType, XSDO.abstract, Literal(True)))
    base_content = BNode()
    graph.add((EX.BaseType, XSDO.contentModel, base_content))
    graph.add((base_content, RDF.type, XSDO.Sequence))
    base_particle = BNode()
    graph.add((base_content, XSDO.hasParticle, base_particle))
    graph.add((base_particle, XSDO.particlePosition, Literal(1)))
    graph.add((base_particle, XSDO.minOccurs, Literal(1)))
    graph.add((base_particle, XSDO.maxOccurs, Literal(1)))
    graph.add((base_particle, XSDO["term"], EX.BaseElement))
    graph.add((EX.BaseElement, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.BaseElement, XSDO.name, Literal("BaseElement")))

    # Extending type: extends BaseType, adds its own Choice with 2
    # elements, one required attribute use, and one identity constraint.
    graph.add((EX.ExtType, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.ExtType, XSDO.name, Literal("ExtType")))
    graph.add((EX.ExtType, XSDO.abstract, Literal(False)))
    graph.add((EX.ExtType, XSDO.extends, EX.BaseType))
    ext_content = BNode()
    graph.add((EX.ExtType, XSDO.contentModel, ext_content))
    graph.add((ext_content, RDF.type, XSDO.Sequence))
    outer_particle = BNode()
    graph.add((ext_content, XSDO.hasParticle, outer_particle))
    graph.add((outer_particle, XSDO.particlePosition, Literal(1)))
    graph.add((outer_particle, XSDO.minOccurs, Literal(1)))
    graph.add((outer_particle, XSDO.maxOccurs, Literal(1)))
    choice_node = BNode()
    graph.add((outer_particle, XSDO["term"], choice_node))
    graph.add((choice_node, RDF.type, XSDO.Choice))
    for i, elem_name in enumerate(("OptionA", "OptionB"), start=1):
        elem_particle = BNode()
        graph.add((choice_node, XSDO.hasParticle, elem_particle))
        graph.add((elem_particle, XSDO.particlePosition, Literal(i)))
        graph.add((elem_particle, XSDO.minOccurs, Literal(1)))
        graph.add((elem_particle, XSDO.maxOccurs, Literal(1)))
        elem_uri = EX[elem_name]
        graph.add((elem_particle, XSDO["term"], elem_uri))
        graph.add((elem_uri, RDF.type, XSDO.ElementDeclaration))
        graph.add((elem_uri, XSDO.name, Literal(elem_name)))
    use_node = BNode()
    graph.add((EX.ExtType, XSDO.hasAttributeUse, use_node))
    graph.add((use_node, XSDO.required, Literal(True)))
    graph.add((use_node, XSDO["term"], EX.SomeAttr))
    graph.add((EX.SomeAttr, RDF.type, XSDO.AttributeDeclaration))
    graph.add((EX.SomeAttr, XSDO.name, Literal("SomeAttr")))
    graph.add((EX.ExtType, XSDO.hasIdentityConstraint, EX.SomeConstraint))
    graph.add((EX.SomeConstraint, RDF.type, XSDO.Unique))
    graph.add((EX.SomeConstraint, XSDO.selector, Literal("./Row")))
    graph.add((EX.SomeConstraint, XSDO.field, Literal("@id")))

    structure = build_structure(graph)

    assert set(structure.keys()) == {NS}
    complex_types = {t["name"]: t for t in structure[NS]["complexTypes"]}
    assert set(complex_types) == {"BaseType", "ExtType"}

    base = complex_types["BaseType"]
    assert base["abstract"] is True
    assert base["extends"] is None
    assert base["contentModel"]["kind"] == "Sequence"
    assert len(base["contentModel"]["particles"]) == 1

    ext = complex_types["ExtType"]
    assert ext["abstract"] is False
    assert ext["extends"] == str(EX.BaseType)
    outer = ext["contentModel"]
    assert outer["kind"] == "Sequence"
    assert len(outer["particles"]) == 1
    nested = outer["particles"][0]["term"]["nested"]
    assert nested["kind"] == "Choice"
    assert len(nested["particles"]) == 2
    assert ext["attributeUses"] == [{"required": True, "ref": str(EX.SomeAttr)}]
    assert ext["identityConstraints"] == [
        {"kind": "Unique", "selector": "./Row", "fields": ["@id"], "refer": None}
    ]


def test_unbounded_particle_is_reported_as_the_string_unbounded():
    graph = Graph()
    graph.add((EX.T, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((EX.T, XSDO.name, Literal("T")))
    graph.add((EX.T, XSDO.abstract, Literal(False)))
    content = BNode()
    graph.add((EX.T, XSDO.contentModel, content))
    graph.add((content, RDF.type, XSDO.Sequence))
    particle = BNode()
    graph.add((content, XSDO.hasParticle, particle))
    graph.add((particle, XSDO.particlePosition, Literal(1)))
    graph.add((particle, XSDO.minOccurs, Literal(0)))
    graph.add((particle, XSDO.maxOccursUnbounded, Literal(True)))
    graph.add((particle, XSDO["term"], EX.Elem))
    graph.add((EX.Elem, RDF.type, XSDO.ElementDeclaration))
    graph.add((EX.Elem, XSDO.name, Literal("Elem")))

    structure = build_structure(graph)

    particle_data = structure[NS]["complexTypes"][0]["contentModel"]["particles"][0]
    assert particle_data["minOccurs"] == 0
    assert particle_data["maxOccurs"] == "unbounded"


def test_anonymous_type_has_no_name_but_still_gets_a_full_entry():
    graph = Graph()
    anon_uri = EX["Owner.Type"]
    graph.add((anon_uri, RDF.type, XSDO.ComplexTypeDefinition))
    graph.add((anon_uri, XSDO.abstract, Literal(False)))
    content = BNode()
    graph.add((anon_uri, XSDO.contentModel, content))
    graph.add((content, RDF.type, XSDO.Sequence))

    structure = build_structure(graph)

    entry = structure[NS]["complexTypes"][0]
    assert entry["name"] is None
    assert entry["uri"] == str(anon_uri)


def test_simple_type_with_facets_enumeration_pattern_and_union():
    graph = Graph()
    graph.add((EX.EnumType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.EnumType, XSDO.name, Literal("EnumType")))
    for value in ("A", "B"):
        value_node = BNode()
        graph.add((EX.EnumType, XSDO.hasEnumerationValue, value_node))
        graph.add((value_node, XSDO.literalValue, Literal(value)))

    graph.add((EX.LenType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.LenType, XSDO.name, Literal("LenType")))
    graph.add((EX.LenType, XSDO.length, Literal(5)))
    graph.add((EX.LenType, XSDO.pattern, Literal("[A-Z]{5}")))

    graph.add((EX.UnionType, RDF.type, XSDO.SimpleTypeDefinition))
    graph.add((EX.UnionType, XSDO.name, Literal("UnionType")))
    graph.add((EX.UnionType, XSDO.hasUnionMember, EX.EnumType))
    graph.add((EX.UnionType, XSDO.hasUnionMember, EX.LenType))

    structure = build_structure(graph)

    simple_types = {t["name"]: t for t in structure[NS]["simpleTypes"]}
    assert sorted(simple_types["EnumType"]["enumeration"]) == ["A", "B"]
    assert simple_types["LenType"]["facets"] == {"length": 5}
    assert simple_types["LenType"]["patterns"] == ["[A-Z]{5}"]
    assert set(simple_types["UnionType"]["unionMembers"]) == {
        str(EX.EnumType), str(EX.LenType)
    }
