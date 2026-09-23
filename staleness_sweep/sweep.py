"""Batches reference_model's check_reference() across many References at
once. See docs/specs/2026-09-23-staleness-sweep-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from reference_model.cite import LeafCheckResult, check_reference
from reference_model.model import Leaf, Reference, Status
from staleness_sweep.resolve import resolve_current_location


@dataclass(frozen=True)
class FamilyResolutionFailure:
    family: str
    status: Status  # always NOT_FOUND -- see resolve_current_location


@dataclass(frozen=True)
class SweepReport:
    results_by_key: dict[str, list[LeafCheckResult]]
    family_resolution_failures: tuple[FamilyResolutionFailure, ...]
    excluded_keys: tuple[str, ...]  # caller keys omitted from results_by_key, and why


def _collect_families(reference: Reference) -> set[str]:
    if isinstance(reference, Leaf):
        return {reference.subject_document.family}
    families: set[str] = set()
    for part in reference.parts:
        families |= _collect_families(part)
    return families


def sweep(references: dict[str, Reference], module_root: str) -> SweepReport:
    all_families: set[str] = set()
    for reference in references.values():
        all_families |= _collect_families(reference)

    overrides: dict[str, str] = {}
    failures: list[FamilyResolutionFailure] = []
    for family in sorted(all_families):
        # Sorted, not raw set iteration order -- a report meant to be
        # diffed/snapshot-compared by a later sub-project can't have an
        # order that reshuffles run to run under hash randomization.
        outcome = resolve_current_location(module_root, family)
        if outcome.status == Status.RESOLVED:
            overrides[family] = outcome.raw_content
        else:
            failures.append(FamilyResolutionFailure(family=family, status=outcome.status))

    failed_families = {failure.family for failure in failures}
    results_by_key: dict[str, list[LeafCheckResult]] = {}
    excluded_keys: list[str] = []
    for key, reference in references.items():
        if _collect_families(reference) & failed_families:
            excluded_keys.append(key)
        else:
            results_by_key[key] = check_reference(reference, retrieval_overrides=overrides)

    return SweepReport(
        results_by_key=results_by_key,
        family_resolution_failures=tuple(failures),
        excluded_keys=tuple(excluded_keys),
    )
