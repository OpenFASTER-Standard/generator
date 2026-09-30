# Workspace Admin Authentication — Design

## Summary

Roadmap task 6 ("collaborative annotation platform with public/private
visibility scopes") started as task-master's own pre-spec auto-elaboration:
a multi-tenant SaaS platform with a SQLite `workspaces`/`workspace_members`
schema, session cookies, and a FastAPI backend -- built almost entirely on
top of the old citation/webapp stack this same effort has just removed
outright (`docs/specs/2026-09-30-...` cleanup commit `45ca560`). None of
that survives contact with the real, current codebase or this project's own
standing rule against treating any prior scaffolding -- task-master's
included -- as an anchor.

This spec narrows task 6 to its genuinely hard, genuinely novel piece, and
nothing else: **proving an admin can authenticate to a specific annotation
workspace with zero server and zero database**, on infrastructure that
costs nothing to run (GitHub Pages) and that a five-to-ten-person trusted
group can operate without any of this project's own code holding a secret
at rest anywhere except as ciphertext. Everything downstream of "prove who
you are" -- an actual write client, an actual editing UI -- is deliberately
out of scope here and left to its own future roadmap tasks (see Non-Goals).

## Context

**The real current system has no server, no users, no sessions, anywhere.**
Confirmed via exhaustive grep before this spec was written: `annotation_model`
and `alignment` (roadmap tasks 1-4, the only stacks left after the old-stack
removal) are libraries. `annotation_model/store.py`'s `TargetStore(path)` is
the only thing resembling a "workspace" boundary today -- an explicit,
required, git-backed target directory, chosen specifically (per its own
docstring) so "a public regulation and a bank's own private process are
indistinguishable to this code." `annotation_model/transform/jinja.py`
already names this exact future need in a comment: "a bank registering its
own private transformation, roadmap task 6."

**Visibility is git-native, not app-level.** A workspace is one real git
repository. Public vs. private is that repository's own GitHub visibility
setting -- a real, already-built, battle-tested mechanism -- not a new
`visibility` column reinvented in this codebase. This was an explicit
scoping decision made during this spec's own brainstorm, not an assumption:
the alternative (a hosted multi-user web service with its own session/role
database) was considered and rejected as reintroducing the server this
project just removed, for a problem GitHub's own repo-visibility model
already solves.

**RDF-native access control (Solid's Web Access Control / WebID) was
considered and rejected.** WAC is real, W3C-adjacent prior art built for
exactly "who can write which RDF resource" -- but it requires a live HTTP
server enforcing `.acl` files per resource, which directly contradicts the
git-native, no-server decision above. Noted here so a future reader doesn't
re-discover and re-litigate it.

**"Admin-only editing, start deliberately narrow" needs a real identity
check, not just an assumption that whoever has `gh` configured locally is
trustworthy.** The first design attempt for this spec proposed exactly that
gap -- provisioning tooling that delegated entirely to GitHub's ambient
session with no check of its own -- and was correctly rejected during
brainstorming as not actually solving authentication at all.

**The real, current, professional pattern for "automation needs to hold a
git-adjacent secret safely" is SOPS+age**, live-verified earlier this
session: `age` (FiloSottile/age, v1.3.2) is the current asymmetric/passphrase
encryption primitive; `getsops/sops` (v3.13.3) is the real tool wrapping it
for structured secrets; the PyPI `sops` package (v1.18) is a dead,
pre-Go-rewrite relic with no age support and must not be used; `pyrage`
(woodruffw/pyrage, v1.4.0) is the real, current, native Python binding to
the Rust `age` reimplementation. Flux CD's own documented practice (live web
research, not memory) confirms SOPS+age is the current real-world standard
for exactly this shape of problem: encrypt a secret with age, commit the
ciphertext to git, only key-holders decrypt.

**2026's current industry consensus has moved past static bot
tokens/deploy keys toward GitHub Apps** (short-lived, installation-scoped
tokens minted on demand) for any *automated, unattended* writer -- live web
research, multiple independent sources. Nothing in this codebase writes
unattended today (confirmed via grep: no cron/CI runner, no bot, no
`__main__`), so building an actual GitHub App is explicitly deferred (see
Non-Goals); the credential-storage mechanism this spec builds is
format-agnostic and will hold whatever credential shape a future automated
writer needs, without redesign.

**The exact cross-implementation and browser-compatibility claims this spec
depends on were verified live, not assumed, during this same session's
brainstorm**: a file passphrase-encrypted with real `pyrage`
(`pyrage.passphrase.encrypt`, Python/Rust) was correctly decrypted by the
real `age-encryption` npm package (`FiloSottile/typage`, v0.3.1 -- age's own
author's TypeScript implementation) both in Node and inside a real headless
Chromium browser (via Playwright, bundled with `esbuild` exactly per that
package's own README instructions). The reverse direction (encrypt in JS,
decrypt in Python) was also verified. A wrong passphrase was confirmed to
fail cleanly (`"no identity matched any of the file's recipients"`) rather
than silently succeeding -- the property this whole design depends on to
use "successful decrypt" as an authentication decision, not just a storage
mechanism. `pyrage.passphrase.encrypt`'s actual output was inspected
directly (not assumed from docs): it is the raw age binary container
(`bytes`, beginning with the literal ASCII header `age-encryption.org/v1`)
-- `pyrage` has no `armor` module of its own (confirmed: `pyrage.armor`
does not exist). The live spike used this raw binary form directly, with
no ASCII-armor step on either side, and it worked end to end -- this spec
follows exactly what was proven, not a wrapped-up embellishment of it.

**A real chicken-and-egg problem was found and designed around before any
code was written**: a *private* workspace's own repo can't be the place its
roster file lives, because reading anything from a private GitHub repo
already requires a token -- the exact thing the roster file exists to hand
out. Resolved by keeping every workspace's roster file (its confidentiality
already coming from encryption, not from repo privacy -- the same principle
`sops`-encrypted files rely on when committed to public infra repos) in one
small, dedicated, always-public repo, separate from any workspace's own
(potentially private) content repo.

**A real, named security trade-off, surfaced by live research into Decap
CMS (formerly Netlify CMS)**: handing a decrypted GitHub token to
client-side JS, which then calls GitHub's API directly with no server in
between, is exactly the trade-off that community has already debated
in the open. Their own consensus: acceptable for a small, trusted-group,
low-stakes deployment; never recommended at adversarial/public scale. This
matches task 6's own stated scope (5-10 trusted admins) exactly, and is
recorded here as an explicit boundary, not an oversight.

## Core Concepts

**Workspace.** One real GitHub repository (public or private), holding
whatever `annotation_model`/`alignment` content it wants. This spec adds no
code that touches that content -- workspaces are opaque to everything below.

**Workspace-id.** A short, URL-safe slug the operator picks at provisioning
time (e.g. `mikadiv-fm-public`, `acme-bank-internal`), unique only within
`workspace-auth`'s own `rosters/` directory -- unrelated to, and not
derived from, the workspace's actual `<owner>/<repo>` (which can be any
org, including one outside `OpenFASTER-Standard` entirely, and is recorded
inside the encrypted payload, not the filename). Two different
organizations' same-named repos never collide, because the slug is chosen
independently each time.

**Workspace-auth repo.** One new, small, dedicated, always-public GitHub
repo (`OpenFASTER-Standard/workspace-auth`), created as part of this task,
holding:
- A generic, static login page (`index.html` + a bundled `age.js`, built
  from the real `age-encryption` npm package via `esbuild`, exactly per
  that package's own documented browser-usage instructions), deployed via
  GitHub Pages. One page serves every workspace; which workspace is
  selected via a query parameter (`?workspace=<workspace-id>`).
- `rosters/<workspace-id>.age` -- one `age` passphrase-encrypted file per
  workspace, stored exactly as `pyrage.passphrase.encrypt` produces it (a
  raw binary container beginning with the ASCII header
  `age-encryption.org/v1` -- confirmed live; `pyrage` has no ASCII-armor
  function of its own, and the verified spike used this raw form directly
  on both the Python and JS sides, so this spec does the same rather than
  adding an unverified armoring step). Decrypted plaintext is a small JSON
  document: `{"workspace_repo": "<owner>/<repo>", "github_token":
  "<fine-grained PAT, scoped to only that one repo, contents:write>"}`. A
  GitHub PR touching this file shows "binary file changed" rather than a
  rendered diff -- acceptable here, since a meaningful review of this file
  is about *which workspace's roster changed and when* (visible in the
  commit itself), not a line-level content review of ciphertext.

**Roster file as both the user directory and the auth check.** There is no
separate "who is an admin" list to keep in sync: the roster file's
existence *is* the fact that a workspace has an admin group, and a
successful decrypt of it with a given passphrase *is* the authentication
decision. This is a deliberate Phase-1 simplification: one shared passphrase
per workspace admin group (matching Wikipedia's own real early history,
cited in task-master's original research, of a small trusted group without
individually-revocable accounts yet), not per-admin individual credentials.
Per-admin identity and rotation is Phase 2 (see Non-Goals) -- age's own
spec-level constraint (a passphrase/`scrypt` recipient stanza cannot occur
alongside a non-`scrypt`, i.e. individual-keypair, recipient in the same
file) means that upgrade is a new file shape, not a small patch to this one,
so it is correctly deferred rather than half-built now.

**`generator/workspace_auth/roster.py`.** The one piece of new Python in
this repo:
- `create_roster(*, workspace_repo: str, github_token: str, passphrase: str) -> bytes`
  -- builds the JSON payload, encrypts it with `pyrage.passphrase.encrypt`,
  returns the raw bytes ready to write to `rosters/<workspace-id>.age`.
- `read_roster(ciphertext: bytes, *, passphrase: str) -> dict` -- decrypts
  via `pyrage.passphrase.decrypt`, JSON-parses the plaintext. Raises a
  named `RosterAuthenticationError(ValueError)` on a wrong passphrase or a
  corrupted file (wrapping `pyrage.DecryptError`), and a separate
  `RosterFormatError(ValueError)` if decryption succeeds but the plaintext
  isn't valid JSON in the expected shape -- matching this codebase's actual
  current convention of small, specific exceptions deriving directly from
  the nearest fitting builtin (e.g. `alignment/sssom.py`'s
  `SssomParseError(ValueError)`, `annotation_model/store.py`'s
  `TargetStoreError(RuntimeError)`), not a shared base error class -- there
  is no longer one in this codebase (`generator_errors`, which used to
  provide one, was removed with the old stack).

These two functions are the entire Python surface. Provisioning a new
workspace's roster is a human, documented, manual runbook (see Data Flow) --
not a CLI or an automated pipeline. Automating repo creation itself would
be easy; automating fine-grained PAT issuance is not possible at all
(GitHub has no API for a token to mint a new fine-grained PAT for itself --
a deliberate GitHub security boundary), so any amount of automation here
would still bottleneck on a manual step, and a half-automated tool that
still needs the operator to tab over to GitHub's UI mid-run is worse than
one honest runbook.

## Data Flow

**Provisioning a new workspace** (manual, by a trusted operator who already
has their own `gh` access -- this step's trust boundary is "whoever the
existing OpenFASTER-Standard org already trusts with repo-creation rights,"
which is exactly as narrow as task 6 itself asks for):

1. Operator creates the workspace's content repo (`gh repo create
   <owner>/<name> --public` or `--private`).
2. Operator manually creates a fine-grained PAT scoped to only that repo,
   `contents: write` permission, via GitHub's web UI (not automatable, see
   Core Concepts).
3. Operator picks a passphrase for this workspace's admin group and runs
   `create_roster(workspace_repo=..., github_token=..., passphrase=...)`,
   writes the result to `workspace-auth/rosters/<workspace-id>.age`.
4. Operator commits and pushes that one file to `workspace-auth`.
5. Operator shares the passphrase with the trusted admin group out of band,
   via this box's existing Vaultwarden org vault (already the established
   mechanism for exactly this kind of shared-team-secret distribution on
   this project).

**Logging in** (any admin, any browser, no install):

1. Admin opens `https://openfaster-standard.github.io/workspace-auth/?workspace=<workspace-id>`.
2. Page fetches `rosters/<workspace-id>.age` (always succeeds -- the file is
   public; its content, not its reachability, is the protection).
3. Admin types the shared passphrase into what looks like an ordinary login
   form.
4. Page calls `d.addPassphrase(entered)` then `await d.decrypt(ciphertext,
   "text")` client-side (the real, verified `age-encryption` API -- two
   calls, not chained), then `JSON.parse`s the result. Success: the
   decrypted `github_token` is held in page memory (`sessionStorage` is
   explicitly *not* used for it -- see Error Handling) and the page shows a
   logged-in state naming the workspace. Failure (decrypt rejects, or the
   result isn't the expected JSON shape): the page shows a plain "incorrect
   passphrase" message and nothing else -- no distinction between "wrong
   passphrase" and "workspace doesn't exist," matching normal login-form
   practice of not confirming which part of a credential was wrong.

Nothing after step 4 (actually writing an annotation via the held token) is
in scope for this task -- see Non-Goals.

## Error Handling

- **Wrong passphrase**: `Decrypter.decrypt` rejects with age's own real,
  verified error ("no identity matched any of the file's recipients"). The
  login page catches this and shows a generic failure message. `read_roster`
  on the Python side raises `RosterAuthenticationError` for the same
  underlying failure, so a test or a future caller can distinguish "bad
  passphrase" from a Python-level bug without string-matching age's own
  error text.
- **Corrupted or truncated roster file**: verified live -- `pyrage`
  raises the same `DecryptError` type for a truncated file ("failed to
  fill whole buffer") as it does for a wrong passphrase ("Decryption
  failed"), just with a different message. `read_roster` wraps both into
  the same `RosterAuthenticationError` -- an admin-facing failure either
  way, not a stack trace, and not a distinction worth exposing to the
  caller since neither case is actionable differently by an admin typing a
  passphrase.
- **Roster file not found (404)**: the login page must not crash or show a
  raw fetch error -- a mistyped or not-yet-provisioned `workspace-id` shows
  "no such workspace," a real, named case, not an unhandled promise
  rejection.
- **Decrypted token never persisted**: the decrypted `github_token` lives
  only in an in-memory JS variable for the lifetime of the page load, never
  written to `localStorage`/`sessionStorage`/a cookie. This is a deliberate
  choice to bound the leak surface. It is not defended against by this
  task's tests (there is no write client yet to exercise the token at all
  -- see Non-Goals) but is a real Review Focus item for whichever future
  task adds one: back this claim with a test at that point, not now, since
  there is nothing yet that would make the test meaningful.

## Testing Strategy

**Python (`tests/workspace_auth/test_roster.py`)**:
- `create_roster` then `read_roster` round-trips the exact original payload.
- `read_roster` with the wrong passphrase raises `RosterAuthenticationError`,
  not a bare `pyrage` exception leaking through.
- `read_roster` on a truncated/corrupted ciphertext raises the same
  `RosterAuthenticationError` (wrapping `pyrage.DecryptError`, verified
  live to cover both this case and a wrong passphrase), not an unhandled
  `pyrage` exception leaking through.
- `read_roster` on a *correct* passphrase whose decrypted plaintext isn't
  valid JSON in the expected shape raises `RosterFormatError`, not
  `RosterAuthenticationError` and not a bare `json.JSONDecodeError`.
- `create_roster`'s output begins with the real age binary header
  (`age-encryption.org/v1`, verified live to be `pyrage`'s actual output
  format), so a test can assert on real, checkable structure rather than
  merely "some bytes came back."

**Cross-implementation and browser (`tests/workspace_auth/test_login_page.py`
or equivalent under whatever this repo's real JS-adjacent test location
turns out to be during planning)**:
- A roster file produced by the real `create_roster` (Python/`pyrage`) is
  decrypted correctly by the real bundled `age-encryption` JS, driven
  through a real headless-browser page load (Playwright), not a Node-only
  unit test -- this is the exact scenario this spec's own live spike already
  proved works, turned into a permanent regression test rather than a
  one-off.
- The same fixture with the wrong passphrase shows the login page's
  generic failure state, verified via the rendered DOM, not by inspecting
  a thrown JS exception directly.
- A `workspace-id` with no matching roster file shows the "no such
  workspace" state, verified the same way.

**Review Focus** (input classes this spec implies but the tests above don't
yet pin, most likely to bite a real admin first):
- A roster file that decrypts successfully but whose plaintext is not valid
  JSON in the expected shape (e.g. hand-edited, or produced by a future
  tool version with a different payload shape) -- `read_roster` must raise
  `RosterFormatError`, not let a `json.JSONDecodeError` leak through
  unlabeled (already covered above in Testing Strategy proper; listed here
  too since it is the single most likely real mistake an operator makes by
  hand-editing a roster's plaintext before re-encrypting it).
- A passphrase containing characters the login form's own input handling
  might mangle (leading/trailing whitespace from a copy-paste out of a
  password manager, non-ASCII characters) -- must be passed to
  `addPassphrase` exactly as typed, no silent trimming that would make a
  correct passphrase appear wrong.
- Opening the login page with no `?workspace=` query parameter at all --
  must show an explicit "which workspace?" state, not a blank page or a
  fetch to a literal `undefined` URL.

## Non-Goals

- **No automated repo creation or fine-grained-PAT issuance.** The former
  is easy but pointless to automate alone; the latter is impossible via any
  GitHub API today. Provisioning is one honest manual runbook (see Data
  Flow), not a half-automated tool that still stops for a manual step.
- **No per-admin individual credentials, rotation, or audit trail of *who*
  logged in** -- Phase 1 is one shared passphrase per workspace admin
  group, matching Wikipedia's own real early history and this task's own
  "start deliberately narrow" framing. Individual identity is Phase 2, a
  different file shape (age's own spec forbids mixing `scrypt` and
  individual-keypair recipients in one file), and explicitly not this task.
- **No write client.** This task proves an admin can obtain a valid,
  scoped GitHub token client-side. It does not spend that token on any
  GitHub API call. A future task builds the Content-API write client;
  another future task wires that into an actual annotation-editing UI
  (task 3's shape-driven form generation, `@openfaster-standard/ui`).
- **No GitHub App, no bot identity, no automated/unattended writer.**
  Nothing in this codebase writes without a human running it (confirmed via
  grep). The credential format this task's roster file stores is agnostic
  to what's inside it, so a future GitHub App's installation-token-minting
  private key fits into the exact same mechanism without redesigning it --
  but building that App, and the service that would mint tokens from it, is
  explicitly deferred until an actual automated writer exists to justify it.
- **No branch protection, required reviewers, or PR-based write flow.**
  Phase 1 has exactly one trust tier (admin); there is no second party's
  edit to gate behind a review yet. Real future work once Phase 2 exists.
- **No defense beyond "small, trusted group."** The in-memory-only token
  handling in Error Handling raises the bar somewhat, but this design is
  explicitly, on the record, not safe to scale to an adversarial or public
  admin pool without a fresh design pass -- matching the real, live-researched
  consensus on this exact trade-off from the Decap/Netlify CMS community.

## Open Questions

- **Exact repo name for the new public workspace-auth repo**
  (`workspace-auth` used as a working name throughout this spec) -- pick at
  implementation time, no functional dependency on the exact string.
- **Exact location of JS-adjacent browser tests within `generator`'s own
  test tree** -- this repo has no precedent for a Playwright-driven test
  today (the old `webapp/frontend` React test suite, which did have one, was
  removed in the old-stack cleanup); the implementation plan should decide
  where this lives (inside `generator/tests/` invoked via a Python-wrapped
  Playwright call, matching this project's existing `pytest`-only CI job, or
  as a small separate `package.json` inside the new `workspace-auth` repo
  with its own minimal CI) rather than this spec prescribing one.
