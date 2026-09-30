"""Thin wrapper around SpiffWorkflow's real start/complete/serialize
calls -- no new execution logic invented here, only generator-domain
naming on top of the library calls verified live this session.
"""
from __future__ import annotations

from pathlib import Path

from SpiffWorkflow.bpmn import BpmnWorkflow
from SpiffWorkflow.bpmn.parser import BpmnParser
from SpiffWorkflow.bpmn.serializer import BpmnWorkflowSerializer
from SpiffWorkflow.task import TaskState

_BPMN_FILE = Path(__file__).resolve().parent / "citation_correction.bpmn"

_parser = BpmnParser()
_parser.add_bpmn_file(str(_BPMN_FILE))
_SPEC = _parser.get_spec("CitationCorrection")


class NoReadyCorrectionTaskError(Exception):
    """Raised when complete_correction() is given a workflow that does
    not have exactly one ready task -- either it's already completed, or
    something produced more than one ready task at once, neither of
    which this process is designed to handle silently."""


def start_citation_correction(*, verdict: str) -> BpmnWorkflow:
    workflow = BpmnWorkflow(_SPEC)
    # A freshly-constructed workflow's only ready "task" is the Start
    # event itself -- do_engine_steps() advances past it (and any other
    # automatic step) to the first real user task.
    workflow.do_engine_steps()
    ready = workflow.get_tasks(state=TaskState.READY)
    ready[0].set_data(verdict=verdict)
    ready[0].run()
    workflow.do_engine_steps()
    return workflow


def complete_correction(workflow: BpmnWorkflow, *, corrected_fact_key: str) -> None:
    ready = workflow.get_tasks(state=TaskState.READY)
    if len(ready) != 1:
        raise NoReadyCorrectionTaskError(f"expected exactly one ready task, found {len(ready)}")
    ready[0].set_data(corrected_fact_key=corrected_fact_key)
    ready[0].run()
    workflow.do_engine_steps()


def serialize(workflow: BpmnWorkflow) -> str:
    return BpmnWorkflowSerializer().serialize_json(workflow)


def deserialize(blob: str) -> BpmnWorkflow:
    return BpmnWorkflowSerializer().deserialize_json(blob)
