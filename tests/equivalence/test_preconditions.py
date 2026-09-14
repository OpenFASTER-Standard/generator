"""Tests for the xs:assert/xs:any guardrail."""
import pytest
from rdflib import RDF, Graph, Namespace

from equivalence.preconditions import XSDO, UnsupportedConstructError, check

EX = Namespace("https://example.org/test/")


def test_check_passes_on_a_graph_with_no_assertion_or_wildcard():
    graph = Graph()
    graph.add((EX.SomeType, RDF.type, XSDO.ComplexTypeDefinition))
    check(graph)  # must not raise


def test_check_raises_on_assertion():
    graph = Graph()
    graph.add((EX.SomeAssertion, RDF.type, XSDO.Assertion))
    with pytest.raises(UnsupportedConstructError):
        check(graph)


def test_check_raises_on_wildcard():
    graph = Graph()
    graph.add((EX.SomeWildcard, RDF.type, XSDO.Wildcard))
    with pytest.raises(UnsupportedConstructError):
        check(graph)
