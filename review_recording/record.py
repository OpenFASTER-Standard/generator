"""Turns a reviewer's decision into a plain, real JSON document, cited
through the same Reference/cite() machinery already built for XSDs and
PDFs. See docs/specs/2026-09-23-review-recording-design.md.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from reference_model.cite import cite
from reference_model.model import Leaf, SubjectDocument
from reference_model.selectors.json_selector import JsonSelector
from review_surfacing.summarize import DriftKind


class Verdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


def record_review(
    reviews_dir: str,
    fact_key: str,
    family: str,
    drift_kind: DriftKind,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Leaf:
    Path(reviews_dir).mkdir(parents=True, exist_ok=True)
    review_id = str(uuid.uuid4())
    document = {
        "fact_key": fact_key,
        "family": family,
        "drift_kind": drift_kind.value,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict.value,
        "reasoning": reasoning,
    }
    file_path = Path(reviews_dir) / f"{review_id}.json"
    file_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    subject_document = SubjectDocument(
        family=f"review-{review_id}", version="1", retrieval_uri=str(file_path)
    )
    return cite(subject_document, JsonSelector.create(""))
