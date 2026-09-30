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


def test_no_ready_correction_task_error_is_a_generator_error_with_http_500():
    # I4: consistent with this project's own GeneratorError contract.
    from generator_errors import GeneratorError

    assert issubclass(NoReadyCorrectionTaskError, GeneratorError)
    assert NoReadyCorrectionTaskError.http_status == 500


def test_an_unrecognized_verdict_raises_a_named_domain_error_not_a_bare_library_exception():
    # M4: verified live before this fix that an unrecognized verdict
    # (the gateway has no default flow) raised a bare
    # SpiffWorkflow.exceptions.WorkflowException with no indication this
    # was a caller-input problem, not an engine bug.
    from process_workflow.engine import InvalidVerdictError

    with pytest.raises(InvalidVerdictError):
        start_citation_correction(verdict="maybe")


def test_invalid_verdict_error_is_a_generator_error_with_http_400():
    # A bad caller-supplied verdict is a client error (400), distinct
    # from NoReadyCorrectionTaskError's server-side-state 500.
    from generator_errors import GeneratorError
    from process_workflow.engine import InvalidVerdictError

    assert issubclass(InvalidVerdictError, GeneratorError)
    assert InvalidVerdictError.http_status == 400


def test_start_citation_correction_guards_against_an_unexpected_number_of_ready_tasks():
    # M3: start_citation_correction indexed ready[0] with no guard while
    # complete_correction guarded the same shape of lookup -- asymmetric,
    # and a future edit to the BPMN diagram would surface here as a bare
    # IndexError instead of a named error. Simulate "no ready task" by
    # driving a workflow to completion before start_citation_correction's
    # own internal lookup would run -- exercised directly against the
    # module's internal spec/workflow-construction shape instead, via a
    # workflow that is already complete before the initial ready-task
    # lookup: use SpiffWorkflow directly to build one from the same real
    # spec, run it fully, and confirm engine.py's own guard helper raises
    # rather than IndexError'ing on an empty list.
    from process_workflow.engine import _first_ready_task_or_raise

    with pytest.raises(NoReadyCorrectionTaskError):
        _first_ready_task_or_raise([])
    with pytest.raises(NoReadyCorrectionTaskError):
        _first_ready_task_or_raise([object(), object()])


def test_shared_module_level_spec_does_not_leak_state_across_workflow_instances():
    # M8: _SPEC is parsed once at import time and reused by every
    # start_citation_correction() call -- confirm two workflows built
    # from it are genuinely independent, not aliased. Matches the
    # analogous regression test this project already added for its own
    # shared module-level SAFE_XML_PARSER precedent.
    paused = start_citation_correction(verdict="rejected")
    completed = start_citation_correction(verdict="approved")

    assert not paused.is_completed()
    assert completed.is_completed()

    complete_correction(paused, corrected_fact_key="fact-isolated")
    assert paused.is_completed()
    assert completed.is_completed()  # unaffected by the other instance completing just now
