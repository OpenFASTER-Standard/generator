"""Connects candidate discovery to the catalog: given a family + xpath a
human picked from list_corpus_candidates(), re-resolves the family's real
current location server-side, builds and verifies a fresh citation, and
records it as a new revision. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from pathlib import Path

from generator_errors import GeneratorError
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import Revision, add_revision
from staleness_sweep.resolve import resolve_family_location


class FamilyNotFoundError(GeneratorError):
    # The caller named a family that doesn't exist -- a bad request.
    http_status = 400


class FamilyNotCitableError(GeneratorError):
    # The caller named a real family, but not one this citation flow
    # supports (e.g. a PDF family) -- also a bad request.
    http_status = 400


def add_citation(
    corpus_root: str,
    catalog_path: str | Path,
    family: str,
    xpath: str,
    fact_key: str,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    # Resolves only the one family requested -- an unrelated broken
    # manifest entry for some OTHER family must never prevent citing this
    # one. See resolve_family_location()'s own docstring.
    location = resolve_family_location(corpus_root, family)
    if location is None:
        raise FamilyNotFoundError(f"no such family in the current corpus snapshot: {family!r}")
    if not location.retrieval_uri.endswith(".xsd"):
        raise FamilyNotCitableError(
            f"family {family!r} has no XSD in the current corpus snapshot and cannot be cited"
        )
    subject_document = SubjectDocument(
        family=location.family,
        version=location.version,
        retrieval_uri=location.retrieval_uri,
    )
    leaf = cite(subject_document, XPathSelector.create(xpath))
    return add_revision(catalog_path, fact_key, leaf, author, comment, is_correction)
