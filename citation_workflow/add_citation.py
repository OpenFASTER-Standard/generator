"""Connects candidate discovery to the catalog: given a family + xpath a
human picked from list_corpus_candidates(), re-resolves the family's real
current location server-side, builds and verifies a fresh citation, and
records it as a new revision. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from pathlib import Path

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import Revision, add_revision
from staleness_sweep.resolve import list_current_locations


class FamilyNotFoundError(Exception):
    pass


def add_citation(
    module_root: str,
    catalog_path: str | Path,
    family: str,
    xpath: str,
    fact_key: str,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    locations = {loc.family: loc for loc in list_current_locations(module_root)}
    if family not in locations:
        raise FamilyNotFoundError(f"no such family in the current corpus snapshot: {family!r}")
    location = locations[family]
    subject_document = SubjectDocument(
        family=location.family,
        version=location.version,
        retrieval_uri=location.retrieval_uri,
    )
    leaf = cite(subject_document, XPathSelector.create(xpath))
    return add_revision(catalog_path, fact_key, leaf, author, comment, is_correction)
