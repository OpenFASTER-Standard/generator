"""Orchestrates the review pipeline against the real catalog: load
current citations, sweep them for drift, filter out what's already been
reviewed, and record new review decisions back onto the catalog. See
docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from review_workflow.orchestrate import (
    WebReviewSummary,
    get_review_summary,
    submit_review,
)

__all__ = ["WebReviewSummary", "get_review_summary", "submit_review"]
