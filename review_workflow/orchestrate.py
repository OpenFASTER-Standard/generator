"""Orchestrates the review pipeline against the real catalog: load
current citations, sweep them for drift, filter out what's already been
reviewed, and record new review decisions back onto the catalog. See
docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reference_model.deserialize import ReferenceDeserializationError, from_json_dict
from references_catalog.catalog import Revision, RevisionKind, add_revision, list_pages
from review_consultation.consult import apply_reviews, load_reviews
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import FlaggedLeaf, ReviewSummary, summarize_for_review
from staleness_sweep.sweep import sweep


@dataclass(frozen=True)
class WebReviewSummary:
    summary: ReviewSummary
    deserialization_failures: tuple[str, ...]  # fact_keys whose current revision isn't a valid Reference


def get_review_summary(catalog_path: str | Path, module_root: str, reviews_dir: str) -> WebReviewSummary:
    pages = list_pages(catalog_path)

    references = {}
    deserialization_failures = []
    for fact_key, page_summary in pages.items():
        try:
            references[fact_key] = from_json_dict(page_summary.current.reference)
        except ReferenceDeserializationError:
            deserialization_failures.append(fact_key)

    report = sweep(references, module_root)
    summary = summarize_for_review(report)
    reviews = load_reviews(reviews_dir)
    summary = apply_reviews(summary, reviews)

    return WebReviewSummary(
        summary=summary,
        deserialization_failures=tuple(sorted(deserialization_failures)),
    )


def submit_review(
    catalog_path: str | Path,
    reviews_dir: str,
    fact_key: str,
    flagged: FlaggedLeaf,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Revision:
    leaf = record_review(reviews_dir, fact_key, flagged, reviewer, verdict, reasoning)
    return add_revision(
        catalog_path, fact_key, leaf, reviewer,
        f"Review ({verdict.value}): {reasoning}", is_correction=False,
        kind=RevisionKind.REVIEW,
    )
