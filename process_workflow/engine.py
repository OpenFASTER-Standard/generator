"""Thin wrapper around SpiffWorkflow's real start/complete/serialize
calls -- no new execution logic invented here, only generator-domain
naming on top of the library calls verified live this session.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from SpiffWorkflow.bpmn import BpmnWorkflow
from SpiffWorkflow.bpmn.parser import BpmnParser
from SpiffWorkflow.bpmn.serializer import BpmnWorkflowSerializer
from SpiffWorkflow.exceptions import WorkflowException
from SpiffWorkflow.task import Task, TaskState

from generator_errors import GeneratorError

_BPMN_FILE = Path(__file__).resolve().parent / "citation_correction.bpmn"

_parser = BpmnParser()
_parser.add_bpmn_file(str(_BPMN_FILE))
_SPEC = _parser.get_spec("CitationCorrection")


class NoReadyCorrectionTaskError(GeneratorError):
    """Raised when a workflow does not have exactly one ready task where
    exactly one was expected -- either it's already completed, or
    something produced more than one ready task at once, neither of
    which this process is designed to handle silently. A server-side
    state problem, not a caller-input problem."""

    http_status = 500


class InvalidVerdictError(GeneratorError):
    """Raised when start_citation_correction() is given a verdict the
    CitationCorrection diagram's VerdictGateway has no branch for --
    previously surfaced as a bare SpiffWorkflow.exceptions.WorkflowException
    ("No conditions satisfied"), with no indication this was a bad
    caller input rather than an engine bug. A caller-input problem
    (400), not a server-side state problem."""

    http_status = 400


def _first_ready_task_or_raise(ready: list[Task]) -> Task:
    if len(ready) != 1:
        raise NoReadyCorrectionTaskError(f"expected exactly one ready task, found {len(ready)}")
    return ready[0]


def start_citation_correction(*, verdict: Literal["approved", "rejected"]) -> BpmnWorkflow:
    workflow = BpmnWorkflow(_SPEC)
    # A freshly-constructed workflow's only ready "task" is the Start
    # event itself -- do_engine_steps() advances past it (and any other
    # automatic step) to the first real user task.
    workflow.do_engine_steps()
    task = _first_ready_task_or_raise(workflow.get_tasks(state=TaskState.READY))
    task.set_data(verdict=verdict)
    task.run()
    try:
        workflow.do_engine_steps()
    except WorkflowException as exc:
        raise InvalidVerdictError(f"no VerdictGateway branch matches verdict={verdict!r}: {exc}") from exc
    return workflow


def complete_correction(workflow: BpmnWorkflow, *, corrected_fact_key: str) -> None:
    task = _first_ready_task_or_raise(workflow.get_tasks(state=TaskState.READY))
    task.set_data(corrected_fact_key=corrected_fact_key)
    task.run()
    workflow.do_engine_steps()


def serialize(workflow: BpmnWorkflow) -> str:
    return BpmnWorkflowSerializer().serialize_json(workflow)


def deserialize(blob: str) -> BpmnWorkflow:
    return BpmnWorkflowSerializer().deserialize_json(blob)
