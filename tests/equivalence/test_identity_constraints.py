"""Tests for direct xs:key/xs:unique/xs:keyref comparison."""
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.identity_constraints import XSDO, compare

EX = Namespace("https://example.org/test/")


def _key(graph, type_uri, constraint_uri, kind, selector, field):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, kind))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    graph.add((constraint_uri, XSDO.field, Literal(field)))


def _key_multi_field(graph, type_uri, constraint_uri, kind, selector, fields):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, kind))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    for field in fields:
        graph.add((constraint_uri, XSDO.field, Literal(field)))


def _keyref(graph, type_uri, constraint_uri, selector, fields, refer):
    graph.add((type_uri, XSDO.hasIdentityConstraint, constraint_uri))
    graph.add((constraint_uri, RDF.type, XSDO.KeyRef))
    graph.add((constraint_uri, XSDO.selector, Literal(selector)))
    for field in fields:
        graph.add((constraint_uri, XSDO.field, Literal(field)))
    graph.add((constraint_uri, XSDO.refer, Literal(refer)))


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


def test_composite_key_missing_a_field_is_caught_as_a_mismatch():
    """A real xs:key/xs:unique can have more than one xs:field child
    (a composite key) -- collecting only the first field (the bug this
    guards against) would make a mismatch in the second-or-later field
    invisible."""
    official = Graph()
    _key_multi_field(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", ["@id", "@type"])
    generated = Graph()
    _key_multi_field(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", ["@id"])

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].official_selector == "./Row"
    assert mismatches[0].generated_selector == "./Row"
    assert "@type" in mismatches[0].official_detail
    assert "@type" not in (mismatches[0].generated_detail or "")


def test_composite_key_with_identical_fields_in_different_order_matches():
    official = Graph()
    _key_multi_field(official, EX.OffType, EX.OffKey, XSDO.Key, "./Row", ["@type", "@id"])
    generated = Graph()
    _key_multi_field(generated, EX.GenType, EX.GenKey, XSDO.Key, "./Row", ["@id", "@type"])

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []


def test_keyref_with_differing_refer_is_caught_as_a_mismatch():
    """Two xs:keyrefs with the same selector/field but a different
    `refer` target reference different keys and are not equivalent --
    `refer` must actually be compared, not silently dropped."""
    official = Graph()
    _keyref(official, EX.OffType, EX.OffKeyRef, "./Row", ["@id"], "OffKey")
    generated = Graph()
    _keyref(generated, EX.GenType, EX.GenKeyRef, "./Row", ["@id"], "GenKey")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert len(mismatches) == 1
    assert mismatches[0].constraint_kind == str(XSDO.KeyRef)
    assert "OffKey" in mismatches[0].official_detail
    assert "GenKey" in mismatches[0].generated_detail


def test_keyref_with_identical_refer_matches():
    official = Graph()
    _keyref(official, EX.OffType, EX.OffKeyRef, "./Row", ["@id"], "SharedKey")
    generated = Graph()
    _keyref(generated, EX.GenType, EX.GenKeyRef, "./Row", ["@id"], "SharedKey")

    mismatches = compare(official, generated, EX.OffType, EX.GenType)

    assert mismatches == []
