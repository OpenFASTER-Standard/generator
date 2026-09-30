# Task ID: 5

**Title:** Design and implement stateful process layer (BPMN 2.0-based workflow engine)

**Status:** cancelled

**Dependencies:** 1 ✓, 2 ✓, 3 ✓

**Priority:** low

**Description:** Formalize a real gap in this project's own review cycle -- a REJECTED review verdict left a flagged item sitting unresolved forever, with no trackable 'a correction is owed' state -- using a small, real BPMN 2.0 process (SpiffWorkflow, a real pure-Python engine) that starts on rejection, persists as a real resumable file, and completes when the correction is actually provided. Proven to survive a real process restart via a genuinely separate subprocess, not just an in-memory object.

**Details:**

## Reversion note (2026-09-30)

This task's real implementation (`process_workflow/`, wired into
`review_workflow.orchestrate.submit_review()`) was removed in its
entirety as part of a deliberate cleanup of an entire parallel,
never-unified citation stack (`reference_model`, `references_catalog`,
`review_recording`, `review_consultation`, `review_surfacing`,
`review_workflow`, `citation_workflow`, `staleness_sweep`, `discovery`,
`generator_errors`, `webapp`) that predated `annotation_model` (task 1)
and had already been marked "dead code pending a follow-up migration
plan" in this repo's own README before that migration ever happened.

`process_workflow`'s own code was real, tested, and correct at the time
it shipped (see its final review, 0 Critical/6 Important/11 Minor
findings, all fixed) -- but its *only* production integration point was
`submit_review()`, itself part of the removed stack. Once that stack was
gone, `process_workflow` had no caller anywhere in this codebase, so it
was removed alongside it rather than left as tested-but-permanently-
disconnected code.

Status changed from `done` to `cancelled` rather than `pending`: the
real work happened, was verified, and is preserved in git history (see
`evidence.commits` below) -- `pending` would erase that; `cancelled`
records that a real, complete implementation was later superseded by an
architectural decision, not that it was never attempted. If BPMN-based
process tracking is wanted again in the future, it needs to be
redesigned against whatever stack (`annotation_model`, or a future
successor) is live at that time -- this task's own design (a
`CitationCorrection` process reacting to a rejected review verdict) was
specific to the removed stack's own review-verdict concept, which has
no direct equivalent in `annotation_model` today.

---

## Reconciliation note (2026-09-30)

This task's `description`/`details`/`testStrategy` originally came from
task-master's own AI auto-elaboration at task-creation time, before the
real design spec existed -- the same situation tasks 3 and 4 were in
before their own reconciliation (see those tasks' own Reconciliation
notes). The auto-elaboration proposed a much larger and differently-shaped
project than what the approved spec scoped and what was actually built: a
full hand-rolled BPMN 2.0 XML dialect and Petri-net token executor, a
5-table Postgres schema (`process_definitions`/`process_instances`/
`execution_tokens`/`user_task_instances`/`event_subscriptions` with
JSONB/GIN indexes), a REST API (`/api/processes/deploy`, `/api/tasks`,
`/api/events/correlate`), a fictional `mikadiv-fm-submission.bpmn`
process modeling a bank submitting a filing to a regulator, a
`counterparty_mock_connector.py` reaching into a completely different
repo's mock service, load/performance tests ("100 concurrent instances,"
a 24-hour wait test), and BPMN.io visual monitoring.

None of that was built, and per this project's own final-review process
this would give a future reader a materially false picture of what
exists. The section below replaces it with what the approved spec
(`docs/specs/2026-09-30-stateful-process-layer-design.md`) actually
scoped and what was actually shipped.

## What this task actually built

One repository (`generator`), one new top-level package
(`process_workflow/`), one real committed BPMN diagram, wired into one
real existing function.

### The key scoping decision: formalize a real gap, not an invented process

Task 5's own auto-elaboration invented a fictional regulatory-submission
business process that has no connection to any real code this project
implements -- the real system is about citing sources and reviewing
drift, not submitting filings to a counterparty. Reading the real code
(`review_consultation/consult.py`'s `apply_reviews()`) found the actual
gap worth formalizing: a `REJECTED` verdict keeps a flagged item in the
review summary forever, with no code path that turns a rejection into an
explicit, trackable task. This task's one real BPMN process,
`CitationCorrection`, tracks exactly that: `Drift flagged -> Review
flagged drift -> [gateway on verdict] -> Suppressed` (approved) or `->
Correct the citation -> Correction submitted` (rejected).

### `process_workflow/citation_correction.bpmn`

The real, committed BPMN 2.0 diagram, executed by **SpiffWorkflow 3.2.0**
(real PyPI package, verified live: exactly one runtime dependency,
`lxml`, already a `generator` dependency -- chosen over hand-rolling a
Petri-net executor because correctly implementing BPMN's token/gateway
semantics from scratch is real, easy-to-get-wrong spec-compliance work,
the same reasoning this project already applies to reusing real
reference implementations elsewhere).

### `process_workflow/engine.py`

Thin wrapper around real SpiffWorkflow calls:
`start_citation_correction(*, verdict)` parses the committed BPMN file
once at import time, advances a fresh workflow past its Start event,
completes the (already-decided) review step with the given verdict, and
returns the resulting workflow -- either already complete (`approved`)
or paused at `CorrectCitation` (`rejected`). `complete_correction()`
completes that one paused task. `serialize`/`deserialize` wrap
SpiffWorkflow's own real `BpmnWorkflowSerializer`. `NoReadyCorrectionTaskError`/
`InvalidVerdictError` (both deriving from this project's own
`GeneratorError`, at 500 and 400 respectively) replace what would
otherwise be bare library exceptions for "wrong number of ready tasks"
and "a verdict the gateway has no branch for".

### `process_workflow/store.py`

Real per-instance persistence: one JSON file per *pending* instance
(never for an `approved` verdict, which completes immediately), under
`/work/ontologies/mikadiv-fm/process_instances/` -- matching
`webapp/app.py`'s own `DEFAULT_CATALOG_PATH`/`DEFAULT_REVIEWS_DIR`
convention exactly, including call-time env-var overrides
(`MIKADIV_PROCESS_INSTANCES_DIR`) and an explicit per-call
`instances_dir` parameter for callers that already have their own path
in hand. Each file records its own `CorrectionIdentity`
(`fact_key`/`leaf_reference_id`/`drift_kind`/`fingerprint`, the same
identity `review_consultation.consult` already uses to match a review to
a flagged leaf) alongside the serialized workflow, verified against the
requested identity on load, and is written atomically (matching
`references_catalog/catalog.py`'s own established tmp-write +
`os.replace` pattern). Filenames are a hash of each field hashed
independently first, then concatenated and re-hashed -- a real
collision in the simpler "join fields, then hash" approach was found and
fixed live during implementation (a `fact_key` containing the join
separator can make two different identities join to the identical
string).

### `process_workflow/orchestration.py` + wiring

`start_pending_correction`/`complete_pending_correction` compose engine
+ store into the two operations a caller needs. `review_workflow.
orchestrate.submit_review()` is the one real function extended: on a
`REJECTED` verdict, it now also starts a pending correction, using the
identity already available from its own `FlaggedLeaf` parameter.
`citation_workflow.add_citation()` is deliberately **not** modified --
checked against the real webapp `AddCitationRequest` shape before
deciding this: it carries no leaf/drift/fingerprint identity to look
anything up by, and inventing one would mean widening a request shape
for a webapp flow ("correct this specific flagged leaf") that doesn't
exist yet. `complete_pending_correction()` is a public function for
whichever future caller has the full identity in hand.

### The end-to-end proof

`tests/process_workflow/test_end_to_end.py`: a real flagged citation is
rejected (persisting a real instance file), a real correction is made via
the existing `add_citation()`, and then a **genuinely separate
subprocess** (`subprocess.run([sys.executable, ...])`, not a second
in-memory object) loads the persisted file and completes the correction
-- proving real cross-process resumability, the actual point of this
being a "stateful process layer" distinct from the pure, request-scoped
declarative transformation layer (roadmap task 2).

## Non-Goals (unchanged from the approved spec, still true of what shipped)

- A webapp UI for viewing/claiming/completing process tasks, or a
  BPMN.io visual monitor -- nobody has asked for either yet.
- Timers, boundary events, multi-instance markers, message correlation,
  or DMN -- SpiffWorkflow supports all of these; this proof needs none.
- A second BPMN process type (e.g. task_005.md's invented
  regulatory-submission process) -- nothing in this codebase implements
  filing submission to a counterparty today.
- A database -- flat, per-instance JSON files, matching this project's
  own existing `references.json`/`reviews/` convention.
- Abandoned-instance cleanup/expiry policy -- a rejected review that's
  never corrected leaves its instance file on disk indefinitely (no
  worse than the pre-existing status quo, where it just sits flagged
  forever).

**Test Strategy:**

## Verification strategy (what was actually run, matching the approved spec's Testing Strategy)

- **Real BPMN, real SpiffWorkflow, no mocked engine**
  (`tests/process_workflow/test_citation_correction_bpmn.py`,
  `test_engine.py`, 11 tests): every test drives the actual committed
  `.bpmn` file through the actual library -- both gateway branches, a
  real serialize/deserialize round-trip, the shared module-level spec's
  genuine isolation across concurrent workflow instances (verified live
  before writing the regression test), an unrecognized verdict raising a
  named `InvalidVerdictError` rather than a bare
  `SpiffWorkflow.exceptions.WorkflowException` (confirmed live before the
  fix), and symmetric ready-task guards on both
  `start_citation_correction`/`complete_correction`.
- **Real per-instance persistence** (`test_store.py`, 14 tests): a real
  saved instance loads back resumable; a never-saved identity returns
  `None`, not an error; a corrupted file raises `CorruptedInstanceError`
  naming the file; a stored-identity mismatch is detected and raises
  (guarding the exact collision class the ledger caught once); an
  interrupted write (mocked `os.replace` failure, matching
  `references_catalog`'s own real test pattern) leaves the original file
  byte-for-byte untouched; two identities differing only in where a `|`
  separator falls never collide on the same filename (verified live: the
  plan's own original scheme *did* collide on this exact pair before the
  fix); an NFC vs. NFD-encoded `fact_key` hashes identically; an explicit
  `instances_dir` override works independently of the env var.
- **Real wiring, exercised through the real existing functions**
  (`test_orchestration.py` + extended `tests/review_workflow/
  test_orchestrate.py`, 13 tests): `submit_review(..., verdict=REJECTED)`
  leaves a real instance file on disk keyed by the real identity from its
  `FlaggedLeaf`; `verdict=APPROVED` leaves nothing on disk;
  `complete_pending_correction()` for a matching identity completes and
  deletes it, for a non-matching identity returns `False`, and for a
  *corrupted* matching file raises rather than returning `False` (the
  distinction this whole layer exists to get right, tested at the exact
  boundary the plan named); `submit_review()`'s pre-existing return
  value/behavior is provably unchanged (every pre-existing test in that
  file still passes untouched); an explicit `instances_dir` threads all
  the way from `submit_review()` down to the file actually written.
- **The actual deliverable, proven end-to-end** (`test_end_to_end.py`, 1
  test): one real rejected review, one real correction via the existing
  `add_citation()`, one real **separate OS subprocess** loading the
  persisted file and completing it -- the assertion that the instances
  directory is empty afterward is checked from the *parent* process,
  proving the *subprocess itself* did the deletion, not a shared
  in-memory reference.
- **Fresh-review verification**: a final whole-branch review (fresh Opus
  reviewer) found 0 Critical, 6 Important, 11 Minor findings, all fixed
  in the same pass per this project's standing rule (never defer
  Minors) -- full suite 386/386 passing after the fix pass (up from 369),
  including a real non-editable wheel build confirmed to actually contain
  the committed `.bpmn` file (a real, verified gap: SpiffWorkflow's spec
  parser is invoked at `engine.py`'s own import time, so a package
  missing that file fails to import at all, not just at runtime).

## Explicitly not run (out of scope, not a gap)

- No webapp UI/BPMN.io verification -- neither exists for this task
  (Non-Goal).
- No timer/boundary-event/multi-instance/DMN test coverage -- none of
  these are used by the one real diagram this task ships (Non-Goal).
- No second BPMN process / no counterparty-submission test -- that
  capability doesn't exist anywhere in this codebase (Non-Goal).
- No database/ORM test coverage -- deliberately not a dependency of this
  task.

## Definition of Done (replaces the original, met in full)

- The real `CitationCorrection` BPMN diagram parses and executes both
  branches correctly via SpiffWorkflow.
- A `REJECTED` review verdict persists a real, resumable process
  instance; an `APPROVED` verdict never touches the filesystem.
- A persisted instance is attributable to its own identity and verified
  on load; writes are atomic; filenames never collide across different
  identities (a real collision was found and fixed).
- New domain errors derive from this project's own `GeneratorError`
  contract, matching its existing 400/500 split.
- `process_workflow`'s public surface is a real, stated module
  (`process_workflow/__init__.py`), not internal-submodule reaching.
- Genuine cross-process resumability is proven via a real separate
  subprocess, not merely an in-memory round-trip.
- Full test suite green (`pytest`, 386/386) confirmed after every
  final-review fix, not just once at task completion.
- README.md's own package-layout section and this task-master record
  itself accurately describe what was built, not task-master's own
  pre-spec auto-elaboration.
