"""Loads previously-recorded review decisions and filters a ReviewSummary
against them, scoped to the exact fingerprint each review was recorded
against. See docs/specs/2026-09-24-review-consultation-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from review_recording.record import Verdict
from review_surfacing.summarize import DriftKind, FlaggedLeaf, ReviewSummary


@dataclass(frozen=True)
class ReviewRecord:
    fact_key: str
    family: str
    drift_kind: DriftKind
    reviewed_fingerprint: str
    reviewer: str
    reviewed_at: str
    verdict: Verdict
    reasoning: str


class ReviewLoadError(Exception):
    pass


_REQUIRED_FIELDS = (
    "fact_key", "family", "drift_kind", "reviewed_fingerprint",
    "reviewer", "reviewed_at", "verdict", "reasoning",
)


def load_reviews(reviews_dir: str) -> list[ReviewRecord]:
    records = []
    for path in sorted(Path(reviews_dir).glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ReviewLoadError(f"{path}: not valid JSON") from e
        if not isinstance(raw, dict):
            raise ReviewLoadError(f"{path}: expected a JSON object")
        missing = [f for f in _REQUIRED_FIELDS if f not in raw]
        if missing:
            raise ReviewLoadError(f"{path}: missing field(s) {missing}")
        try:
            drift_kind = DriftKind(raw["drift_kind"])
            verdict = Verdict(raw["verdict"])
        except ValueError as e:
            raise ReviewLoadError(f"{path}: invalid drift_kind/verdict value") from e
        records.append(ReviewRecord(
            fact_key=raw["fact_key"],
            family=raw["family"],
            drift_kind=drift_kind,
            reviewed_fingerprint=raw["reviewed_fingerprint"],
            reviewer=raw["reviewer"],
            reviewed_at=raw["reviewed_at"],
            verdict=verdict,
            reasoning=raw["reasoning"],
        ))
    return records


def apply_reviews(summary: ReviewSummary, reviews: list[ReviewRecord]) -> ReviewSummary:
    approved = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.APPROVED
    }
    rejected = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.REJECTED
    }

    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for fact_key, entries in summary.flagged.items():
        kept = tuple(
            fl for fl in entries
            if (fact_key, fl.drift_kind, fl.fingerprint) not in approved
            or (fact_key, fl.drift_kind, fl.fingerprint) in rejected
        )
        if kept:
            flagged[fact_key] = kept

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=summary.unresolved_families,
        excluded_keys=summary.excluded_keys,
    )
