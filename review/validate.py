"""SHACL validation for review-workflow writes -- gives the integrity
guarantees a SQL schema's CHECK constraints/foreign keys would otherwise
give for free (valid status/outcome values, no self-approval), as an
explicit step rather than built into the storage engine. Verified live
during design: pyshacl correctly rejects a self-approval attempt via a
SPARQL-based SHACL constraint, and accepts a decision by a different
reviewer.
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
