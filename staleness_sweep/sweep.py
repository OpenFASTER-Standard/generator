"""Batches reference_model's check_reference() across many References at
once. See docs/specs/2026-09-23-staleness-sweep-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from reference_model.cite import LeafCheckResult, check_reference
from reference_model.model import Leaf, Reference, Status
from staleness_sweep.resolve import resolve_family_location


@dataclass(frozen=True)
class FamilyResolutionFailure:
    family: str
    status: Status  # always NOT_FOUND -- resolve_family_location() distinguishes only found/not-found


@dataclass(frozen=True)
class ReferenceCheckFailure:
    # An unexpected exception from a selector's own resolve()/
    # canonicalize_and_hash() (a selector-implementation bug, not a
    # resolution outcome like NOT_FOUND/UNCITABLE, which check_reference()
    # already reports as data via LeafCheckResult.outcome, never raises
    # for) -- isolated to this one key, same principle as
    # family_resolution_failures/excluded_keys below.
    key: str
    error: str


@dataclass(frozen=True)
class SweepReport:
    results_by_key: dict[str, list[LeafCheckResult]]
    family_resolution_failures: tuple[FamilyResolutionFailure, ...]
    excluded_keys: tuple[str, ...]  # caller keys omitted from results_by_key, and why
    check_failures: tuple[ReferenceCheckFailure, ...] = ()


def _collect_families(reference: Reference) -> set[str]:
    if isinstance(reference, Leaf):
        return {reference.subject_document.family}
    families: set[str] = set()
    for part in reference.parts:
        families |= _collect_families(part)
    return families


def sweep(references: dict[str, Reference], corpus_root: str) -> SweepReport:
    all_families: set[str] = set()
    for reference in references.values():
        all_families |= _collect_families(reference)

    overrides: dict[str, str] = {}
    failures: list[FamilyResolutionFailure] = []
    for family in sorted(all_families):
        # Sorted, not raw set iteration order -- a report meant to be
        # diffed/snapshot-compared by a later sub-project can't have an
        # order that reshuffles run to run under hash randomization.
        location = resolve_family_location(corpus_root, family)
        if location is not None:
            overrides[family] = location.retrieval_uri
        else:
            failures.append(FamilyResolutionFailure(family=family, status=Status.NOT_FOUND))

    failed_families = {failure.family for failure in failures}
    results_by_key: dict[str, list[LeafCheckResult]] = {}
    excluded_keys: list[str] = []
    check_failures: list[ReferenceCheckFailure] = []
    for key, reference in references.items():
        if _collect_families(reference) & failed_families:
            excluded_keys.append(key)
            continue
        try:
            results_by_key[key] = check_reference(reference, retrieval_overrides=overrides)
        except Exception as exc:
            # A selector's resolve()/canonicalize_and_hash() raising is an
            # implementation bug in that selector, not a normal resolution
            # outcome -- but one broken/unusual reference must never take
            # down the whole sweep for every OTHER, healthy key.
            check_failures.append(ReferenceCheckFailure(key=key, error=str(exc)))

    return SweepReport(
        results_by_key=results_by_key,
        family_resolution_failures=tuple(failures),
        excluded_keys=tuple(excluded_keys),
        check_failures=tuple(check_failures),
    )
