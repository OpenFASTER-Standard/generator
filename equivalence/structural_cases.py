"""Bounded-exhaustive / pairwise enumeration of a xsdo:Sequence content
model's structural variations: which optional particles are present, at
which occurrence-count boundary. xsdo:Choice/xsdo:All are an explicit,
flagged fast-follow (see this plan's Global Constraints), not handled
here -- the real schemas are overwhelmingly sequence-based.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from allpairspy import AllPairs
from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

UNBOUNDED_CEILING = 5
FULL_ENUMERATION_CEILING = 1024


@dataclass(frozen=True)
class ParticleOccurrence:
    term: URIRef
    count: int


@dataclass(frozen=True)
class StructuralCase:
    occurrences: tuple[ParticleOccurrence, ...]
    should_be_valid: bool


def _occurrence_options(graph: Graph, particle: URIRef) -> list[tuple[int, bool]]:
    min_occurs_literal = graph.value(particle, XSDO.minOccurs)
    min_occurs = int(min_occurs_literal) if min_occurs_literal is not None else 1

    unbounded_literal = graph.value(particle, XSDO.maxOccursUnbounded)
    is_unbounded = unbounded_literal is not None and str(unbounded_literal).lower() == "true"
    if is_unbounded:
        max_occurs = UNBOUNDED_CEILING
    else:
        max_occurs_literal = graph.value(particle, XSDO.maxOccurs)
        max_occurs = int(max_occurs_literal) if max_occurs_literal is not None else 1

    options: dict[int, bool] = {min_occurs: True}
    if max_occurs > min_occurs:
        options[min_occurs + 1] = True
    options[max_occurs] = True
    # Over-max is only a meaningful *invalid* boundary when max_occurs is a
    # real, finite repeat limit (>1): a plain 0-or-1 particle (max_occurs<=1)
    # has no "too many" case worth probing, and the unbounded ceiling is an
    # enumeration cutoff, not a genuine schema limit -- N+1 there is not
    # actually invalid against the real (unbounded) schema.
    if not is_unbounded and max_occurs > 1:
        options[max_occurs + 1] = False
    return sorted(options.items())


def enumerate_cases(graph: Graph, content_model: URIRef) -> list[StructuralCase]:
    if (content_model, RDF.type, XSDO.Sequence) not in graph:
        actual_type = graph.value(content_model, RDF.type)
        raise NotImplementedError(
            f"structural_cases only handles xsdo:Sequence content models, "
            f"got {actual_type}"
        )

    particles = sorted(
        graph.objects(content_model, XSDO.hasParticle),
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )
    terms = [graph.value(p, XSDO["term"]) for p in particles]
    per_particle_options = [_occurrence_options(graph, p) for p in particles]

    total_combinations = 1
    for options in per_particle_options:
        total_combinations *= len(options)

    if total_combinations <= FULL_ENUMERATION_CEILING:
        combos = list(product(*per_particle_options))
    else:
        combos = list(AllPairs(per_particle_options))

    cases = []
    for combo in combos:
        occurrences = tuple(
            ParticleOccurrence(term=term, count=count)
            for term, (count, _valid) in zip(terms, combo)
        )
        should_be_valid = all(valid for _count, valid in combo)
        cases.append(StructuralCase(occurrences=occurrences, should_be_valid=should_be_valid))
    return cases
