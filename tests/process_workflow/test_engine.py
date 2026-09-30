import pytest
from SpiffWorkflow.task import TaskState

from process_workflow.engine import (
    NoReadyCorrectionTaskError,
    complete_correction,
    deserialize,
    serialize,
    start_citation_correction,
)


def test_approved_verdict_completes_immediately():
    wf = start_citation_correction(verdict="approved")
    assert wf.is_completed()


def test_rejected_verdict_pauses_at_correct_citation():
    wf = start_citation_correction(verdict="rejected")
    assert not wf.is_completed()
    ready = wf.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"


def test_complete_correction_finishes_the_process_with_both_tasks_data():
    wf = start_citation_correction(verdict="rejected")
    complete_correction(wf, corrected_fact_key="fact-42")

    assert wf.is_completed()
    assert wf.last_task.data == {"verdict": "rejected", "corrected_fact_key": "fact-42"}


def test_complete_correction_on_an_already_completed_workflow_raises():
    wf = start_citation_correction(verdict="approved")
    with pytest.raises(NoReadyCorrectionTaskError):
        complete_correction(wf, corrected_fact_key="fact-42")


def test_serialize_then_deserialize_preserves_a_paused_workflow():
    wf = start_citation_correction(verdict="rejected")
    blob = serialize(wf)

    restored = deserialize(blob)

    ready = restored.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"

    complete_correction(restored, corrected_fact_key="fact-99")
    assert restored.is_completed()
    assert restored.last_task.data["corrected_fact_key"] == "fact-99"
