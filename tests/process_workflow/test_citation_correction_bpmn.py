from pathlib import Path

from SpiffWorkflow.bpmn import BpmnWorkflow
from SpiffWorkflow.bpmn.parser import BpmnParser
from SpiffWorkflow.task import TaskState

BPMN_FILE = Path(__file__).resolve().parents[2] / "process_workflow" / "citation_correction.bpmn"


def test_the_real_committed_file_parses_and_starts_at_review_drift():
    parser = BpmnParser()
    parser.add_bpmn_file(str(BPMN_FILE))
    spec = parser.get_spec("CitationCorrection")

    wf = BpmnWorkflow(spec)
    wf.do_engine_steps()

    ready = wf.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "ReviewDrift"
