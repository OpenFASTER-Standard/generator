"""Format-agnostic Reference/Selector data model. Nothing in this module
knows about XSDs, PDFs, or any specific selector type -- see
reference_model/selectors/ for those. See
docs/specs/2026-09-23-source-reference-model-design.md.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union as TypingUnion


class Status(Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    UNCITABLE = "UNCITABLE"


@dataclass(frozen=True)
class ResolutionOutcome:
    status: Status
    raw_content: Any = None  # only meaningful when status is RESOLVED


@dataclass(frozen=True)
class SubjectDocument:
    family: str
    version: str
    retrieval_uri: str


@dataclass(frozen=True)
class ContentHash:
    algorithm: str
    digest: str


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def selector_canonical_form(selector: Any) -> str:
    """Any dataclass-based Selector gets a stable canonical form for free --
    a new selector type needs no custom method for this to work, which is
    part of what makes adding a new source format trivial."""
    if not is_dataclass(selector):
        raise TypeError(f"selector {selector!r} must be a dataclass")
    return _canonical_json(asdict(selector))


def compute_leaf_reference_id(family: str, selector: Any) -> str:
    # Deliberately excludes subject_document.version -- see Global
    # Constraints in the implementation plan.
    key = f"{family}|{selector_canonical_form(selector)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compute_union_reference_id(part_ids: list[str]) -> str:
    key = "|".join(part_ids)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compute_union_content_hash(part_digests: list[str]) -> ContentHash:
    key = "|".join(part_digests)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return ContentHash(algorithm="sha256", digest=digest)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Leaf:
    reference_id: str
    subject_document: SubjectDocument
    selector: Any
    content_hash: ContentHash
    captured_at: str


@dataclass(frozen=True)
class Union:
    parts: tuple["Reference", ...]

    @property
    def reference_id(self) -> str:
        return compute_union_reference_id([p.reference_id for p in self.parts])

    @property
    def content_hash(self) -> ContentHash:
        return compute_union_content_hash([p.content_hash.digest for p in self.parts])


Reference = TypingUnion[Leaf, Union]
