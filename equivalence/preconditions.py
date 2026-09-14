"""Guardrail: refuses to proceed if a graph contains a construct outside
the decidable fragment this checker's bounded-exhaustive method covers.

xs:assert (arbitrary XPath 2.0 boolean predicates) and xs:any/
xs:anyAttribute (open-content wildcards) are the two XSD constructs that
put correctness checking out of reach here -- neither can be meaningfully
covered by enumerating structural cases and boundary leaf values. This
module is the loud, explicit failure that fires if either ever appears,
rather than silently producing a weaker guarantee.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")


class UnsupportedConstructError(Exception):
    """Raised when a graph contains xsdo:Assertion or xsdo:Wildcard."""


def check(graph: Graph) -> None:
    for unsupported_class in (XSDO.Assertion, XSDO.Wildcard):
        if (None, RDF.type, unsupported_class) in graph:
            raise UnsupportedConstructError(
                f"graph contains a {unsupported_class} node -- equivalence "
                "cannot be checked by this method while it's present"
            )
