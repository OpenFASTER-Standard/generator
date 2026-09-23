"""cite() builds a new, verified Reference at citation time -- it raises
unless the selector resolves cleanly. check_leaf()/check_reference()
re-check an existing Reference later, returning outcomes as data without
raising: "this doesn't resolve anymore" is an expected, meaningful result
at check time, not a bug. See the "Resolution & Error Semantics" section of
docs/specs/2026-09-23-source-reference-model-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reference_model.model import (
    ContentHash,
    Leaf,
    Reference,
    ResolutionOutcome,
    Status,
    SubjectDocument,
    Union,
    compute_leaf_reference_id,
    now_iso,
)
from reference_model.registry import get_resolver


class CitationError(Exception):
    pass


def cite(subject_document: SubjectDocument, selector: Any) -> Leaf:
    resolver = get_resolver(selector.type)
    outcome = resolver.resolve(selector, subject_document.retrieval_uri)
    if outcome.status != Status.RESOLVED:
        raise CitationError(
            f"cannot cite {selector!r} against {subject_document.retrieval_uri!r}: "
            f"resolved to {outcome.status.value}, not RESOLVED"
        )
    digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return Leaf(
        reference_id=compute_leaf_reference_id(subject_document.family, selector),
        subject_document=subject_document,
        selector=selector,
        content_hash=ContentHash(algorithm="sha256", digest=digest),
        captured_at=now_iso(),
    )


def cite_union(parts: list[Reference]) -> Union:
    # No further resolution check is needed for non-empty parts: every
    # element is already either a Leaf built by a successful cite() call,
    # or a Union built the same recursive way -- there is no way to
    # construct an unresolved Reference to put in this list. An *empty*
    # list is the one gap that guarantee doesn't close: it would produce a
    # well-formed, permanently-"healthy" Reference backed by nothing, which
    # a staleness sweep could never flag -- reject it explicitly instead.
    if not parts:
        raise CitationError("cite_union() requires at least one part; an empty Union can never be flagged as stale")
    return Union(parts=tuple(parts))


@dataclass(frozen=True)
class LeafCheckResult:
    leaf: Leaf
    outcome: ResolutionOutcome
    hash_changed: bool | None  # None unless outcome.status is RESOLVED


def check_leaf(leaf: Leaf, retrieval_uri: str | None = None) -> LeafCheckResult:
    resolver = get_resolver(leaf.selector.type)
    uri = retrieval_uri if retrieval_uri is not None else leaf.subject_document.retrieval_uri
    outcome = resolver.resolve(leaf.selector, uri)
    if outcome.status != Status.RESOLVED:
        return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=None)
    new_digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=new_digest != leaf.content_hash.digest)


def check_reference(
    reference: Reference, retrieval_overrides: dict[str, str] | None = None
) -> list[LeafCheckResult]:
    if isinstance(reference, Leaf):
        override = None
        if retrieval_overrides is not None:
            override = retrieval_overrides.get(reference.subject_document.family)
        return [check_leaf(reference, retrieval_uri=override)]

    results: list[LeafCheckResult] = []
    for part in reference.parts:
        results.extend(check_reference(part, retrieval_overrides))
    return results
