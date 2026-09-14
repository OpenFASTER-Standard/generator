"""Tests for leaf boundary-value generation, one test per facet kind."""
import re

from rdflib import Graph, Literal, Namespace, XSD

from equivalence.leaf_values import XSDO, generate

EX = Namespace("https://example.org/test/")


def _valid_values(cases):
    return {c.value for c in cases if c.should_be_valid}


def _invalid_values(cases):
    return {c.value for c in cases if not c.should_be_valid}


def test_enumeration_facet_returns_every_value_plus_one_rejection():
    graph = Graph()
    graph.add((EX.AnredeEnum, XSDO.hasEnumerationValue, EX.Frau))
    graph.add((EX.Frau, XSDO.literalValue, Literal("FRAU")))
    graph.add((EX.AnredeEnum, XSDO.hasEnumerationValue, EX.Herr))
    graph.add((EX.Herr, XSDO.literalValue, Literal("HERR")))

    cases = generate(graph, EX.AnredeEnum)

    assert _valid_values(cases) == {"FRAU", "HERR"}
    assert len(_invalid_values(cases)) == 1


def test_exact_length_facet_returns_boundary_and_off_by_one_cases():
    graph = Graph()
    graph.add((EX.FixedLen, XSDO.length, Literal(3)))

    cases = generate(graph, EX.FixedLen)

    assert "xxx" in _valid_values(cases)
    assert "xxxx" in _invalid_values(cases)
    assert "xx" in _invalid_values(cases)


def test_min_max_length_facets_return_both_boundaries_and_rejections():
    graph = Graph()
    graph.add((EX.Vorname, XSDO.minLength, Literal(1)))
    graph.add((EX.Vorname, XSDO.maxLength, Literal(80)))

    cases = generate(graph, EX.Vorname)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert "x" in valid  # at minLength
    assert "x" * 80 in valid  # at maxLength
    assert "" in invalid  # below minLength
    assert "x" * 81 in invalid  # above maxLength


def test_pattern_facet_returns_a_matching_and_a_non_matching_value():
    graph = Graph()
    pattern = r"[A-Z]{2}[0-9]{4}"
    graph.add((EX.CodeType, XSDO.pattern, Literal(pattern)))

    cases = generate(graph, EX.CodeType)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert len(valid) == 1
    assert re.fullmatch(pattern, next(iter(valid)))
    assert len(invalid) == 1
    assert not re.fullmatch(pattern, next(iter(invalid)))


def test_numeric_range_facets_return_boundaries_and_out_of_range_values():
    graph = Graph()
    graph.add((EX.SmallInt, XSDO.minInclusive, Literal(0)))
    graph.add((EX.SmallInt, XSDO.maxInclusive, Literal(100)))

    cases = generate(graph, EX.SmallInt)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert "0" in valid
    assert "100" in valid
    assert "-1" in invalid
    assert "101" in invalid


def test_digit_facets_return_a_boundary_and_an_over_precision_value():
    graph = Graph()
    graph.add((EX.Amount, XSDO.totalDigits, Literal(5)))
    graph.add((EX.Amount, XSDO.fractionDigits, Literal(2)))

    cases = generate(graph, EX.Amount)

    valid = _valid_values(cases)
    invalid = _invalid_values(cases)
    assert any(v.replace(".", "").replace("-", "") for v in valid)
    assert len(invalid) >= 1


def test_unconstrained_type_returns_one_representative_value():
    graph = Graph()
    graph.add((EX.PlainString, XSDO.baseTypeDefinition, XSD.string))

    cases = generate(graph, EX.PlainString)

    assert len(cases) == 1
    assert cases[0].should_be_valid
