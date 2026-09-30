# Task ID: 5

**Title:** Design and implement stateful process layer (BPMN 2.0-based workflow engine)

**Status:** pending

**Dependencies:** 1 ✓, 2 ✓, 3 ✓

**Priority:** low

**Description:** Build a BPMN 2.0-based stateful process engine for multi-step regulatory interactions (submit, acknowledge, correct, resubmit, decide), deliberately separated from the pure declarative transformation layer. Based on real prior art (BPMN 2.0 Petri-net semantics, Camunda/Zeebe open-source engines) and reuses Task 3's shape-driven UI generation for process task forms.

**Details:**

## Overview

This task implements a stateful workflow engine for the subset of ground-truth processes that are genuinely multi-step, stateful interactions with external systems (e.g., KaFE/MiKaDiv-FM submission pipeline: submit → await acknowledgement → correct → resubmit → await decision) rather than single pure input-to-output mappings. This is deliberately kept as a **separate mechanism** from the declarative transformation layer (Task 2) to avoid the known anti-pattern of folding stateful process logic into pure data-mapping logic, which leads to untestable mappings and cluttered process definitions.

**Ground Truth Prior Art** (not invented here):
- **BPMN 2.0 (OMG Standard)**: Business Process Model and Notation with Petri-net-derived formal semantics for process definition, execution, and state management. Defines process elements (tasks, gateways, events), execution tokens, and sequence flows.
- **Camunda/Zeebe**: Production-grade open-source BPMN engines used in real regtech/KYC workflow systems. Zeebe specifically provides horizontal scalability and event-driven architecture for long-running processes.
- **counterparty-mock's 6-stage KaFE submission pipeline**: Already models exactly this shape in `/work/counterparty-mock` (submission → pre-validation → validation → processing → acknowledgement → decision stages with corrections) — just not yet named/structured as a BPMN process.

**Separation from Task 2 (Declarative Transformation Layer)**:
- **Task 2**: Pure, stateless graph-to-graph/graph-to-document transformations with no process state. Input → transformation rules → output, no waiting, no external system interaction.
- **This Task**: Stateful processes where execution pauses at human task steps or external service calls, resumes when events arrive, maintains process instance state across time, and handles corrections/retries.

**Integration with Task 3 (Shape-driven UI)**:
- Reuse Task 3's shape-rendering engine to generate task forms for human interaction steps in processes
- BPMN User Tasks reference SHACL shapes (from Task 1) for their input/output schemas
- The same `@openfaster-standard/ui` shape renderer that generates data-entry forms generates process task forms

## Architecture

### 1. Process Definition Layer (BPMN 2.0 XML)

**Core BPMN Elements to Support** (aligned with counterparty-mock's real workflow):
- **Tasks**: 
  - `ServiceTask`: Automated calls to external systems (e.g., submit to KaFE API)
  - `UserTask`: Human interaction points (e.g., review validation errors, provide corrections)
  - `ScriptTask`: Inline logic (e.g., validate schema compliance before submission)
- **Gateways**:
  - `ExclusiveGateway`: XOR decision points (e.g., validation passed/failed)
  - `ParallelGateway`: AND splits/joins for concurrent execution
- **Events**:
  - `StartEvent`: Process instance creation trigger
  - `IntermediateCatchEvent`: Wait for external events (e.g., acknowledgement received from KaFE)
  - `EndEvent`: Process completion (success/failure/cancellation)
- **Sequence Flows**: Directed edges between elements with optional conditions

**Process Definition Storage**:
- BPMN 2.0 XML files in `processes/definitions/` (e.g., `mikadiv-fm-submission.bpmn`)
- Version control: each deployment creates immutable process definition version
- Reference existing process definitions from counterparty-mock's implicit 6-stage pipeline as the first concrete process to model

### 2. Process Engine Core

**Process Instance State Management**:
```python
@dataclass(frozen=True)
class ProcessInstance:
    """A single execution of a process definition."""
    instance_id: str  # UUID
    process_definition_id: str
    process_definition_version: int
    state: ProcessState  # RUNNING | SUSPENDED | COMPLETED | TERMINATED
    current_tokens: list[Token]  # Petri-net execution tokens
    variables: dict[str, Any]  # Process instance variables (mutable across execution)
    started_at: str  # ISO datetime
    completed_at: str | None
    parent_instance_id: str | None  # For sub-processes

@dataclass(frozen=True)
class Token:
    """Execution position in the process (Petri-net token)."""
    token_id: str
    current_element_id: str  # BPMN element ID where this token currently resides
    scope_id: str  # For nested scopes (sub-processes, multi-instance)

class ProcessState(Enum):
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"  # Waiting for external event or user action
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"  # Cancelled or errored
```

**Execution Engine**:
- Token-based execution following Petri-net semantics (BPMN 2.0 spec §13)
- `execute_step(instance_id, token_id)`: Advance one token by one element
- `complete_task(instance_id, task_id, output_data)`: Resume from completed user/service task
- `correlate_event(instance_id, event_name, payload)`: Resume from intermediate catch event
- State persistence after every step for crash recovery

### 3. Task Execution Layer

**Service Task Executor**:
```python
class ServiceTaskExecutor:
    """Executes automated service calls to external systems."""
    
    async def execute(self, task_def: ServiceTask, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Invokes configured service endpoint with process variables as input.
        
        Examples from counterparty-mock:
        - Submit MiKaDiv-VIB XML to KaFE endpoint
        - Poll for acknowledgement status
        - Retrieve decision notification
        
        Returns: Output variables to merge back into process instance
        Raises: ServiceTaskError on failures (triggers BPMN error boundary events)
        """
        pass
```

**User Task Manager** (integrates with Task 3):
```python
class UserTaskManager:
    """Manages human interaction steps, integrated with shape-driven UI."""
    
    def create_task(self, process_instance_id: str, task_def: UserTask) -> UserTaskInstance:
        """
        Creates a user task instance that pauses process execution.
        
        Integration with Task 3:
        - task_def.form_schema references a SHACL shape ID (from Task 1)
        - Frontend calls shape renderer to generate form UI from that shape
        - User fills form, submits → complete_task() resumes process
        """
        pass
    
    def get_pending_tasks(self, assignee: str | None = None) -> list[UserTaskInstance]:
        """Returns task inbox for assignment/claiming."""
        pass
    
    def complete_task(self, task_id: str, form_data: dict[str, Any]) -> None:
        """Validates form data against shape, merges into process variables, resumes execution."""
        pass
```

### 4. Event Correlation

**External Event Handling** (critical for KaFE-style acknowledgement flows):
```python
class EventCorrelator:
    """Correlates external events to waiting process instances."""
    
    def correlate(self, event_name: str, correlation_keys: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        """
        Finds process instances waiting for this event via correlation keys.
        
        Example: KaFE acknowledgement arrives with submission_id=X
        → Find process instance with variables.submission_id=X waiting at "Acknowledgement Received" event
        → Resume that instance with acknowledgement payload
        
        Returns: List of resumed instance IDs
        """
        pass
```

### 5. Process Definition from counterparty-mock

**Map counterparty-mock's 6-stage pipeline to BPMN**:

The existing Java/Spring Boot counterparty-mock at `/work/counterparty-mock` already implements a stateful submission pipeline:
1. **Submission**: Receive MiKaDiv-VIB XML upload
2. **Pre-validation**: Schema validation, basic checks
3. **Validation**: Deep regulatory validation
4. **Processing**: Business logic, enrichment
5. **Acknowledgement**: Send ACK/NACK to submitter
6. **Decision**: Final acceptance/rejection decision

**BPMN Modeling** (first concrete process definition):
```xml
<!-- processes/definitions/mikadiv-fm-submission.bpmn (excerpt) -->
<bpmn:process id="MiKaDivFMSubmission" name="MiKaDiv-FM Submission to KaFE">
  
  <bpmn:startEvent id="StartEvent_Submit" name="Submission Received" />
  
  <bpmn:serviceTask id="Task_PreValidation" name="Pre-validation">
    <bpmn:extensionElements>
      <openfaster:serviceConnector type="XSDSchemaValidator" />
    </bpmn:extensionElements>
  </bpmn:serviceTask>
  
  <bpmn:exclusiveGateway id="Gateway_PreValidOK" name="Pre-validation OK?" />
  
  <bpmn:userTask id="Task_FixPreValidationErrors" name="Fix Pre-validation Errors">
    <bpmn:extensionElements>
      <openfaster:formSchema shapeId="urn:openfaster:shapes:ValidationErrorCorrection" />
    </bpmn:extensionElements>
  </bpmn:userTask>
  
  <bpmn:serviceTask id="Task_SubmitToKaFE" name="Submit to KaFE" />
  
  <bpmn:intermediateCatchEvent id="Event_AckReceived" name="Acknowledgement Received">
    <bpmn:messageEventDefinition messageRef="KaFEAcknowledgement" />
  </bpmn:intermediateCatchEvent>
  
  <bpmn:exclusiveGateway id="Gateway_AckAccepted" name="Accepted?" />
  
  <!-- Rejection path with corrections -->
  <bpmn:userTask id="Task_ProvideCorrections" name="Provide Corrections">
    <bpmn:extensionElements>
      <openfaster:formSchema shapeId="urn:openfaster:shapes:SubmissionCorrection" />
    </bpmn:extensionElements>
  </bpmn:userTask>
  
  <!-- Loop back to resubmit -->
  <bpmn:sequenceFlow sourceRef="Task_ProvideCorrections" targetRef="Task_SubmitToKaFE" />
  
  <bpmn:intermediateCatchEvent id="Event_DecisionReceived" name="Decision Received">
    <bpmn:messageEventDefinition messageRef="KaFEDecision" />
  </bpmn:intermediateCatchEvent>
  
  <bpmn:endEvent id="EndEvent_Completed" name="Submission Completed" />
  
</bpmn:process>
```

### 6. Storage and Persistence

**Database Schema** (PostgreSQL):
```sql
CREATE TABLE process_definitions (
    definition_id TEXT PRIMARY KEY,
    version INT NOT NULL,
    bpmn_xml TEXT NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL,
    UNIQUE(definition_id, version)
);

CREATE TABLE process_instances (
    instance_id UUID PRIMARY KEY,
    definition_id TEXT NOT NULL,
    definition_version INT NOT NULL,
    state TEXT NOT NULL,  -- RUNNING | SUSPENDED | COMPLETED | TERMINATED
    variables JSONB NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    parent_instance_id UUID,
    FOREIGN KEY (definition_id, definition_version) REFERENCES process_definitions(definition_id, version)
);

CREATE TABLE execution_tokens (
    token_id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES process_instances(instance_id),
    current_element_id TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    INDEX idx_instance_active (instance_id) WHERE current_element_id IS NOT NULL
);

CREATE TABLE user_task_instances (
    task_id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES process_instances(instance_id),
    task_definition_id TEXT NOT NULL,
    form_shape_id TEXT,  -- References SHACL shape from Task 1
    assignee TEXT,
    state TEXT NOT NULL,  -- CREATED | CLAIMED | COMPLETED | CANCELLED
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    form_data JSONB
);

CREATE TABLE event_subscriptions (
    subscription_id UUID PRIMARY KEY,
    instance_id UUID NOT NULL REFERENCES process_instances(instance_id),
    event_name TEXT NOT NULL,
    correlation_keys JSONB NOT NULL,  -- e.g., {"submission_id": "ABC123"}
    created_at TIMESTAMPTZ NOT NULL,
    INDEX idx_correlation (event_name, correlation_keys) USING gin
);
```

### 7. API Layer

**REST Endpoints** (Flask/FastAPI):
```python
# Process deployment
POST /api/processes/deploy
  Body: { "bpmn_xml": "..." }
  Response: { "definition_id": "...", "version": 1 }

# Start new process instance
POST /api/processes/{definition_id}/start
  Body: { "variables": {...} }
  Response: { "instance_id": "..." }

# Query process instance
GET /api/processes/instances/{instance_id}
  Response: { "instance_id": "...", "state": "RUNNING", "current_activities": [...], "variables": {...} }

# User task inbox
GET /api/tasks
  Query: assignee=user@example.com, state=CREATED
  Response: [{ "task_id": "...", "name": "Fix Validation Errors", "form_shape_id": "urn:...", "created_at": "..." }, ...]

# Complete user task
POST /api/tasks/{task_id}/complete
  Body: { "form_data": {...} }
  Response: { "success": true }

# Correlate external event
POST /api/events/correlate
  Body: { "event_name": "KaFEAcknowledgement", "correlation_keys": {"submission_id": "X"}, "payload": {...} }
  Response: { "correlated_instances": ["..."] }
```

## Implementation Phases

### Phase 1: Core Engine Foundation
- BPMN 2.0 XML parser (using existing Python BPMN libraries like `camunda-modeler-python` or `spiffworkflow`)
- Token-based execution engine with Petri-net semantics
- Process instance state management and persistence
- Basic task executors (service task, user task stubs)

### Phase 2: Integration with Tasks 1 & 3
- Link UserTask form schemas to SHACL shape IDs (Task 1)
- Extend Task 3's shape renderer to accept user task context
- Implement form data validation against SHACL shapes before task completion
- Test round-trip: create user task → render form from shape → validate submission → resume process

### Phase 3: Event Correlation & External Systems
- Event subscription mechanism for IntermediateCatchEvents
- Correlation engine matching external events to waiting instances
- ServiceTask executor framework with pluggable connectors
- First connector: counterparty-mock's KaFE API (submit, poll acknowledgement, retrieve decision)

### Phase 4: counterparty-mock Process Migration
- Model counterparty-mock's 6-stage pipeline as BPMN 2.0 XML
- Define SHACL shapes for correction/validation-error forms
- Deploy process definition and run end-to-end test:
  - Submit MiKaDiv-VIB XML
  - Pre-validate (automated)
  - Submit to KaFE (service task)
  - Wait for acknowledgement (event correlation)
  - Handle rejection → corrections (user task with shape-driven form) → resubmit loop
  - Final decision → completion
- Compare behavior with counterparty-mock's existing Java implementation for correctness

### Phase 5: Monitoring & Operations
- Process instance history and audit log
- Visual process diagram with current token positions (BPMN.io integration)
- Failed task retry/escalation mechanisms
- Metrics: active instances, completed throughput, average cycle time per process

## Technical Decisions

**Why BPMN 2.0, not custom workflow DSL?**
- Industry-standard graphical notation understood by business analysts and regulators
- Formal Petri-net semantics prevent ambiguity in execution
- Tooling ecosystem (BPMN.io modeler, Camunda Cockpit for monitoring)
- Real production validation in regtech systems

**Why separate from Task 2's transformation layer?**
- Pure transformations (Task 2) compose/test easily; stateful processes don't
- Mixing them creates untestable mapping logic with hidden side effects
- Separate concerns: Task 2 = "what output document?", This Task = "what workflow steps?"
- Real-world parallel: XBRL DPM (pure mapping) vs. regulatory submission portals (stateful workflows) are distinct systems

**Language choice: Python or TypeScript?**
- Python: Aligns with existing `/work/generator` codebase (reference_model, staleness_sweep, etc. are Python)
- TypeScript: Aligns with `/work/counterparty-mock` (Spring Boot/Java), but OpenFASTER ecosystem is primarily Python
- **Recommendation: Python** for consistency with this repo, with TypeScript/Java connectors for external system integration

**Persistence: Why PostgreSQL?**
- JSONB for process variables (flexible, queryable schema-on-read)
- ACID transactions for state consistency (critical for Petri-net token semantics)
- GIN indexes for event correlation (fast lookup by correlation keys)
- Already used in counterparty-mock's own stack

## Files to Create/Modify

**New directories/modules**:
- `processes/` (top-level, sibling to `reference_model/`, `staleness_sweep/`, etc.)
  - `processes/definitions/` - BPMN XML process definitions
  - `processes/engine/` - Core execution engine
    - `engine/bpmn_parser.py` - Parse BPMN 2.0 XML to internal model
    - `engine/token_executor.py` - Petri-net token-based execution
    - `engine/state_manager.py` - Process instance state persistence
  - `processes/tasks/` - Task executor implementations
    - `tasks/service_task_executor.py`
    - `tasks/user_task_manager.py`
  - `processes/events/` - Event correlation
    - `events/correlator.py`
    - `events/subscription_manager.py`
  - `processes/api/` - REST API layer
    - `api/process_routes.py` - Process deployment/start endpoints
    - `api/task_routes.py` - User task inbox/completion
    - `api/event_routes.py` - Event correlation endpoint

**Integration points**:
- `webapp/frontend/src/components/ProcessTaskForm.tsx` - Wrapper around Task 3's shape renderer for user task forms
- `processes/engine/shape_validator.py` - Validate user task form data against SHACL shapes (calls Task 1's shape resolution)
- `processes/connectors/counterparty_mock_connector.py` - ServiceTask connector for counterparty-mock's KaFE API

**First concrete artifact**:
- `processes/definitions/mikadiv-fm-submission.bpmn` - BPMN 2.0 model of counterparty-mock's 6-stage pipeline

## Non-Goals (Explicitly Out of Scope)

- BPMN Choreography or Collaboration diagrams (only Process diagrams)
- Multi-tenancy / organizational hierarchy (single-tenant for initial release)
- Hot-deployment of process definitions (require restart/migration)
- BPMN 1.x compatibility (2.0 only)
- Full Camunda/Zeebe API compatibility (inspired by, not drop-in replacement)

**Test Strategy:**

## Verification Strategy

### 1. Design Approval Gate

**Pre-Implementation Checkpoint**:
- [ ] Design spec in `docs/specs/stateful-process-layer-design.md` reviewed and approved
- [ ] Stakeholder confirmation: BPMN 2.0 approach aligns with regtech/KYC production practices
- [ ] Technical validation: Separation from Task 2 (transformation layer) is architecturally sound
- [ ] Integration plan with Tasks 1 & 3 confirmed feasible

### 2. BPMN Parser Tests (`tests/processes/engine/test_bpmn_parser.py`)

**Test BPMN 2.0 XML parsing**:
```python
def test_parse_simple_sequence():
    """Parse: StartEvent → ServiceTask → EndEvent"""
    bpmn_xml = """
    <bpmn:process id="SimpleProcess">
      <bpmn:startEvent id="start" />
      <bpmn:serviceTask id="task1" name="Do Work" />
      <bpmn:endEvent id="end" />
      <bpmn:sequenceFlow sourceRef="start" targetRef="task1" />
      <bpmn:sequenceFlow sourceRef="task1" targetRef="end" />
    </bpmn:process>
    """
    process_def = BPMNParser.parse(bpmn_xml)
    assert process_def.id == "SimpleProcess"
    assert len(process_def.elements) == 3
    assert process_def.get_element("task1").type == "serviceTask"
    assert process_def.get_outgoing_flows("start") == ["task1"]

def test_parse_exclusive_gateway():
    """Parse: Gateway with conditional sequence flows"""
    # Test XOR split/join with conditions
    assert gateway.type == "exclusiveGateway"
    assert flow.condition == "${validationPassed == true}"

def test_parse_user_task_with_form_schema():
    """Parse: UserTask with SHACL shape reference in extensionElements"""
    assert user_task.form_shape_id == "urn:openfaster:shapes:ValidationErrorCorrection"
```

### 3. Token Execution Engine Tests (`tests/processes/engine/test_token_executor.py`)

**Test Petri-net token-based execution**:
```python
def test_execute_simple_sequence(db_session):
    """Execute: StartEvent → ServiceTask → EndEvent"""
    process_def = load_test_process("simple_sequence.bpmn")
    instance = ProcessEngine.start_instance(process_def.id, variables={})
    
    # Initially: one token at StartEvent
    tokens = db_session.query(ExecutionToken).filter_by(instance_id=instance.instance_id).all()
    assert len(tokens) == 1
    assert tokens[0].current_element_id == "start"
    
    # Execute one step: token moves to ServiceTask
    ProcessEngine.execute_step(instance.instance_id, tokens[0].token_id)
    tokens = reload_tokens(instance.instance_id)
    assert len(tokens) == 1
    assert tokens[0].current_element_id == "task1"
    
    # Complete service task (stub executor returns immediately)
    ProcessEngine.execute_step(instance.instance_id, tokens[0].token_id)
    tokens = reload_tokens(instance.instance_id)
    assert len(tokens) == 1
    assert tokens[0].current_element_id == "end"
    
    # Execute EndEvent: process completes, token consumed
    ProcessEngine.execute_step(instance.instance_id, tokens[0].token_id)
    assert ProcessInstance.query.get(instance.instance_id).state == ProcessState.COMPLETED
    assert ExecutionToken.query.filter_by(instance_id=instance.instance_id).count() == 0

def test_exclusive_gateway_splits_token_conditionally(db_session):
    """XOR gateway: only one outgoing flow activates based on condition"""
    instance = start_process_with_variables({"score": 85})
    # Gateway with conditions: score >= 80 → path A, else → path B
    # Execute until gateway, then verify only one token on correct path
    assert token.current_element_id == "pathA_task"

def test_parallel_gateway_creates_concurrent_tokens(db_session):
    """AND gateway: multiple tokens created for concurrent execution"""
    instance = start_process("parallel_split.bpmn")
    # ParallelGateway with 3 outgoing flows
    execute_until_gateway(instance.instance_id)
    tokens = reload_tokens(instance.instance_id)
    assert len(tokens) == 3  # One token per parallel path
    assert {t.current_element_id for t in tokens} == {"taskA", "taskB", "taskC"}
```

### 4. User Task Integration Tests (`tests/processes/tasks/test_user_task_manager.py`)

**Test user task creation, form rendering, and completion**:
```python
def test_create_user_task_pauses_process(db_session):
    """Process execution pauses at UserTask until manually completed"""
    instance = start_process("user_task_flow.bpmn")
    execute_until_user_task(instance.instance_id)
    
    # Process is SUSPENDED, waiting for user input
    assert instance.state == ProcessState.SUSPENDED
    user_tasks = UserTaskManager.get_pending_tasks()
    assert len(user_tasks) == 1
    assert user_tasks[0].task_definition_id == "Task_FixErrors"
    assert user_tasks[0].form_shape_id == "urn:openfaster:shapes:ValidationErrorCorrection"

def test_complete_user_task_validates_against_shape(db_session):
    """UserTask completion validates form data against SHACL shape"""
    task_id = create_test_user_task(shape_id="urn:openfaster:shapes:SimpleForm")
    
    # Invalid data (violates shape constraints)
    with pytest.raises(ShapeValidationError):
        UserTaskManager.complete_task(task_id, form_data={"invalidField": "value"})
    
    # Valid data (conforms to shape)
    UserTaskManager.complete_task(task_id, form_data={"requiredField": "value"})
    assert UserTaskInstance.query.get(task_id).state == "COMPLETED"

def test_complete_user_task_resumes_process(db_session):
    """Completing user task merges form data into process variables and resumes execution"""
    instance = start_process_with_user_task()
    task_id = get_pending_task_id(instance.instance_id)
    
    UserTaskManager.complete_task(task_id, form_data={"correctedValue": "ABC"})
    
    # Process variables updated
    instance = reload_instance(instance.instance_id)
    assert instance.variables["correctedValue"] == "ABC"
    
    # Process resumed to next element
    tokens = reload_tokens(instance.instance_id)
    assert tokens[0].current_element_id == "nextTask"
```

### 5. Event Correlation Tests (`tests/processes/events/test_correlator.py`)

**Test external event correlation to waiting process instances**:
```python
def test_correlate_event_resumes_waiting_instance(db_session):
    """External event arriving correlates to waiting instance via correlation keys"""
    # Start process that waits for external event
    instance = start_process("event_wait_flow.bpmn", variables={"submissionId": "X123"})
    execute_until_event(instance.instance_id, "Event_AckReceived")
    
    # Process is SUSPENDED, event subscription created
    assert instance.state == ProcessState.SUSPENDED
    sub = EventSubscription.query.filter_by(instance_id=instance.instance_id).one()
    assert sub.event_name == "KaFEAcknowledgement"
    assert sub.correlation_keys == {"submissionId": "X123"}
    
    # External event arrives with matching correlation key
    correlated = EventCorrelator.correlate(
        event_name="KaFEAcknowledgement",
        correlation_keys={"submissionId": "X123"},
        payload={"status": "ACCEPTED"}
    )
    
    # Process resumed, payload merged into variables
    assert len(correlated) == 1
    assert correlated[0] == instance.instance_id
    instance = reload_instance(instance.instance_id)
    assert instance.state == ProcessState.RUNNING
    assert instance.variables["acknowledgementStatus"] == "ACCEPTED"

def test_correlate_event_to_multiple_instances(db_session):
    """One event can correlate to multiple waiting instances (broadcast correlation)"""
    # Two instances waiting for same event type with different correlation keys
    inst1 = start_and_wait_for_event(variables={"region": "EU"})
    inst2 = start_and_wait_for_event(variables={"region": "EU"})
    
    correlated = EventCorrelator.correlate(
        event_name="RegionUpdate",
        correlation_keys={"region": "EU"},
        payload={"newRate": 0.15}
    )
    
    assert len(correlated) == 2
    assert set(correlated) == {inst1.instance_id, inst2.instance_id}
```

### 6. counterparty-mock Integration Tests (`tests/processes/integration/test_mikadiv_submission.py`)

**End-to-end test of MiKaDiv-FM submission process against counterparty-mock**:
```python
def test_successful_submission_flow_end_to_end(db_session, counterparty_mock_api):
    """Happy path: Submit → Validate → Acknowledge → Decision = Accepted"""
    # Start MiKaDiv-FM submission process
    instance = ProcessEngine.start_instance(
        "MiKaDivFMSubmission",
        variables={"mikadivXml": load_test_xml("valid_submission.xml")}
    )
    
    # Pre-validation (automated ServiceTask) passes
    execute_until_suspension(instance.instance_id)
    assert instance.variables["preValidationPassed"] == True
    
    # Submit to counterparty-mock KaFE (ServiceTask)
    tokens = reload_tokens(instance.instance_id)
    assert tokens[0].current_element_id == "Task_SubmitToKaFE"
    ProcessEngine.execute_step(instance.instance_id, tokens[0].token_id)
    
    # Verify submission reached counterparty-mock
    submissions = counterparty_mock_api.get_submissions()
    assert len(submissions) == 1
    assert submissions[0]["status"] == "SUBMITTED"
    
    # Simulate KaFE acknowledgement (external event)
    EventCorrelator.correlate(
        event_name="KaFEAcknowledgement",
        correlation_keys={"submissionId": instance.variables["submissionId"]},
        payload={"status": "ACCEPTED", "ackId": "ACK123"}
    )
    
    # Process resumes, waits for final decision
    instance = reload_instance(instance.instance_id)
    assert instance.state == ProcessState.SUSPENDED
    
    # Simulate KaFE decision (external event)
    EventCorrelator.correlate(
        event_name="KaFEDecision",
        correlation_keys={"submissionId": instance.variables["submissionId"]},
        payload={"decision": "APPROVED", "decisionId": "DEC456"}
    )
    
    # Process completes successfully
    instance = reload_instance(instance.instance_id)
    assert instance.state == ProcessState.COMPLETED
    assert instance.variables["finalDecision"] == "APPROVED"

def test_rejection_with_corrections_loop(db_session, counterparty_mock_api):
    """Rejection path: Submit → NACK → User corrects → Resubmit → Acknowledge → Decision"""
    instance = start_submission_process("invalid_submission.xml")
    
    # Submit to KaFE
    execute_until_suspension(instance.instance_id)
    
    # KaFE rejects with validation errors
    EventCorrelator.correlate(
        event_name="KaFEAcknowledgement",
        correlation_keys={"submissionId": instance.variables["submissionId"]},
        payload={"status": "REJECTED", "errors": ["Missing BeneficialOwner"]}
    )
    
    # Process routes to UserTask for corrections
    instance = reload_instance(instance.instance_id)
    assert instance.state == ProcessState.SUSPENDED
    user_tasks = UserTaskManager.get_pending_tasks()
    assert len(user_tasks) == 1
    assert user_tasks[0].task_definition_id == "Task_ProvideCorrections"
    
    # User completes corrections via shape-driven form
    UserTaskManager.complete_task(
        user_tasks[0].task_id,
        form_data={"correctedXml": load_test_xml("corrected_submission.xml")}
    )
    
    # Process loops back to resubmit
    tokens = reload_tokens(instance.instance_id)
    assert tokens[0].current_element_id == "Task_SubmitToKaFE"
    
    # Resubmission succeeds
    execute_until_suspension(instance.instance_id)
    EventCorrelator.correlate(
        event_name="KaFEAcknowledgement",
        correlation_keys={"submissionId": instance.variables["submissionId"]},
        payload={"status": "ACCEPTED"}
    )
    EventCorrelator.correlate(
        event_name="KaFEDecision",
        correlation_keys={"submissionId": instance.variables["submissionId"]},
        payload={"decision": "APPROVED"}
    )
    
    # Process completes after correction loop
    assert reload_instance(instance.instance_id).state == ProcessState.COMPLETED
```

### 7. State Persistence & Recovery Tests (`tests/processes/engine/test_state_recovery.py`)

**Test crash recovery via state persistence**:
```python
def test_resume_after_crash_mid_execution(db_session):
    """Process can resume from persisted state after engine restart"""
    instance = start_process("multi_step_flow.bpmn")
    execute_steps(instance.instance_id, count=3)
    
    # Simulate crash: flush session, clear all in-memory state
    db_session.commit()
    ProcessEngine.shutdown()
    ProcessEngine.restart()
    
    # Reload instance from database, continue execution
    instance = ProcessInstance.query.get(instance.instance_id)
    tokens = ExecutionToken.query.filter_by(instance_id=instance.instance_id).all()
    assert len(tokens) == 1
    
    # Continue execution from where it left off
    ProcessEngine.execute_step(instance.instance_id, tokens[0].token_id)
    # Verify process state advanced correctly
    assert reload_tokens(instance.instance_id)[0].current_element_id == "expectedNextElement"
```

### 8. Shape-driven Form Rendering Integration (`webapp/frontend/src/components/ProcessTaskForm.test.tsx`)

**Test Task 3 integration for user task forms**:
```typescript
describe('ProcessTaskForm', () => {
  it('renders user task form from SHACL shape', async () => {
    const task = {
      taskId: 'task123',
      formShapeId: 'urn:openfaster:shapes:ValidationErrorCorrection',
      taskName: 'Fix Validation Errors'
    };
    
    render(<ProcessTaskForm task={task} />);
    
    // Verify shape renderer called with correct shape ID
    expect(screen.getByText('Fix Validation Errors')).toBeInTheDocument();
    
    // Form fields rendered from shape (Task 3's shape renderer)
    expect(screen.getByLabelText('Error Code')).toBeInTheDocument();
    expect(screen.getByLabelText('Correction')).toBeInTheDocument();
  });
  
  it('validates form submission against SHACL shape', async () => {
    const task = createTestTask();
    const { user } = render(<ProcessTaskForm task={task} />);
    
    // Submit invalid data
    await user.type(screen.getByLabelText('Correction'), 'short');  // Violates min length
    await user.click(screen.getByText('Complete Task'));
    
    // Validation error shown (from shape constraints)
    expect(await screen.findByText(/must be at least 10 characters/)).toBeInTheDocument();
  });
  
  it('completes task and resumes process on valid submission', async () => {
    const task = createTestTask();
    const { user } = render(<ProcessTaskForm task={task} />);
    
    await user.type(screen.getByLabelText('Correction'), 'This is a valid correction');
    await user.click(screen.getByText('Complete Task'));
    
    // API call to complete task
    await waitFor(() => {
      expect(mockApi.completeTask).toHaveBeenCalledWith('task123', {
        correction: 'This is a valid correction'
      });
    });
    
    // UI shows task completed
    expect(screen.getByText('Task completed successfully')).toBeInTheDocument();
  });
});
```

### 9. Manual Acceptance Testing

**Prerequisites**:
- [ ] counterparty-mock running at `http://cloud-admin-box.admin-toolbox.svc.cluster.local:8085/`
- [ ] Process engine deployed with `mikadiv-fm-submission.bpmn`
- [ ] Frontend integrated with ProcessTaskForm component

**Test Scenario 1: Happy Path Submission**:
1. Start new MiKaDiv-FM submission process via API or UI
2. Upload valid MiKaDiv-VIB XML
3. Verify pre-validation passes automatically (no user task)
4. Verify submission appears in counterparty-mock's `/submissions` page
5. Manually advance counterparty-mock's submission to "Acknowledged" state
6. Verify process engine receives acknowledgement event and advances
7. Manually advance to "Decision: Approved" in counterparty-mock
8. Verify process engine receives decision event and completes
9. Check process instance state = COMPLETED, final variables contain decision

**Test Scenario 2: Rejection & Correction Loop**:
1. Start process with intentionally invalid XML (missing required field)
2. Verify pre-validation catches error → UserTask created
3. Open user task in frontend → shape-driven form renders with error details
4. Provide correction via form (add missing field)
5. Submit form → verify process resumes and resubmits to counterparty-mock
6. Verify corrected submission appears in counterparty-mock
7. Approve corrected submission in counterparty-mock
8. Verify process completes successfully

**Test Scenario 3: Multi-Instance Parallel Execution** (if implemented):
1. Start 5 submission processes concurrently
2. Verify all 5 execute independently (no cross-instance interference)
3. Correlate events to correct instances via submission IDs
4. Verify each completes with its own distinct variables

### 10. Performance & Scalability Tests

**Load test**:
- Start 100 concurrent process instances
- Verify: execution throughput, database query performance, event correlation latency
- Acceptance: 95th percentile task execution <500ms, event correlation <200ms

**Long-running process test**:
- Start process that waits 24h for external event (simulated via clock advance)
- Verify: instance state persisted, no memory leaks, event subscription survives restarts

### 11. Definition of Done

- [ ] All unit tests pass (parser, executor, user tasks, events)
- [ ] All integration tests pass (counterparty-mock end-to-end)
- [ ] Manual acceptance tests completed for both happy path and correction loop
- [ ] counterparty-mock's 6-stage pipeline fully modeled as BPMN and executable
- [ ] User task forms render via Task 3's shape renderer, validated against Task 1's shapes
- [ ] Documentation: architecture decision record, BPMN modeling guide, API reference
- [ ] Code review approved by stakeholder
- [ ] Deployed to staging environment, smoke tests pass
