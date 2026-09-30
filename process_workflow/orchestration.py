"""Composes engine + store into the two operations a caller actually
needs: start a pending correction (persisting only if it doesn't
complete immediately) and complete one (only if a matching pending
instance genuinely exists).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from process_workflow.engine import NoReadyCorrectionTaskError, complete_correction, start_citation_correction
from process_workflow.store import CorrectionIdentity, delete_instance, load_instance, save_instance


def start_pending_correction(
    identity: CorrectionIdentity, *, verdict: Literal["approved", "rejected"], instances_dir: Path | None = None
) -> None:
    workflow = start_citation_correction(verdict=verdict)
    if not workflow.is_completed():
        save_instance(identity, workflow, instances_dir=instances_dir)


def complete_pending_correction(
    identity: CorrectionIdentity, *, corrected_fact_key: str, instances_dir: Path | None = None
) -> bool:
    workflow = load_instance(identity, instances_dir=instances_dir)
    if workflow is None:
        return False
    try:
        complete_correction(workflow, corrected_fact_key=corrected_fact_key)
    except NoReadyCorrectionTaskError as exc:
        # Re-raised with the identity attached (M5) -- the bare "found 0"
        # message from engine.py has no way to know which pending
        # correction it came from; this is the one layer that does.
        raise NoReadyCorrectionTaskError(f"{identity!r}: {exc}") from exc
    delete_instance(identity, instances_dir=instances_dir)
    return True
