"""Tests for matching ElementDeclarations across two graphs by name."""
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.type_correspondence import XSDO, match

EX = Namespace("https://example.org/test/")


def _element(graph, uri, name):
    graph.add((uri, RDF.type, XSDO.ElementDeclaration))
    graph.add((uri, XSDO.name, Literal(name)))


def test_elements_with_the_same_name_are_matched():
    official = Graph()
    _element(official, EX.OffVorname, "Vorname")
    generated = Graph()
    _element(generated, EX.GenVorname, "Vorname")

    result = match(official, generated)

    assert result.matched == [(EX.OffVorname, EX.GenVorname)]
    assert result.official_only == []
    assert result.generated_only == []


def test_element_only_in_official_is_reported_as_official_only():
    official = Graph()
    _element(official, EX.OffTitel, "Titel")
    generated = Graph()

    result = match(official, generated)

    assert result.matched == []
    assert result.official_only == [EX.OffTitel]


def test_element_only_in_generated_is_reported_as_generated_only():
    official = Graph()
    generated = Graph()
    _element(generated, EX.GenExtra, "Extra")

    result = match(official, generated)

    assert result.matched == []
    assert result.generated_only == [EX.GenExtra]
