"""Classifies a SweepReport's entries into what a human reviewer needs to
see first. See docs/specs/2026-09-23-review-surfacing-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from reference_model.cite import LeafCheckResult
from reference_model.model import Leaf, ResolutionOutcome, Status
from staleness_sweep.sweep import FamilyResolutionFailure, SweepReport


class DriftKind(Enum):
    CONTENT = "CONTENT"
    STRUCTURAL = "STRUCTURAL"


@dataclass(frozen=True)
class FlaggedLeaf:
    leaf: Leaf
    outcome: ResolutionOutcome
    drift_kind: DriftKind
    fingerprint: str


@dataclass(frozen=True)
class ReviewSummary:
    flagged: dict[str, tuple[FlaggedLeaf, ...]]
    unresolved_families: tuple[FamilyResolutionFailure, ...]
    excluded_keys: tuple[str, ...]


def _classify(result: LeafCheckResult) -> FlaggedLeaf | None:
    if result.outcome.status == Status.RESOLVED:
        if result.hash_changed:
            assert result.new_content_hash is not None, (
                "check_leaf() guarantees new_content_hash is set whenever outcome.status "
                "is RESOLVED -- a LeafCheckResult violating that invariant is malformed"
            )
            return FlaggedLeaf(result.leaf, result.outcome, DriftKind.CONTENT, result.new_content_hash)
        return None
    return FlaggedLeaf(result.leaf, result.outcome, DriftKind.STRUCTURAL, result.outcome.status.name)


def summarize_for_review(report: SweepReport) -> ReviewSummary:
    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for key, results in report.results_by_key.items():
        problematic = [fl for fl in (_classify(result) for result in results) if fl is not None]
        if problematic:
            flagged[key] = tuple(problematic)

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=report.family_resolution_failures,
        excluded_keys=report.excluded_keys,
    )
