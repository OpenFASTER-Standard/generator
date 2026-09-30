# Stateful Process Layer — Design

## Summary

Fills a real, currently-unfilled gap in this project's own review cycle:
today, `review_workflow.submit_review()`'s `REJECTED` verdict leaves a
flagged item sitting in the review summary forever, with no formal
record that "a correction is now owed" — a human has to notice it's
still flagged and separately remember to fix it via `citation_workflow.
add_citation()`. This spec introduces a small, real BPMN 2.0 process
(`CitationCorrection`), executed by SpiffWorkflow (a real, pure-Python,
one-dependency library — verified live, not guessed), that tracks
exactly that gap as genuine, resumable process state: created the
moment a verdict is `REJECTED`, paused at "owed a correction," and
completed the moment that correction is actually provided — proven to
survive a real process restart, not just an in-memory object.

This is the direct fix for why this needs to be a separate "stateful
process layer" at all, distinct from the pure, request-scoped
declarative transformation layer (roadmap task 2): a `Transformation` is
a pure function of "whatever graph you hand it, right now." A process
instance is not — it has to still be "owed a correction" three days
later, after the process that started it has long since exited.

## Context

Depends on roadmap tasks 1-3 (all done, merged). Per this project's
standing rule, nothing here treats existing code as untouchable, but
nothing here needs to change any of tasks 1-3's code — this is additive,
wiring into two existing call sites.

**What already exists that this design builds on, verified live, not
assumed:**

- **The real gap this fills, confirmed by reading the real code, not
  assumed from the task description.** `review_consultation/consult.py`'s
  `apply_reviews()` keeps a flagged item in the summary forever once
  `REJECTED` (`kept = ...`, line 103) — there is no
  code path anywhere that turns a rejection into an explicit,
  trackable task. `review_workflow/orchestrate.py`'s `submit_review()`
  (61 lines total) is a stateless, single-call batch pipeline: it
  records the verdict and returns: no persisted execution position, no
  "this specific thing is still pending" concept.
- **task_005.md's own auto-elaboration is not this design's scope.**
  It proposes a fictional bank-submits-a-filing-to-a-regulator process
  (a `mikadiv-fm-submission.bpmn`, a `counterparty_mock_connector.py`
  reaching into a different repo's mock service, a 5-table Postgres
  schema, a REST API, BPMN.io visual monitoring) that has no connection
  to any real business process this project's real code implements
  today. This design instead formalizes the real gap named above —
  matching the same "ground the first proof in what's actually real"
  discipline already used for roadmap tasks 3 and 4.
- **`@openfaster-standard/shapes` (task 3) cannot be reused for process
  task forms**, despite task_005.md's claim. Its own design spec states
  directly in its Non-Goals: *"Data-entry (write-back) forms — today's
  shapes are read-only citation records; nothing in this spec produces a
  form that writes back to a `TargetStore`."* `ShapeField.tsx` renders
  every case through one unconditional `<FormControl readOnly ... />`.
  This design needs no UI at all for its first proof (see Non-Goals) —
  a webapp integration is later, separate work, the same pattern already
  used for tasks 3 and 4's own UI/CLI non-goals.
- **SpiffWorkflow 3.2.0 is real, appropriately-sized, and verified live
  end-to-end**, not assumed from its README. Confirmed: one runtime
  dependency (`lxml`, already a `generator` dependency) — unlike
  `sssom-py`'s pandas/linkml chain rejected for roadmap task 4. Unlike
  that rejection, this is not a "don't add a heavy framework for a
  trivial format" situation: correctly implementing BPMN 2.0's token/
  gateway/boundary-event execution semantics from scratch is real,
  easy-to-get-subtly-wrong spec-compliance work, which is exactly the
  kind of logic this project's own practice says to reuse a real
  reference implementation for rather than reinvent.
  **Verified live, this session, against a real minimal BPMN 2.0 XML
  file** (`StartEvent → UserTask "Review flagged drift" →
  ExclusiveGateway (condition on a `verdict` process variable) →
  either EndEvent "Suppressed" or UserTask "Correct the citation" →
  EndEvent "Correction submitted"`): parsing
  (`SpiffWorkflow.bpmn.parser.BpmnParser`), instantiation and stepping
  (`SpiffWorkflow.bpmn.BpmnWorkflow`, `.do_engine_steps()`), completing a
  user task with real data (`task.set_data(...)`, `task.run()`), and
  — the part that actually matters for "stateful" — real serialization
  to JSON (`SpiffWorkflow.bpmn.serializer.BpmnWorkflowSerializer
  .serialize_json(workflow)`) that a **separate Python process
  invocation**, minutes later, loaded back
  (`.deserialize_json(...)`), found the same paused task still ready,
  completed it, and reached real completion with both tasks' data intact
  (`{"verdict": "rejected", "corrected_fact_key": "..."}`). Both the
  `approved` and `rejected` branches were verified to route correctly.
- **No database exists anywhere in `generator`'s own stack**
  (`pyproject.toml` has no DB driver/ORM). The existing convention for
  data that needs to outlive one request is a flat JSON file per entity,
  in the separate `ontologies` corpus repo, not `generator`'s own git
  history (`DEFAULT_CATALOG_PATH`/`DEFAULT_REVIEWS_DIR` in
  `webapp/app.py` both point at
  `/work/ontologies/mikadiv-fm/...`, read via a call-time
  `os.environ.get(...)`-based override, never import-time). This design
  follows that exact convention rather than introducing Postgres.

## Core Concepts

### `process_workflow/citation_correction.bpmn` (new, real, committed)

The real BPMN 2.0 XML verified live above, committed as-is (five nodes:
one start event, two user tasks, one exclusive gateway, two end events).
Process id `CitationCorrection`. The gateway's two `sequenceFlow`
conditions are real Python boolean expressions over a `verdict` process
variable (`verdict == "approved"` / `verdict == "rejected"`), evaluated
by SpiffWorkflow's own default script engine — no custom scripting
engine needed for this scope.

### `process_workflow/engine.py` (new)

Thin wrapper around the verified SpiffWorkflow calls — no new execution
logic invented, only real generator-domain naming on top of real
library calls:

- `start_citation_correction(*, verdict: str) -> BpmnWorkflow` — parses
  the committed BPMN file (once; the parsed `BpmnProcessSpec` is cheap to
  reuse across instances), creates a `BpmnWorkflow`, immediately
  completes the "Review flagged drift" task with the given `verdict`
  (this integration never pauses there — the real verdict was already
  collected by the existing `submit_review()` call that triggers this;
  representing that step in the diagram is for clarity, not to
  duplicate a UI that already exists), and runs engine steps. Returns
  the resulting workflow, which is either already `is_completed()`
  (the `approved` branch) or paused at "Correct the citation" (the
  `rejected` branch).
- `complete_correction(workflow: BpmnWorkflow, *, corrected_fact_key: str) -> None`
  — completes the one ready user task with the given data and runs
  engine steps to finish the process.
- `serialize(workflow) -> str` / `deserialize(blob: str) -> BpmnWorkflow`
  — thin wrappers around `BpmnWorkflowSerializer`, verified live to
  round-trip correctly across a real separate process invocation.

### `process_workflow/store.py` (new)

Mirrors `webapp/app.py`'s `_corpus_root()`/`_catalog_path()` convention
exactly: `DEFAULT_PROCESS_INSTANCES_DIR =
"/work/ontologies/mikadiv-fm/process_instances"`,
`process_instances_dir()` reads `MIKADIV_PROCESS_INSTANCES_DIR` at call
time. One JSON file per *pending* instance, named by the same identity
tuple `review_consultation.consult`'s `apply_reviews()` already uses to
match a review to a flagged leaf — `(fact_key, leaf_reference_id,
drift_kind, fingerprint)` — so this design invents no new identity
scheme. `save_instance(identity, workflow)`,
`load_instance(identity) -> BpmnWorkflow | None`,
`delete_instance(identity)` (called once a correction completes the
process — a finished instance has nothing left to resume).

### Wiring: one real call site extended, one new explicit function — not two silent hooks

Checked against the real webapp request shapes before designing this,
not assumed: `SubmitReviewRequest` (`webapp/app.py`) carries
`leaf_reference_id` (the server looks up the full `FlaggedLeaf`,
including its `drift_kind`/`fingerprint`, from that), so `submit_review()`
has everything needed to start a correctly-identified process instance.
`AddCitationRequest` carries none of that — only `family`, `xpath`,
`fact_key`, `author`, `comment`, `is_correction` — because today's
webapp has no flow that links "correct this specific flagged leaf" to
the citation form at all (that link is exactly the webapp integration
this spec defers as a Non-Goal). Silently having `add_citation()` guess
at a matching pending instance from `fact_key` alone would be wrong the
moment a `fact_key` has more than one independently-flagged leaf, which
`review_consultation`'s own matching logic already accounts for as a
real case (two leaves can share a fingerprint under one fact_key).

So only one of the two integration points is a modification to existing
code; the other is a new function for a future, fully-informed caller
to use explicitly:

- `review_workflow.orchestrate.submit_review()` **is extended**: when
  `verdict == Verdict.REJECTED`, after recording the review as it
  already does, also calls `start_citation_correction(verdict="rejected")`
  and `store.save_instance(identity, workflow)`, where `identity` is
  built from the same `(fact_key, flagged.leaf.reference_id,
  flagged.drift_kind, flagged.fingerprint)` tuple `record_review()`
  already writes into the review JSON document. When `verdict ==
  Verdict.APPROVED`, the same call is made but completes immediately,
  so nothing is persisted — no behavior visible to an `APPROVED` caller
  changes.
- `citation_workflow.add_citation()` **is not modified.** It has no
  identity to look anything up by, and inventing one (e.g. widening its
  request shape) is exactly the webapp-flow work this spec defers.
  Instead, `process_workflow` exposes
  `complete_pending_correction(identity, *, corrected_fact_key: str) ->
  bool` (returns whether a pending instance was actually found and
  completed) as a public function for whichever caller already has the
  full identity in hand to invoke *after* a successful `add_citation()`
  call. This session's own end-to-end test is exactly such a caller —
  it has the full identity because it is the one that created the
  correction in the first place. A future webapp flow that lets a human
  go straight from "this flagged item" to "here's my fix" would call it
  the same way, once that flow exists (Non-Goal here, not blocked by
  this design).

## Data Flow

1. A reviewer submits a `REJECTED` verdict via the existing
   `submit_review()` call, which already has the full identity
   (`fact_key`, `flagged.leaf.reference_id`, `flagged.drift_kind`,
   `flagged.fingerprint`) from its own `FlaggedLeaf` parameter.
2. A `CitationCorrection` process instance starts, immediately advances
   past its own "review" step (the verdict is already known), and pauses
   at "Correct the citation." It is persisted to a real file, keyed by
   that identity.
3. Time passes — possibly a different process, possibly a different
   human, possibly days later.
4. A correction is submitted via the existing `add_citation(...,
   is_correction=True)` call, unmodified — it knows nothing about
   pending process instances.
5. Whichever caller made that correction *and already has the same
   identity in hand* (this spec's own end-to-end test; later, a webapp
   flow not built here) calls
   `complete_pending_correction(identity, corrected_fact_key=...)`. The
   pending instance is loaded from disk (a genuinely separate process
   load, not a reused in-memory object), completed, and its file is
   deleted — the process instance's own life cycle is now over; the
   correction itself lives on as a catalog revision, exactly as it
   already did before this design.

## Error Handling

- A `store.load_instance()` call for an identity with no persisted file
  returns `None`, not an exception — matching Data Flow step 5's "not
  every correction originates from this process" case above.
- A persisted instance file that fails to deserialize (corrupted,
  truncated) raises a clear, named error identifying the file — never a
  bare SpiffWorkflow/JSON internal exception (mirroring this project's
  established `ReviewLoadError`/`SssomParseError` precedent).
- `complete_correction()` on a workflow with no ready user task (e.g.
  the identity matched a file that was already `is_completed()` somehow)
  raises a clear, named error rather than silently no-op'ing.

## Testing Strategy

- **Real BPMN, real SpiffWorkflow, no mocked engine**: every test in
  this task drives the actual committed `.bpmn` file through the actual
  library, matching this project's established "real data, not
  synthetic fixtures" discipline.
- **Both gateway branches**: an `approved` verdict completes
  immediately with nothing persisted; a `rejected` verdict pauses and
  persists.
- **Genuine cross-process resumability, not an in-memory illusion**:
  the defining test of this whole layer runs `complete_correction`
  against a workflow object loaded fresh from a file written by a
  *separate* Python process invocation (a subprocess, or two
  independent test functions sharing only the file on disk) — proving
  real persistence, the same way this was verified live during
  brainstorming, not just that one Python object's state survived a
  round-trip in the same process.
- **The real wiring, exercised through the real existing functions**:
  `submit_review(..., verdict=REJECTED)` leaves a real instance file on
  disk, keyed by the real identity from its `FlaggedLeaf`; a real
  `add_citation(..., is_correction=True)` call followed by
  `complete_pending_correction(identity, ...)` for that same identity
  loads and completes it, then deletes the file; a `submit_review(...,
  verdict=APPROVED)` call leaves nothing on disk;
  `complete_pending_correction()` for an identity with no matching file
  returns `False` rather than raising (the "not every correction
  originates from this process" case).
- **A corrupted instance file** raises the named error, not a bare
  library exception.

## Non-Goals

- **A webapp UI for viewing/claiming/completing process tasks.** Nobody
  has asked for one yet; this spec proves the mechanism with real
  wiring into existing function calls, not an authoring/monitoring
  workflow — same pattern as tasks 3 and 4's own UI non-goals.
- **BPMN.io or any visual process editor/monitor.**
- **Timers, boundary events, multi-instance markers, message
  correlation between separate process instances, or DMN.** SpiffWorkflow
  supports all of these; this proof needs none of them. Adding one is a
  small, additive change to the committed `.bpmn` file and
  `engine.py`'s dispatch, not a redesign.
- **A second BPMN process type** (e.g. task_005.md's invented
  regulatory-submission process). Nothing in this codebase implements
  filing submission to a counterparty today; inventing that capability
  is separate, much larger work, unrelated to formalizing this real
  review-correction gap.
- **A database.** Flat, per-instance JSON files in the same
  `ontologies`-repo location convention `references.json`/`reviews_dir`
  already use.
- **Abandoned-instance cleanup/expiry policy.** A `REJECTED` review
  that's never corrected leaves its instance file sitting on disk
  indefinitely today (no worse than the status quo, where it just sits
  flagged forever) — a garbage-collection policy is a real future
  question, not this proof's job.

## Open Questions

- Whether `store`'s one-file-per-instance approach remains adequate once
  the number of simultaneously-pending corrections grows large (a
  directory listing / lookup-by-identity performance question) — not a
  concern at today's real corpus scale, deferred until it is.
- Whether a second, genuinely different BPMN process (once one exists)
  should share `process_workflow/`'s `engine.py`/`store.py` or get its
  own — deferred until a second real process exists to learn from.
