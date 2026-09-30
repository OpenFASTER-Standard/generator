# Task ID: 13

**Title:** Write client and annotation-editing UI

**Status:** pending

**Dependencies:** 3 ✓, 6 ✓

**Priority:** medium

**Description:** Spend the GitHub token task 6's admin-login primitive hands out: a client that actually commits an edit via GitHub's Content API, wired to task 3's shape-driven form generation -- the piece that turns "an admin can log in" into "an admin can actually edit an annotation," the literal Wikipedia-editing half of the collaborative platform.

**Details:**

## Why this is the most urgent remaining piece

Task 6 (done) proved an admin can authenticate to a workspace with zero
server and zero database -- but explicitly, by its own stated Non-Goals,
spends no part of the resulting token: "This task proves an admin can
obtain a valid, scoped GitHub token client-side. It does not spend that
token on any GitHub API call." Nothing built so far lets anyone actually
write an annotation through the collaborative platform this whole
project is building toward -- "I want it to become very similar to how
Wikipedia works," and Wikipedia's entire value is that people can edit
it. Until this exists, every other piece (login, shape-driven forms,
visibility scopes) is real but inert.

## Real building blocks already proven

- Task 6's login primitive hands out a real, scoped GitHub token in
  browser memory on successful authentication.
- GitHub's Content API genuinely supports CORS for direct browser calls
  (`PUT /repos/{owner}/{repo}/contents/{path}`, verified live during task
  6's own research) -- no backend proxy needed.
- Task 3's shape-driven UI generation already renders a form from a real
  SHACL property shape; this task's job is wiring that form's submission
  to a real commit via the Content API, using the token task 6 already
  provides.

## Scope

Brainstorm from scratch: how a rendered task-3 form's submitted values
become a real Turtle/RDF update to the target workspace's own git
repository via the Content API, using the exact token-handoff task 6
already built and tested. Real end-to-end proof: an admin logs in via the
live `workspace-auth` page, edits a real annotation through a real
shape-driven form, and the resulting commit is verifiable in the target
repository's own git history -- the literal "someone edited a Wikipedia
page" moment for this platform.

**Test Strategy:**

Defined during this task's own brainstorm/spec, per this project's established per-task cycle -- not prescribed here.
