"""Composes engine + store into the two operations a caller actually
needs: start a pending correction (persisting only if it doesn't
complete immediately) and complete one (only if a matching pending
instance genuinely exists).
"""
from __future__ import annotations

from process_workflow.engine import complete_correction, start_citation_correction
from process_workflow.store import CorrectionIdentity, delete_instance, load_instance, save_instance


def start_pending_correction(identity: CorrectionIdentity, *, verdict: str) -> None:
    workflow = start_citation_correction(verdict=verdict)
    if not workflow.is_completed():
        save_instance(identity, workflow)


def complete_pending_correction(identity: CorrectionIdentity, *, corrected_fact_key: str) -> bool:
    workflow = load_instance(identity)
    if workflow is None:
        return False
    complete_correction(workflow, corrected_fact_key=corrected_fact_key)
    delete_instance(identity)
    return True
