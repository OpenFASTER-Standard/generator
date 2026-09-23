"""Format-agnostic Reference/Selector data model. Nothing in this module
knows about XSDs, PDFs, or any specific selector type -- see
reference_model/selectors/ for those. See
docs/specs/2026-09-23-source-reference-model-design.md.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
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
    # Deliberately excludes subject_document.version (see the design
    # spec's "Core concept: Reference" section) -- citing the same logical
    # span across a version bump keeps the same reference_id even though
    # content_hash may differ. Consequence for any future consumer: two
    # Leafs with the same reference_id are NOT guaranteed to have the same
    # content_hash, so reference_id alone is never a safe key for anything
    # that cares about a specific cited value (e.g. a future storage/
    # persistence layer) -- only for "is this citing the same span."
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
    # reference_id/content_hash are derived from `parts`, but stored as
    # real fields (computed once in __post_init__) rather than @property --
    # a @property is invisible to dataclasses.asdict(), which would
    # otherwise silently drop them for any future consumer (e.g. a
    # persistence layer) that serializes via asdict(), the obvious
    # approach. Leaf already stores these as fields; Union now matches.
    parts: tuple["Reference", ...]
    reference_id: str = field(init=False)
    content_hash: ContentHash = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "reference_id", compute_union_reference_id([p.reference_id for p in self.parts])
        )
        object.__setattr__(
            self, "content_hash", compute_union_content_hash([p.content_hash.digest for p in self.parts])
        )


Reference = TypingUnion[Leaf, Union]
