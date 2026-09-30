# Task ID: 16

**Title:** Write client: commit a re-citation via GitHub's Content API

**Status:** pending

**Dependencies:** 15, 6 ✓

**Priority:** medium

**Description:** A framework-agnostic module that takes a pending edit (task 15's output shape) and a scoped GitHub token (task 6's login primitive) and commits the resulting Turtle change via GitHub's real Content API -- the mechanism that finally spends the token task 6 has produced since it shipped.

**Details:**

## Why this exists as its own task

Task 6's own stated Non-Goal, verbatim: "This task proves an admin can
obtain a valid, scoped GitHub token client-side. It does not spend that
token on any GitHub API call." Nothing in the roadmap has closed this
until now.

## Real, already-verified building blocks

- GitHub's Content API supports CORS for direct browser calls
  (`PUT /repos/{owner}/{repo}/contents/{path}`, base64-encoded content,
  verified live during task 6's own research) -- no backend proxy needed.
- `annotation_model.rdf`'s real `annotate_xpath`/`annotate_svg` functions
  (task 1) define the exact Turtle shape a re-citation must produce --
  this task's job is producing an equivalent update client-side (in
  TypeScript, since there is no server to run Python), not inventing a
  new format.
- Task 6's login page already holds a real, live, scoped
  (`contents:write`, single-repo) token in `window._workspaceAuthToken`.

## Scope

Pure mechanism, no UI of its own -- consumes task 15's pending-edit shape
and task 6's token, produces a real commit. Needs the existing blob's SHA
for an update (GitHub Content API requirement) and the upsert semantics
task 1's own `clear_property_shape`/`write_shape` already established
(clear the old property shape's triples before adding the new ones) --
reimplemented here in TypeScript against the same Turtle target, not
assumed identical without verification.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
