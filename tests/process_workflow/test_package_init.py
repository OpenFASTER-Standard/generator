"""I1: process_workflow's own public surface -- consumers should import
from here, not reach into process_workflow.engine/store/orchestration
directly, matching annotation_model/__init__.py's own established
convention.
"""
import process_workflow


def test_package_exports_its_stated_public_surface():
    assert process_workflow.start_pending_correction is not None
    assert process_workflow.complete_pending_correction is not None
    assert process_workflow.CorrectionIdentity is not None
    assert process_workflow.CorruptedInstanceError is not None
    assert process_workflow.NoReadyCorrectionTaskError is not None
    assert process_workflow.InvalidVerdictError is not None
