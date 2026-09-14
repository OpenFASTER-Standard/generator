"""Boundary-value generation for xsdo:SimpleTypeDefinition facets, per
standard boundary-value analysis (Kaner/Myers-style equivalence-class
partitioning) -- not exhaustive enumeration of the underlying domain.
Enumerating "all possible strings" is both intractable and not what
boundary-value analysis calls for; the boundary points are where real
schema-divergence bugs actually live.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

import exrex
from rdflib import Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


@dataclass(frozen=True)
class LeafValueCase:
    value: str
    should_be_valid: bool


def generate(graph: Graph, simple_type: URIRef) -> list[LeafValueCase]:
    enumeration_cases = _enumeration_cases(graph, simple_type)
    if enumeration_cases is not None:
        return enumeration_cases

    length_cases = _length_cases(graph, simple_type)
    if length_cases is not None:
        return length_cases

    pattern_cases = _pattern_cases(graph, simple_type)
    if pattern_cases is not None:
        return pattern_cases

    numeric_cases = _numeric_range_cases(graph, simple_type)
    if numeric_cases is not None:
        return numeric_cases

    digit_cases = _digit_precision_cases(graph, simple_type)
    if digit_cases is not None:
        return digit_cases

    return [LeafValueCase("sample", should_be_valid=True)]


def _enumeration_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    enum_values = list(graph.objects(simple_type, XSDO.hasEnumerationValue))
    if not enum_values:
        return None
    cases = [
        LeafValueCase(str(graph.value(v, XSDO.literalValue)), should_be_valid=True)
        for v in enum_values
    ]
    cases.append(LeafValueCase("__NOT_IN_ENUMERATION__", should_be_valid=False))
    return cases


def _length_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    exact = graph.value(simple_type, XSDO.length)
    min_len = graph.value(simple_type, XSDO.minLength)
    max_len = graph.value(simple_type, XSDO.maxLength)
    if exact is None and min_len is None and max_len is None:
        return None

    cases: list[LeafValueCase] = []
    if exact is not None:
        n = int(exact)
        cases.append(LeafValueCase("x" * n, should_be_valid=True))
        cases.append(LeafValueCase("x" * (n + 1), should_be_valid=False))
        if n > 0:
            cases.append(LeafValueCase("x" * (n - 1), should_be_valid=False))
        return cases

    lo = int(min_len) if min_len is not None else 0
    hi = int(max_len) if max_len is not None else None
    cases.append(LeafValueCase("x" * lo, should_be_valid=True))
    if lo > 0:
        cases.append(LeafValueCase("x" * (lo - 1), should_be_valid=False))
    if hi is not None:
        cases.append(LeafValueCase("x" * hi, should_be_valid=True))
        cases.append(LeafValueCase("x" * (hi + 1), should_be_valid=False))
    return cases


def _pattern_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    pattern = graph.value(simple_type, XSDO.pattern)
    if pattern is None:
        return None
    pattern_str = str(pattern)
    matching = exrex.getone(pattern_str)
    cases = [LeafValueCase(matching, should_be_valid=True)]
    non_matching = matching + "\x00"
    if re.fullmatch(pattern_str, non_matching) is None:
        cases.append(LeafValueCase(non_matching, should_be_valid=False))
    return cases


def _numeric_range_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    min_inclusive = graph.value(simple_type, XSDO.minInclusive)
    max_inclusive = graph.value(simple_type, XSDO.maxInclusive)
    if min_inclusive is None and max_inclusive is None:
        return None

    cases: list[LeafValueCase] = []
    if min_inclusive is not None:
        lo = Decimal(str(min_inclusive))
        cases.append(LeafValueCase(str(lo), should_be_valid=True))
        cases.append(LeafValueCase(str(lo - 1), should_be_valid=False))
    if max_inclusive is not None:
        hi = Decimal(str(max_inclusive))
        cases.append(LeafValueCase(str(hi), should_be_valid=True))
        cases.append(LeafValueCase(str(hi + 1), should_be_valid=False))
    return cases


def _digit_precision_cases(graph: Graph, simple_type: URIRef) -> list[LeafValueCase] | None:
    total_digits = graph.value(simple_type, XSDO.totalDigits)
    fraction_digits = graph.value(simple_type, XSDO.fractionDigits)
    if total_digits is None and fraction_digits is None:
        return None

    total = int(total_digits) if total_digits is not None else 18
    fraction = int(fraction_digits) if fraction_digits is not None else 0
    integer_digits = max(total - fraction, 1)

    valid = "1" * integer_digits + ("." + "1" * fraction if fraction else "")
    too_much_fraction = "1" * integer_digits + "." + "1" * (fraction + 1)
    return [
        LeafValueCase(valid, should_be_valid=True),
        LeafValueCase(too_much_fraction, should_be_valid=False),
    ]
