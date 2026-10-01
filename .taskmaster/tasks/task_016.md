# Task ID: 16

**Title:** Write client: commit a re-citation via GitHub's Content API

**Status:** done

**Dependencies:** 15 ✓, 6 ✓

**Priority:** medium

**Description:** A framework-agnostic module that takes a pending edit (task 15's output shape) and a scoped GitHub token (task 6's login primitive) and commits the resulting Turtle change via GitHub's real Content API -- the mechanism that finally spends the token task 6 has produced since it shipped.

**Details:**

## What actually shipped (2026-10-01)

The real implementation lives entirely in the separate `OpenFASTER-Standard/ui` repo (`/work/ui`, new package `packages/write-client`), plus a one-line fix in the separate `OpenFASTER-Standard/workspace-auth` repo -- `generator`'s own `scripts/validate-tasks` can only verify commit ancestry within this repository, so this task's `evidence.commits` points to the task-master rescoping commit made here (the only generator-repo commit substantively about this task -- the same one that split the original task 13 into 13/15/16/17/18), not the implementation itself. The real commits, in `ui`, in order:

- `e2e626d` -- `computeContentHash`: real inclusive XML C14N (W3C REC-xml-c14n-20010315) + SHA-256, matching `annotation_model.selectors.xpath.canonicalize_and_hash_xml` exactly. Live-verified during research that no existing npm library produces this byte-for-byte (`xml-c14n` only implements exclusive C14N; `xml-crypto`'s `C14nCanonicalization` doesn't render ancestor-only namespaces for a detached subtree) -- a small, from-scratch implementation instead.
- `fa60425` -- `upsertCitation`: a Turtle upsert against `n3`, mirroring `clear_property_shape`'s own annotation/target/selector removal and `_annotate`'s own IRI-minting scheme.
- `b10fe2e` -- `fetchFile`/`putFile`: the GitHub Content API client (`GET`/`PUT` against `/repos/{owner}/{repo}/contents/{path}`, confirmed live via `gh api`).
- `cbf832e` -- `commitReCitation`: the orchestrator, re-resolving a pending edit fresh against its live source (never trusting a cached preview value) before committing, plus `parsePropertyShapeIri` -- a glue function this task's own plan added since task 15's real, already-shipped pending-edit shape carries one combined `propertyShapeIri` string, not separate `standard`/`shapeName`/`propertyName` fields.
- `0957064`..`ecd2ae6` -- final-review fix pass: 5 Critical, 6 Important, 11 Minor, all fixed in the same pass per this project's standing rule. Two Criticals were real, confirmed data-corruption bugs, not just wrong hashes: `upsertCitation` was mirroring `clear_property_shape`'s own blanket triple removal literally, which silently destroyed `sh:name`/`sh:order`/`dash:editor` display hints `annotation_model.hints.annotate_display_hint` asserts on the same subject -- generator's own full regeneration pipeline gets away with that blanket removal only because it always re-runs `annotate_display_hint` immediately after `annotate_xpath` in the same pass, which this write client never does; and `fetchFile`'s `atob` call never UTF-8-decoded, mojibaking every non-ASCII character in a fetched shape file (this corpus is German tax reporting, so this hit routinely). A third Critical found the C14N implementation sorted attributes in document order instead of C14N's required (namespace URI, local name) order -- confirmed against 136 of 330 real multi-attribute corpus elements, each of which would have shown permanent spurious drift the instant it was committed; independently re-verified the fix against all 1707 real elements across all 13 corpus XSDs with zero mismatches against `lxml` ground truth. See that repo's own commit messages and `.changeset/write-client-initial-release.md` for the full list.
- `workspace-auth`'s own `d4eb23a` -- one-line fix exposing `window._workspaceRepo` alongside the existing `window._workspaceAuthToken`, since `commitReCitation` needs to know which repo to commit to and the roster payload's own `workspace_repo` field was being decrypted and validated but never stored anywhere.

## Known open question for task 17

`commitReCitation` assumes the shape file path (`shapes/<slug(standard)>/<slug(shapeName)>.ttl`, mirroring `TargetStore._shape_path`) is relative to the GitHub repo root. `TargetStore` is not yet invoked anywhere in this repo's own production code, and the real `OpenFASTER-Standard/ontologies` repo has no `shapes/` directory yet at any level -- there is no existing real deployment to confirm this assumption against either way. Confirm (or add a path prefix) when task 17 actually wires a real repo up.

---

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
