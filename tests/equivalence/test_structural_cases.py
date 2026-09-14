"""Tests for bounded-exhaustive/pairwise structural case enumeration."""
import pytest
from rdflib import RDF, Graph, Literal, Namespace

from equivalence.structural_cases import XSDO, enumerate_cases

EX = Namespace("https://example.org/test/")


def _make_particle(graph, particle, term, position, min_occurs, max_occurs, unbounded=False):
    graph.add((particle, XSDO.particlePosition, Literal(position)))
    graph.add((particle, XSDO.minOccurs, Literal(min_occurs)))
    graph.add((particle, XSDO["term"], term))
    if unbounded:
        graph.add((particle, XSDO.maxOccursUnbounded, Literal(True)))
    else:
        graph.add((particle, XSDO.maxOccurs, Literal(max_occurs)))


def test_raises_on_non_sequence_content_model():
    graph = Graph()
    graph.add((EX.SomeChoice, RDF.type, XSDO.Choice))
    with pytest.raises(NotImplementedError):
        enumerate_cases(graph, EX.SomeChoice)


def test_single_required_particle_produces_one_valid_case():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=1)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)

    assert len(cases) == 1
    assert cases[0].should_be_valid
    assert cases[0].occurrences == (
        __import__("equivalence.structural_cases", fromlist=["ParticleOccurrence"]).ParticleOccurrence(
            term=EX.FieldA, count=1
        ),
    )


def test_optional_particle_produces_present_and_absent_cases():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=0, max_occurs=1)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert counts == [0, 1]
    assert all(c.should_be_valid for c in cases)


def test_repeating_particle_produces_min_min_plus_one_max_and_over_max():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=3)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert counts == [1, 2, 3, 4]
    valid_by_count = {c.occurrences[0].count: c.should_be_valid for c in cases}
    assert valid_by_count[1] and valid_by_count[2] and valid_by_count[3]
    assert not valid_by_count[4]


def test_unbounded_particle_uses_the_ceiling_not_literal_infinity():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    _make_particle(graph, EX.P1, EX.FieldA, 1, min_occurs=1, max_occurs=None, unbounded=True)
    graph.add((EX.Content, XSDO.hasParticle, EX.P1))

    cases = enumerate_cases(graph, EX.Content)
    counts = sorted(c.occurrences[0].count for c in cases)

    assert max(counts) == 5  # the fixed ceiling, not a huge or infinite number


def test_many_independent_particles_falls_back_to_pairwise_below_full_count():
    graph = Graph()
    graph.add((EX.Content, RDF.type, XSDO.Sequence))
    for i in range(15):
        particle = EX[f"P{i}"]
        field = EX[f"Field{i}"]
        _make_particle(graph, particle, field, i, min_occurs=0, max_occurs=1)
        graph.add((EX.Content, XSDO.hasParticle, particle))

    cases = enumerate_cases(graph, EX.Content)

    # 15 independent optional particles = 2**15 = 32768 combinations if
    # fully enumerated -- must be far fewer via pairwise fallback.
    assert len(cases) < 100
