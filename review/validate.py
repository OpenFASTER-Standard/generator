"""SHACL validation for review-workflow writes -- gives the integrity
guarantees a SQL schema's CHECK constraints/foreign keys would otherwise
give for free (valid status/outcome values, no self-approval), as an
explicit step rather than built into the storage engine. Verified live
during design: pyshacl correctly rejects a self-approval attempt via a
SPARQL-based SHACL constraint, and accepts a decision by a different
reviewer.

Scope, stated plainly: validate_graph only checks the SHAPE of the specific
resource(s) in the graph handed to it (the small, single-purpose "check"
graph a caller builds right before writing) -- field presence/cardinality,
allowed values, well-formed datatypes, and (for no-self-approval
specifically) one particular cross-resource relationship expressed as a
SPARQL-based constraint. It does NOT check uniqueness or consistency against
anything already committed in the store. No-self-approval is the one
exception where a genuine store-level relationship (this Decision's decider
vs. its Correction's proposer) is enforced via SHACL, because both ends of
that relationship are present in the same small check graph pyshacl sees.
Every other real store-level invariant in this package is enforced by
ad-hoc Python checks elsewhere instead, because they depend on data outside
any single check graph -- e.g. review.corrections._write_decision's "already
decided" guard (a correction may only ever be decided once) and
review.current_view._find_approved_correction's "most recent approval wins"
resolution (when more than one correction for the same target ends up
independently approved). Don't expect a SHACL conformance result from this
module to mean anything about the rest of the store's state.
"""
from __future__ import annotations

import os

import pyshacl
from rdflib import Graph

_SHAPES_PATH = os.path.join(os.path.dirname(__file__), "shapes.ttl")


def load_shapes() -> Graph:
    return Graph().parse(_SHAPES_PATH, format="turtle")


def validate_graph(data_graph: Graph) -> tuple[bool, str]:
    shapes = load_shapes()
    conforms, _, results_text = pyshacl.validate(data_graph, shacl_graph=shapes)
    return conforms, results_text
