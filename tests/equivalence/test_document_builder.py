"""Tests for building a real XML fragment from a structural case."""
import pytest
from lxml import etree
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.document_builder import build
from equivalence.structural_cases import ParticleOccurrence, StructuralCase

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
EX = Namespace("https://example.org/test/")
NS = "urn:example:test:v1"


def test_build_produces_namespace_qualified_root_and_children():
    graph = Graph()
    graph.add((EX.NatPStruct, XSDO.name, Literal("NatPStruct")))
    graph.add((EX.Vorname, XSDO.name, Literal("Vorname")))
    graph.add((EX.Vorname, RDF.type, XSDO.ElementDeclaration))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Vorname, count=1),),
        should_be_valid=True,
    )
    xml_bytes = build(
        graph, EX.NatPStruct, NS, case, leaf_values={EX.Vorname: "Hans"}
    )

    root = etree.fromstring(xml_bytes)
    assert root.tag == f"{{{NS}}}NatPStruct"
    children = list(root)
    assert len(children) == 1
    assert children[0].tag == f"{{{NS}}}Vorname"
    assert children[0].text == "Hans"


def test_build_repeats_a_particle_the_requested_number_of_times():
    graph = Graph()
    graph.add((EX.Root, XSDO.name, Literal("Root")))
    graph.add((EX.Item, XSDO.name, Literal("Item")))
    graph.add((EX.Item, RDF.type, XSDO.ElementDeclaration))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Item, count=3),),
        should_be_valid=True,
    )
    xml_bytes = build(graph, EX.Root, NS, case, leaf_values={EX.Item: "x"})

    root = etree.fromstring(xml_bytes)
    assert len(list(root)) == 3
    assert all(c.tag == f"{{{NS}}}Item" for c in root)


def test_build_omits_a_particle_with_zero_count():
    graph = Graph()
    graph.add((EX.Root, XSDO.name, Literal("Root")))
    graph.add((EX.Optional, XSDO.name, Literal("Optional")))
    graph.add((EX.Optional, RDF.type, XSDO.ElementDeclaration))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Optional, count=0),),
        should_be_valid=True,
    )
    xml_bytes = build(graph, EX.Root, NS, case, leaf_values={})

    root = etree.fromstring(xml_bytes)
    assert len(list(root)) == 0


def test_build_raises_instead_of_silently_building_a_none_named_element():
    """A particle whose term is a nested xsdo:Choice group (not an
    xsdo:ElementDeclaration) is outside the Sequence-only MVP scope cut.
    Before this fix, build() would call str(graph.value(term, XSDO.name))
    on a term with no xsdo:name, getting the literal string "None" and
    silently emitting a "<tns:None/>" element -- garbage that both real
    schemas reject, making the whole thing look like a clean "no
    divergence" instead of the loud failure the scope cut should produce."""
    graph = Graph()
    graph.add((EX.Root, XSDO.name, Literal("Root")))
    graph.add((EX.NestedChoice, RDF.type, XSDO.Choice))

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.NestedChoice, count=1),),
        should_be_valid=True,
    )

    with pytest.raises(NotImplementedError, match="Choice"):
        build(graph, EX.Root, NS, case, leaf_values={})
