# Stateful Process Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track "a correction is owed" as real, resumable BPMN process
state — created the moment a review verdict is rejected, surviving a
real process restart, completed the moment the correction is actually
provided.

**Architecture:** Five bottom-up tasks, one repository. Task 1 commits
the real BPMN diagram and proves it parses/executes via SpiffWorkflow.
Task 2 wraps the verified SpiffWorkflow calls in generator-domain
naming. Task 3 builds real per-instance file persistence. Task 4 wires
one real existing function (`submit_review`) to start a process, and
adds one new explicit function for a caller to complete one. Task 5 is
the end-to-end proof, including a genuinely separate process for the
resume step.

**Tech Stack:** Python 3.11, `SpiffWorkflow>=3.2.0` (new dependency,
real PyPI package, verified live: exactly one runtime dependency,
`lxml`, already a `generator` dependency).

**Spec:** `docs/specs/2026-09-30-stateful-process-layer-design.md`

## Global Constraints

- **`MIKADIV_PROCESS_INSTANCES_DIR` is read at call time, not import
  time.** Matches `webapp/app.py`'s `_corpus_root()`/`_catalog_path()`
  convention exactly (see that file's own comments) — never a
  module-level `os.environ.get(...)` assignment.
- **An `approved` verdict's process instance is never persisted.** It
  completes immediately inside `start_citation_correction()`/
  `start_pending_correction()`; no file is ever written for it.
- **`add_citation()` is never modified.** The real webapp
  `AddCitationRequest` carries no leaf/drift/fingerprint identity to
  look anything up by (verified live against `webapp/app.py`); wiring a
  guess from `fact_key` alone would be wrong the moment one fact_key has
  more than one independently-flagged leaf. `complete_pending_correction()`
  is a new function for a caller who already has the full identity —
  this plan's own Task 5 test is exactly such a caller.
- **Identity fields**: a `CorrectionIdentity` is
  `(fact_key: str, leaf_reference_id: str, drift_kind: str,
  fingerprint: str)` — matching `review_consultation.consult`'s own
  existing matching key exactly, `drift_kind` stored as the enum's
  `.value` string so `process_workflow` never needs to import
  `review_surfacing`.
- **Filename hashing matches this project's own existing real
  precedent** (`reference_model/model.py`'s `compute_union_reference_id`):
  `hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()` — never
  embed raw field values (user-supplied `fact_key`) directly in a
  filename.

## Review Focus

- **`complete_pending_correction()` genuinely distinguishes "no pending
  instance" (returns `False`) from "pending instance exists but is
  corrupted" (raises)** — the first is an expected, non-error case (not
  every correction originates from this process); the second is a real
  data problem.
- **The `approved` path never touches the filesystem at all** — not
  "the file it would have written happens to be absent," but no
  `save_instance` call happens in that branch. Test by asserting the
  instances directory doesn't even exist afterward, not just that a
  specific file is missing.
- **The Task 5 cross-process resumability test uses a genuinely separate
  process** (`subprocess.run([sys.executable, ...])`), not a second
  in-memory object in the same interpreter — the whole point of this
  layer is state surviving past the process that created it.
- **Two different real identities never collide on the same filename** —
  including one whose `fact_key` contains a literal `"|"` (the real
  join separator) and one that doesn't, which must still hash
  differently from a shifted-field collision.
- **A corrupted instance file's error names the file itself** — not a
  bare `JSONDecodeError`/`KeyError` with no indication of which instance
  broke.

---

### Task 1: Real BPMN diagram, parses and executes

**Files:**
- Modify: `pyproject.toml` (`[project]` `dependencies` list)
- Create: `process_workflow/__init__.py` (empty)
- Create: `process_workflow/citation_correction.bpmn`
- Create: `tests/process_workflow/__init__.py` (empty)
- Test: `tests/process_workflow/test_citation_correction_bpmn.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the committed file at
  `process_workflow/citation_correction.bpmn`, process id
  `CitationCorrection`, task ids `ReviewDrift`/`CorrectCitation`, gateway
  id `VerdictGateway` with conditions on a `verdict` process variable
  (`"approved"`/`"rejected"`) — every later task's `engine.py` parses
  this exact file and these exact ids.

- [ ] **Step 1: Add the dependency**

Add `"SpiffWorkflow>=3.2.0"` to `pyproject.toml`'s `[project]`
`dependencies` list (alongside the existing `lxml`, `rdflib`, etc.
entries). Run `.venv/bin/pip install -e ".[dev]"` to install it.

- [ ] **Step 2: Commit the real BPMN file**

Write `process_workflow/citation_correction.bpmn` with exactly this
content (verified live this session to parse and execute correctly
through both branches, including a real separate-process
serialize/deserialize round-trip):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  targetNamespace="https://openfaster.org/bpmn/citation-correction">
  <bpmn:process id="CitationCorrection" name="Citation Correction" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" name="Drift flagged">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:userTask id="ReviewDrift" name="Review flagged drift">
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:exclusiveGateway id="VerdictGateway" name="Verdict?">
      <bpmn:incoming>Flow_2</bpmn:incoming>
      <bpmn:outgoing>Flow_Approved</bpmn:outgoing>
      <bpmn:outgoing>Flow_Rejected</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:endEvent id="EndApproved" name="Suppressed">
      <bpmn:incoming>Flow_Approved</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:userTask id="CorrectCitation" name="Correct the citation">
      <bpmn:incoming>Flow_Rejected</bpmn:incoming>
      <bpmn:outgoing>Flow_3</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:endEvent id="EndCorrected" name="Correction submitted">
      <bpmn:incoming>Flow_3</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="ReviewDrift" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="ReviewDrift" targetRef="VerdictGateway" />
    <bpmn:sequenceFlow id="Flow_Approved" sourceRef="VerdictGateway" targetRef="EndApproved">
      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">verdict == "approved"</bpmn:conditionExpression>
    </bpmn:sequenceFlow>
    <bpmn:sequenceFlow id="Flow_Rejected" sourceRef="VerdictGateway" targetRef="CorrectCitation">
      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">verdict == "rejected"</bpmn:conditionExpression>
    </bpmn:sequenceFlow>
    <bpmn:sequenceFlow id="Flow_3" sourceRef="CorrectCitation" targetRef="EndCorrected" />
  </bpmn:process>
</bpmn:definitions>
```

- [ ] **Step 3: Write the failing test**

```python
# tests/process_workflow/test_citation_correction_bpmn.py
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_citation_correction_bpmn.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'SpiffWorkflow'` if
Step 1 wasn't run yet, or `FileNotFoundError` if Step 2's file is
missing/misnamed — run Steps 1-2 first if this errors instead of
genuinely asserting).

Actually run this against the state *before* Steps 1-2 by temporarily
renaming the BPMN file, to confirm a real FAIL, then restore it — Steps
1-2 already exist by the time you reach this step in the normal
top-to-bottom flow, so this is a deliberate rather than accidental RED
check.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_citation_correction_bpmn.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml process_workflow/__init__.py process_workflow/citation_correction.bpmn tests/process_workflow/__init__.py tests/process_workflow/test_citation_correction_bpmn.py
git commit -m "feat(process_workflow): commit the real CitationCorrection BPMN diagram"
```

---

### Task 2: `process_workflow/engine.py` — thin SpiffWorkflow wrapper

**Files:**
- Create: `process_workflow/engine.py`
- Test: `tests/process_workflow/test_engine.py`

**Interfaces:**
- Consumes: the committed BPMN file from Task 1 (exact path/ids).
- Produces: `NoReadyCorrectionTaskError(Exception)`.
  `start_citation_correction(*, verdict: str) -> BpmnWorkflow`.
  `complete_correction(workflow: BpmnWorkflow, *, corrected_fact_key: str) -> None`.
  `serialize(workflow: BpmnWorkflow) -> str`.
  `deserialize(blob: str) -> BpmnWorkflow`. Tasks 3-5 use all five.

- [ ] **Step 1: Write the failing test for the approved branch**

```python
# tests/process_workflow/test_engine.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'process_workflow.engine'`).

- [ ] **Step 3: Implement `start_citation_correction(*, verdict: str) -> BpmnWorkflow` in `process_workflow/engine.py`**

Parse `process_workflow/citation_correction.bpmn` (via `BpmnParser` +
`.get_spec("CitationCorrection")` — parsing once at module import time
into a module-level `_SPEC` is fine, since the file never changes at
runtime), construct a fresh `BpmnWorkflow(_SPEC)` per call, find its one
ready task (`wf.get_tasks(state=TaskState.READY)[0]`), call
`task.set_data(verdict=verdict)` then `task.run()`, then
`wf.do_engine_steps()`, then return `wf`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the rejected branch pausing correctly**

```python
def test_rejected_verdict_pauses_at_correct_citation():
    wf = start_citation_correction(verdict="rejected")
    assert not wf.is_completed()
    ready = wf.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: PASS (this should already pass given Step 3's implementation —
run it to confirm rather than assume)

- [ ] **Step 7: Write the failing test for `complete_correction`**

```python
def test_complete_correction_finishes_the_process_with_both_tasks_data():
    wf = start_citation_correction(verdict="rejected")
    complete_correction(wf, corrected_fact_key="fact-42")

    assert wf.is_completed()
    assert wf.last_task.data == {"verdict": "rejected", "corrected_fact_key": "fact-42"}
```

- [ ] **Step 8: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: FAIL (`ImportError`/`AttributeError` for `complete_correction`).

- [ ] **Step 9: Implement `complete_correction(workflow, *, corrected_fact_key: str) -> None`**

Find `workflow.get_tasks(state=TaskState.READY)`; if the length is not
exactly 1, raise `NoReadyCorrectionTaskError(f"expected exactly one "
f"ready task, found {len(ready)}")`. Otherwise call
`ready[0].set_data(corrected_fact_key=corrected_fact_key)`, then
`ready[0].run()`, then `workflow.do_engine_steps()`.

- [ ] **Step 10: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: PASS

- [ ] **Step 11: Write the failing test for `complete_correction` on an already-completed workflow**

```python
def test_complete_correction_on_an_already_completed_workflow_raises():
    wf = start_citation_correction(verdict="approved")
    with pytest.raises(NoReadyCorrectionTaskError):
        complete_correction(wf, corrected_fact_key="fact-42")
```

- [ ] **Step 12: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: PASS (Step 9's guard already covers zero ready tasks; run to
confirm)

- [ ] **Step 13: Write the failing test for a real serialize/deserialize round-trip**

```python
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
```

- [ ] **Step 14: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: FAIL (`ImportError`/`AttributeError` for `serialize`/`deserialize`).

- [ ] **Step 15: Implement `serialize`/`deserialize`**

```python
from SpiffWorkflow.bpmn.serializer import BpmnWorkflowSerializer

def serialize(workflow: BpmnWorkflow) -> str:
    return BpmnWorkflowSerializer().serialize_json(workflow)

def deserialize(blob: str) -> BpmnWorkflow:
    return BpmnWorkflowSerializer().deserialize_json(blob)
```

- [ ] **Step 16: Run all of Task 2's tests to verify they pass**

Run: `.venv/bin/pytest tests/process_workflow/test_engine.py -v`
Expected: PASS (6 passed)

- [ ] **Step 17: Commit**

```bash
git add process_workflow/engine.py tests/process_workflow/test_engine.py
git commit -m "feat(process_workflow): wrap SpiffWorkflow start/complete/serialize calls"
```

---

### Task 3: `process_workflow/store.py` — real per-instance persistence

**Files:**
- Create: `process_workflow/store.py`
- Test: `tests/process_workflow/test_store.py`

**Interfaces:**
- Consumes: `serialize`, `deserialize` (Task 2).
- Produces: `CorrectionIdentity` (frozen dataclass: `fact_key: str`,
  `leaf_reference_id: str`, `drift_kind: str`, `fingerprint: str`).
  `DEFAULT_PROCESS_INSTANCES_DIR: str`.
  `process_instances_dir() -> Path`.
  `CorruptedInstanceError(Exception)`.
  `save_instance(identity: CorrectionIdentity, workflow: BpmnWorkflow) -> None`.
  `load_instance(identity: CorrectionIdentity) -> BpmnWorkflow | None`.
  `delete_instance(identity: CorrectionIdentity) -> None`. Task 4
  consumes all of these.

- [ ] **Step 1: Write the failing test for the default path and call-time env override**

```python
# tests/process_workflow/test_store.py
from pathlib import Path

from process_workflow.store import DEFAULT_PROCESS_INSTANCES_DIR, process_instances_dir


def test_default_path_with_no_env_var(monkeypatch):
    monkeypatch.delenv("MIKADIV_PROCESS_INSTANCES_DIR", raising=False)
    assert process_instances_dir() == Path(DEFAULT_PROCESS_INSTANCES_DIR)


def test_env_var_override_is_read_at_call_time_not_import_time(monkeypatch):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/first")
    assert process_instances_dir() == Path("/tmp/first")
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", "/tmp/second")
    assert process_instances_dir() == Path("/tmp/second")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'process_workflow.store'`).

- [ ] **Step 3: Implement `DEFAULT_PROCESS_INSTANCES_DIR` and `process_instances_dir()` in `process_workflow/store.py`**

```python
DEFAULT_PROCESS_INSTANCES_DIR = "/work/ontologies/mikadiv-fm/process_instances"
```

`process_instances_dir()` returns `Path(os.environ.get(
"MIKADIV_PROCESS_INSTANCES_DIR", DEFAULT_PROCESS_INSTANCES_DIR))` — read
inside the function body, matching `webapp/app.py`'s `_corpus_root()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Write the failing test for `CorrectionIdentity` and save/load round-tripping**

```python
from process_workflow.engine import start_citation_correction
from process_workflow.store import CorrectionIdentity, load_instance, save_instance


def _identity(**overrides) -> CorrectionIdentity:
    fields = dict(fact_key="fact-1", leaf_reference_id="ref-1", drift_kind="CONTENT", fingerprint="fp-1")
    fields.update(overrides)
    return CorrectionIdentity(**fields)


def test_save_then_load_returns_a_resumable_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")

    save_instance(_identity(), wf)
    loaded = load_instance(_identity())

    assert loaded is not None
    from SpiffWorkflow.task import TaskState
    ready = loaded.get_tasks(state=TaskState.READY)
    assert len(ready) == 1
    assert ready[0].task_spec.name == "CorrectCitation"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: FAIL (`ImportError` for `CorrectionIdentity`/`save_instance`/`load_instance`).

- [ ] **Step 7: Implement `CorrectionIdentity`, `_instance_filename`, `save_instance`, `load_instance` in `process_workflow/store.py`**

```python
@dataclass(frozen=True)
class CorrectionIdentity:
    fact_key: str
    leaf_reference_id: str
    drift_kind: str
    fingerprint: str


def _instance_filename(identity: CorrectionIdentity) -> str:
    # Matches reference_model/model.py's compute_union_reference_id's
    # exact real precedent ("|".join(...) then sha256 hexdigest) -- a
    # user-supplied fact_key must never be embedded raw in a filename.
    key = "|".join([identity.fact_key, identity.leaf_reference_id, identity.drift_kind, identity.fingerprint])
    return hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"
```

`save_instance(identity, workflow)`: `process_instances_dir().mkdir(
parents=True, exist_ok=True)`, then write `serialize(workflow)` to
`process_instances_dir() / _instance_filename(identity)`.
`load_instance(identity)`: build the same path; if it doesn't exist,
return `None`; otherwise read its text and call `deserialize(...)`.

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS

- [ ] **Step 9: Write the failing test for loading a never-saved identity**

```python
def test_load_for_a_never_saved_identity_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    assert load_instance(_identity(fact_key="never-saved")) is None
```

- [ ] **Step 10: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS (Step 7's implementation already returns `None` for a
missing file; run to confirm)

- [ ] **Step 11: Write the failing test for a corrupted instance file**

```python
def test_load_for_a_corrupted_file_raises_named_error(monkeypatch, tmp_path):
    from process_workflow.store import CorruptedInstanceError, _instance_filename

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="corrupted")
    bad_path = tmp_path / _instance_filename(identity)
    bad_path.write_text("not valid json at all {{{", encoding="utf-8")

    with pytest.raises(CorruptedInstanceError) as exc_info:
        load_instance(identity)
    assert str(bad_path) in str(exc_info.value)
```

Add `import pytest` to the test file's imports.

- [ ] **Step 12: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: FAIL (`json.JSONDecodeError` propagating uncaught, not
`CorruptedInstanceError` — or `ImportError` if `CorruptedInstanceError`
doesn't exist yet).

- [ ] **Step 13: Make `load_instance` raise `CorruptedInstanceError` on a bad file**

Wrap the `deserialize(...)` call in `try`/`except Exception as exc:
raise CorruptedInstanceError(f"{path}: could not deserialize process "
f"instance: {exc}") from exc` — a broad `except Exception`, matching
`annotation_model/transform/apply.py`'s own established precedent for
"this library call can raise several different real exception types for
different kinds of malformed input, and none of them should reach the
caller bare" (confirmed live: SpiffWorkflow's deserializer raises
`json.JSONDecodeError` for invalid JSON and `KeyError` for
valid-JSON-wrong-shape — both real, both must be caught here).

- [ ] **Step 14: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS

- [ ] **Step 15: Write the failing test for `delete_instance`**

```python
def test_delete_removes_the_file_and_a_second_delete_does_not_raise(monkeypatch, tmp_path):
    from process_workflow.store import delete_instance

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    wf = start_citation_correction(verdict="rejected")
    identity = _identity(fact_key="to-delete")
    save_instance(identity, wf)
    assert load_instance(identity) is not None

    delete_instance(identity)
    assert load_instance(identity) is None
    delete_instance(identity)  # must not raise
```

- [ ] **Step 16: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: FAIL (`ImportError` for `delete_instance`).

- [ ] **Step 17: Implement `delete_instance(identity) -> None`**

```python
def delete_instance(identity: CorrectionIdentity) -> None:
    (process_instances_dir() / _instance_filename(identity)).unlink(missing_ok=True)
```

- [ ] **Step 18: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS

- [ ] **Step 19: Write the failing test proving two real identities never collide**

```python
def test_different_identities_never_collide_on_the_same_filename():
    from process_workflow.store import _instance_filename

    a = _identity(fact_key="alice|bob")  # contains the real join separator
    b = _identity(fact_key="alice", leaf_reference_id="bob|ref-1")  # shifted fields
    assert _instance_filename(a) != _instance_filename(b)
```

Note: this specific pair is NOT expected to collide even with a naive
plain-`"|".join()` (hashing the two different resulting strings already
gives different digests) — the real risk this test guards is a *future*
refactor of `_instance_filename` that stops hashing and starts using the
joined string directly as a path (which a raw `"|"` inside a field could
break by resembling extra join separators); keeping this test in the
suite catches that regression even though today's hash-based
implementation already passes it trivially.

- [ ] **Step 20: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS (already true of Step 7's hash-based implementation; run
to confirm)

- [ ] **Step 21: Run all of Task 3's tests together**

Run: `.venv/bin/pytest tests/process_workflow/test_store.py -v`
Expected: PASS (9 passed)

- [ ] **Step 22: Commit**

```bash
git add process_workflow/store.py tests/process_workflow/test_store.py
git commit -m "feat(process_workflow): persist process instances as one real JSON file each"
```

---

### Task 4: `process_workflow/orchestration.py` + wiring `submit_review()`

**Files:**
- Create: `process_workflow/orchestration.py`
- Modify: `review_workflow/orchestrate.py` (`submit_review()`)
- Test: `tests/process_workflow/test_orchestration.py`
- Test: `tests/review_workflow/test_orchestrate.py` (extend)

**Interfaces:**
- Consumes: `start_citation_correction`, `complete_correction` (Task 2).
  `CorrectionIdentity`, `save_instance`, `load_instance`,
  `delete_instance`, `process_instances_dir` (Task 3). `Verdict`
  (existing, `review_recording/record.py`). `FlaggedLeaf` (existing,
  `review_surfacing/summarize.py`).
- Produces: `start_pending_correction(identity: CorrectionIdentity, *,
  verdict: str) -> None`.
  `complete_pending_correction(identity: CorrectionIdentity, *,
  corrected_fact_key: str) -> bool`. Task 5 uses both.

- [ ] **Step 1: Write the failing test for `start_pending_correction` on rejected**

```python
# tests/process_workflow/test_orchestration.py
from process_workflow.store import CorrectionIdentity, load_instance, process_instances_dir


def _identity(**overrides) -> CorrectionIdentity:
    fields = dict(fact_key="fact-1", leaf_reference_id="ref-1", drift_kind="CONTENT", fingerprint="fp-1")
    fields.update(overrides)
    return CorrectionIdentity(**fields)


def test_start_pending_correction_persists_on_rejected(monkeypatch, tmp_path):
    from process_workflow.orchestration import start_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity()

    start_pending_correction(identity, verdict="rejected")

    loaded = load_instance(identity)
    assert loaded is not None
    assert not loaded.is_completed()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_orchestration.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'process_workflow.orchestration'`).

- [ ] **Step 3: Implement `start_pending_correction(identity, *, verdict: str) -> None` in `process_workflow/orchestration.py`**

```python
def start_pending_correction(identity: CorrectionIdentity, *, verdict: str) -> None:
    workflow = start_citation_correction(verdict=verdict)
    if not workflow.is_completed():
        save_instance(identity, workflow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_orchestration.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test proving the approved path never touches the filesystem**

```python
def test_start_pending_correction_never_persists_on_approved(monkeypatch, tmp_path):
    from process_workflow.orchestration import start_pending_correction

    instances_dir = tmp_path / "process_instances"
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(instances_dir))
    identity = _identity(fact_key="fact-approved")

    start_pending_correction(identity, verdict="approved")

    assert not instances_dir.exists()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_orchestration.py -v`
Expected: PASS (Step 3's `if not workflow.is_completed()` guard already
covers this — `save_instance` is the only code path that creates the
directory; run to confirm rather than assume)

- [ ] **Step 7: Write the failing test for `complete_pending_correction`, both outcomes**

```python
def test_complete_pending_correction_completes_an_existing_instance(monkeypatch, tmp_path):
    from process_workflow.orchestration import complete_pending_correction, start_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    identity = _identity(fact_key="fact-existing")
    start_pending_correction(identity, verdict="rejected")

    result = complete_pending_correction(identity, corrected_fact_key="fact-existing")

    assert result is True
    assert load_instance(identity) is None


def test_complete_pending_correction_returns_false_for_no_matching_instance(monkeypatch, tmp_path):
    from process_workflow.orchestration import complete_pending_correction

    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path))
    result = complete_pending_correction(_identity(fact_key="never-started"), corrected_fact_key="x")
    assert result is False
```

- [ ] **Step 8: Run test to verify it fails**

Run: `.venv/bin/pytest tests/process_workflow/test_orchestration.py -v`
Expected: FAIL (`ImportError` for `complete_pending_correction`).

- [ ] **Step 9: Implement `complete_pending_correction(identity, *, corrected_fact_key: str) -> bool`**

```python
def complete_pending_correction(identity: CorrectionIdentity, *, corrected_fact_key: str) -> bool:
    workflow = load_instance(identity)
    if workflow is None:
        return False
    complete_correction(workflow, corrected_fact_key=corrected_fact_key)
    delete_instance(identity)
    return True
```

- [ ] **Step 10: Run all of Task 4's new tests together**

Run: `.venv/bin/pytest tests/process_workflow/test_orchestration.py -v`
Expected: PASS (4 passed)

- [ ] **Step 11: Read `review_workflow/orchestrate.py`'s current `submit_review()` and `tests/review_workflow/test_orchestrate.py` in full**

No code change in this step — confirm the exact real signature
(`submit_review(catalog_path, reviews_dir, fact_key, flagged, reviewer,
verdict, reasoning) -> Revision`) and the existing tests'
`_real_leaf`/`FlaggedLeaf` construction pattern before modifying it.

- [ ] **Step 12: Write the failing test extending `test_orchestrate.py` for the new wiring**

Add to `tests/review_workflow/test_orchestrate.py` (matching its
existing `_real_leaf`/`FlaggedLeaf` fixture pattern exactly):

```python
def test_submit_review_starts_a_pending_correction_on_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path / "instances"))
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "rejected-key", leaf, "author", "comment", False)

    flagged = FlaggedLeaf(
        leaf=leaf, outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT, fingerprint="fp-rejected",
    )

    submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "rejected-key", flagged,
        "reviewer-1", Verdict.REJECTED, "not fixed yet",
    )

    from process_workflow.store import CorrectionIdentity, load_instance
    identity = CorrectionIdentity(
        fact_key="rejected-key", leaf_reference_id=leaf.reference_id,
        drift_kind="CONTENT", fingerprint="fp-rejected",
    )
    assert load_instance(identity) is not None


def test_submit_review_does_not_persist_a_process_instance_on_approved(tmp_path, monkeypatch):
    instances_dir = tmp_path / "instances"
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(instances_dir))
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "approved-key", leaf, "author", "comment", False)

    flagged = FlaggedLeaf(
        leaf=leaf, outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT, fingerprint="fp-approved",
    )

    submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "approved-key", flagged,
        "reviewer-1", Verdict.APPROVED, "looks fine",
    )

    assert not instances_dir.exists()
```

- [ ] **Step 13: Run test to verify it fails**

Run: `.venv/bin/pytest tests/review_workflow/test_orchestrate.py -v`
Expected: FAIL (the two new tests fail — `load_instance(identity)` is
`None` for the rejected case, since `submit_review()` doesn't yet call
`start_pending_correction`; the approved case likely already passes
trivially since nothing persists anything yet, which is not a
meaningful pass — confirm by checking only the rejected test's failure
matters here).

- [ ] **Step 14: Modify `submit_review()` in `review_workflow/orchestrate.py`**

After the existing `record_review()`+`add_revision()` calls, add:

```python
from process_workflow.orchestration import start_pending_correction
from process_workflow.store import CorrectionIdentity

# ... inside submit_review(), after building `leaf` and `revision`:
identity = CorrectionIdentity(
    fact_key=fact_key,
    leaf_reference_id=flagged.leaf.reference_id,
    drift_kind=flagged.drift_kind.value,
    fingerprint=flagged.fingerprint,
)
start_pending_correction(identity, verdict=verdict.value)
```

Place this after `add_revision(...)`'s existing return-value assignment,
before `submit_review()`'s own `return` statement — the function's
return value (the `Revision`) is unchanged.

- [ ] **Step 15: Run all of `test_orchestrate.py` to verify everything passes, old and new**

Run: `.venv/bin/pytest tests/review_workflow/test_orchestrate.py -v`
Expected: PASS (every pre-existing test in this file still passes,
proving `submit_review()`'s existing return value/behavior is
unchanged, plus the 2 new tests)

- [ ] **Step 16: Commit**

```bash
git add process_workflow/orchestration.py tests/process_workflow/test_orchestration.py review_workflow/orchestrate.py tests/review_workflow/test_orchestrate.py
git commit -m "feat(process_workflow): wire submit_review() to start a pending correction on rejection"
```

---

### Task 5: End-to-end proof — genuine cross-process resumability

**Files:**
- Test: `tests/process_workflow/test_end_to_end.py`
- Create: `tests/process_workflow/_complete_correction_subprocess.py` (a
  small script, not a test file itself — invoked via `subprocess.run`)

**Interfaces:**
- Consumes: `submit_review` (existing, extended by Task 4).
  `add_citation` (existing, unmodified). `complete_pending_correction`,
  `CorrectionIdentity` (Tasks 3-4).
- Produces: nothing further — this is the plan's final task.

- [ ] **Step 1: Write the subprocess helper script**

```python
# tests/process_workflow/_complete_correction_subprocess.py
"""Invoked via `subprocess.run([sys.executable, __file__, ...])` by
test_end_to_end.py -- runs in a genuinely separate Python process so
that loading a persisted process instance here proves real cross-process
resumability, not just that one Python object survived a round-trip in
the same interpreter.

Usage: python _complete_correction_subprocess.py <fact_key>
       <leaf_reference_id> <drift_kind> <fingerprint> <corrected_fact_key>

Prints "True" or "False" (the real return value of
complete_pending_correction) to stdout.
"""
import sys

from process_workflow.orchestration import complete_pending_correction
from process_workflow.store import CorrectionIdentity

if __name__ == "__main__":
    fact_key, leaf_reference_id, drift_kind, fingerprint, corrected_fact_key = sys.argv[1:6]
    identity = CorrectionIdentity(
        fact_key=fact_key, leaf_reference_id=leaf_reference_id,
        drift_kind=drift_kind, fingerprint=fingerprint,
    )
    result = complete_pending_correction(identity, corrected_fact_key=corrected_fact_key)
    print(result)
```

- [ ] **Step 2: Write the failing end-to-end test**

```python
# tests/process_workflow/test_end_to_end.py
import subprocess
import sys
from pathlib import Path

from reference_model.model import ResolutionOutcome, Status
from review_recording.record import Verdict
from review_surfacing.summarize import DriftKind, FlaggedLeaf
from review_workflow.orchestrate import submit_review
from citation_workflow.add_citation import add_citation
from staleness_sweep.resolve import resolve_family_location
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

pytestmark = requires_real_corpus

SUBPROCESS_SCRIPT = Path(__file__).resolve().parent / "_complete_correction_subprocess.py"
FIRST_XPATH = "/xs:schema/xs:complexType[@name='Meldeart23']"
CORRECTED_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _real_leaf(xpath: str):
    location = resolve_family_location(REAL_CORPUS_ROOT, "MiKaDiv_FM_Meldeart23")
    subject_document = SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=location.retrieval_uri)
    return cite(subject_document, XPathSelector.create(xpath))


def test_a_rejected_review_pauses_and_a_later_correction_resumes_it_in_a_separate_process(tmp_path, monkeypatch):
    instances_dir = tmp_path / "instances"
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(instances_dir))
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")

    leaf = _real_leaf(FIRST_XPATH)
    from references_catalog.catalog import add_revision
    add_revision(str(catalog_path), "e2e-key", leaf, "author", "initial", False)

    flagged = FlaggedLeaf(
        leaf=leaf, outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT, fingerprint="e2e-fingerprint",
    )
    submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "e2e-key", flagged,
        "reviewer-1", Verdict.REJECTED, "needs a real correction",
    )
    assert instances_dir.exists() and any(instances_dir.iterdir())

    add_citation(
        REAL_CORPUS_ROOT, str(catalog_path),
        family="MiKaDiv_FM_Meldeart23", xpath=CORRECTED_XPATH,
        fact_key="e2e-key", author="author", comment="corrected", is_correction=True,
    )

    # `env=None` (subprocess.run's default -- just omit the argument) is
    # the right choice here, not a restricted custom dict: it inherits
    # the *whole* current process's environment, which already has
    # monkeypatch's MIKADIV_PROCESS_INSTANCES_DIR override in it (env
    # vars set via os.environ/monkeypatch are always inherited by
    # subprocesses unless explicitly overridden) plus this venv's own
    # PATH/VIRTUAL_ENV, so the subprocess's `sys.executable` resolves
    # its imports the same way this test process does. `cwd` is still
    # set explicitly to the repo root so `process_workflow`/etc. are
    # importable regardless of where pytest itself was invoked from.
    result = subprocess.run(
        [sys.executable, str(SUBPROCESS_SCRIPT), "e2e-key", leaf.reference_id, "CONTENT", "e2e-fingerprint", "e2e-key"],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "True"
    assert not any(instances_dir.iterdir())

    second_run = subprocess.run(
        [sys.executable, str(SUBPROCESS_SCRIPT), "e2e-key", leaf.reference_id, "CONTENT", "e2e-fingerprint", "e2e-key"],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True, text=True, check=True,
    )
    assert second_run.stdout.strip() == "False"
```

- [ ] **Step 3: Run test to verify it passes**

Run: `.venv/bin/pytest tests/process_workflow/test_end_to_end.py -v`
Expected: PASS. If the subprocess call fails instead (check
`result.stderr` in the traceback for the real cause — e.g. a
`ModuleNotFoundError` would mean `cwd` isn't resolving to the repo root
correctly, or the project wasn't installed in editable mode back in
Task 1 Step 1), use superpowers:systematic-debugging rather than
patching around it with a broader `env=` override — inheriting the
full parent environment is already the correct, standard choice.

- [ ] **Step 4: Run the whole project's test suite to confirm nothing regressed**

Run: `.venv/bin/pytest`
Expected: PASS (all pre-existing tests still pass; the new
`tests/process_workflow/` tests and the 2 new tests in
`tests/review_workflow/test_orchestrate.py` all pass too)

- [ ] **Step 5: Commit**

```bash
git add tests/process_workflow/test_end_to_end.py tests/process_workflow/_complete_correction_subprocess.py
git commit -m "test(process_workflow): prove genuine cross-process resumability end to end"
```
