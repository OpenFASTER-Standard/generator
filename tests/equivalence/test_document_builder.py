"""Tests for building a real XML fragment from a structural case."""
from lxml import etree
from rdflib import Graph, Literal, Namespace

from equivalence.document_builder import build
from equivalence.structural_cases import ParticleOccurrence, StructuralCase

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
EX = Namespace("https://example.org/test/")
NS = "urn:example:test:v1"


def test_build_produces_namespace_qualified_root_and_children():
    graph = Graph()
    graph.add((EX.NatPStruct, XSDO.name, Literal("NatPStruct")))
    graph.add((EX.Vorname, XSDO.name, Literal("Vorname")))

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

    case = StructuralCase(
        occurrences=(ParticleOccurrence(term=EX.Optional, count=0),),
        should_be_valid=True,
    )
    xml_bytes = build(graph, EX.Root, NS, case, leaf_values={})

    root = etree.fromstring(xml_bytes)
    assert len(list(root)) == 0
