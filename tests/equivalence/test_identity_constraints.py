"""Tests for direct xs:key/xs:unique/xs:keyref comparison."""
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.identity_constraints import XSDO, compare

EX = Namespace("https://example.org/test/")


def _key(graph, type_uri, constraint_uri, kind, selector, field):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, kind))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    graph.add((constraint_uri, XSDO.field, Literal(field)))


def test_identical_key_constraints_produce_no_mismatches():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []


def test_differing_selector_is_reported_as_a_mismatch():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Item", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].official_selector == "./Row"
    assert mismatches[0].generated_selector == "./Item"


def test_constraint_present_only_on_official_side_is_a_mismatch():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", "@id")
    generated = Graph()

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].generated_selector is None


def test_multiple_constraints_of_same_kind_are_all_compared():
    official = Graph()
    _key(official, EX.OffType, EX.OffKey1, XSDO.Key, "./Row", "@id")
    _key(official, EX.OffType, EX.OffKey2, XSDO.Key, "./Item", "business_key")
    generated = Graph()
    _key(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", "@id")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].constraint_kind == str(XSDO.Key)
    assert "./Row" in mismatches[0].official_selector
    assert "./Item" in mismatches[0].official_selector
    assert mismatches[0].generated_selector == "./Row"
