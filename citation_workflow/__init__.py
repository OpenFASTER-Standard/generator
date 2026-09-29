"""Connects candidate discovery to the catalog: turns a human-picked
(family, xpath) pair into a fresh, verified citation recorded as a new
catalog revision. See docs/specs/2026-09-25-citation-workflow-design.md.
"""
from citation_workflow.add_citation import (
    FamilyNotCitableError,
    FamilyNotFoundError,
    add_citation,
)

__all__ = ["add_citation", "FamilyNotFoundError", "FamilyNotCitableError"]
