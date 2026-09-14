"""OpenFASTER generator: equivalence package.

Proves a graph-generated XSD is behaviorally equivalent to an official
one, via bounded-exhaustive/pairwise structural testing and exact
leaf-facet checking. See docs/specs/2026-09-14-equivalence-checker-design.md
for the full design and its confidence characterization.
"""
from equivalence.checker import Divergence, Report, check_equivalence
from equivalence.preconditions import UnsupportedConstructError

__all__ = [
    "Divergence",
    "Report",
    "UnsupportedConstructError",
    "check_equivalence",
]
