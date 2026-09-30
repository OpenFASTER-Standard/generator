# Workspace Admin Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove an admin can authenticate to a specific annotation workspace
with zero server and zero database, using a passphrase-decryptable,
git-committed roster file and a static GitHub Pages login page.

**Architecture:** Three bottom-up tasks across two repositories. Task 1
builds and tests the Python roster encrypt/decrypt module in `generator`.
Task 2 creates the new, small, dedicated public `workspace-auth` repo and
its static login page, bundling the real `age-encryption` npm package.
Task 3 proves the whole thing works end to end with a real headless-browser
test, turning this session's own live spike into a permanent regression
test, plus the spec's named Review Focus edge cases.

**Tech Stack:** Python 3.11, `pyrage` (new dependency, real PyPI package,
verified live this session: dual-mode passphrase/asymmetric API, no armor
module, raw binary output beginning with the ASCII header
`age-encryption.org/v1`). JavaScript: `age-encryption` npm package v0.3.1
(`FiloSottile/typage`), bundled with `esbuild`. Playwright (already baked
into this box's image) for the real headless-browser test.

**Spec:** `docs/specs/2026-09-30-workspace-admin-authentication-design.md`

## Global Constraints

- **No ASCII armor anywhere.** `pyrage.passphrase.encrypt`/`decrypt` work
  directly on raw binary (verified live; `pyrage` has no `armor` module).
  Roster files are `.age` raw binary, not `.txt` armored text.
- **`RosterAuthenticationError(ValueError)` and `RosterFormatError(ValueError)`**
  are the only two exception types `read_roster` raises — no shared base
  error class exists in this codebase anymore (`generator_errors` was
  removed with the old stack); every other module here (`alignment/sssom.py`'s
  `SssomParseError(ValueError)`, `annotation_model/store.py`'s
  `TargetStoreError(RuntimeError)`) derives its own exception directly from
  the nearest fitting builtin, and this task matches that convention.
- **The decrypted `github_token` is held only in an in-memory JS variable**
  on the login page — never `localStorage`, `sessionStorage`, or a cookie.
- **Workspace-id is an independent slug, never derived from `owner/repo`.**
  It is the roster filename's stem only; the actual `owner/repo` string
  lives inside the encrypted payload.
- **No automated repo creation or fine-grained-PAT issuance** — GitHub has
  no API for a token to self-issue a new fine-grained PAT (a deliberate
  GitHub security boundary). Task 2's repo-creation and Pages-enablement
  steps are a real, externally-visible, moderately consequential action (a
  new public GitHub org repo) — **stop and get the operator's explicit
  confirmation before running them**, per this project's own standing rule
  for any side effect outside the current worktree.

## Review Focus

- **A roster file that decrypts successfully but whose plaintext isn't
  valid JSON in the expected shape** must raise `RosterFormatError`, not
  `RosterAuthenticationError` and not a bare `json.JSONDecodeError` —
  covered in Task 1.
- **A passphrase with leading/trailing whitespace or non-ASCII characters**
  must reach `addPassphrase` byte-for-byte as typed, with no silent
  trimming that would make a correct passphrase appear wrong — covered in
  Task 3.
- **Opening the login page with no `?workspace=` query parameter at all**
  must show an explicit "which workspace?" state, never a blank page or a
  fetch to a literal `undefined` URL — covered in Task 2 (implementation)
  and Task 3 (test).
- **A `workspace-id` with no matching roster file (404)** must show "no
  such workspace," not a raw fetch error — covered in Task 2
  (implementation) and Task 3 (test).
- **Wrong passphrase and a truncated/corrupted ciphertext are the same
  user-facing failure**, verified live this session to both raise
  `pyrage.DecryptError` (different messages, same type) — covered in
  Task 1; the login page must not attempt to distinguish them either
  (Task 2/3), matching normal login-form practice of not confirming which
  part of a credential was wrong.

---

### Task 1: `generator/workspace_auth/roster.py` — encrypt/decrypt

**Files:**
- Modify: `pyproject.toml` (`[project]` `dependencies` list)
- Create: `workspace_auth/__init__.py` (empty)
- Create: `workspace_auth/roster.py`
- Create: `tests/workspace_auth/__init__.py` (empty)
- Test: `tests/workspace_auth/test_roster.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `RosterAuthenticationError(ValueError)`,
  `RosterFormatError(ValueError)`,
  `create_roster(*, workspace_repo: str, github_token: str, passphrase: str) -> bytes`,
  `read_roster(ciphertext: bytes, *, passphrase: str) -> dict`. Task 3's
  fixture-generation step consumes both functions.

- [ ] **Step 1: Add the dependency**

Add `"pyrage>=0.4"` to `pyproject.toml`'s `[project]` `dependencies` list
(alongside the existing `lxml`, `rdflib`, etc. entries — verified live this
session at v0.4.x on PyPI). Run `.venv/bin/pip install -e ".[dev]"`.

- [ ] **Step 2: Write the failing test for the round trip**

```python
# tests/workspace_auth/test_roster.py
import json

import pytest

from workspace_auth.roster import create_roster, read_roster


def test_create_then_read_roundtrips_the_exact_payload():
    ciphertext = create_roster(
        workspace_repo="OpenFASTER-Standard/mikadiv-fm-public",
        github_token="github_pat_fake_test_token_value",
        passphrase="correct-horse-battery-staple",
    )

    payload = read_roster(ciphertext, passphrase="correct-horse-battery-staple")

    assert payload == {
        "workspace_repo": "OpenFASTER-Standard/mikadiv-fm-public",
        "github_token": "github_pat_fake_test_token_value",
    }
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'workspace_auth'`).

- [ ] **Step 4: Implement `create_roster` and `read_roster` in `workspace_auth/roster.py`**

```python
import json

from pyrage import DecryptError, passphrase as age_passphrase


class RosterAuthenticationError(ValueError):
    """Wrong passphrase, or a corrupted/truncated ciphertext -- pyrage
    raises the same DecryptError for both (verified live: "Decryption
    failed" vs. "failed to fill whole buffer"), and neither case is
    actionable differently by an admin typing a passphrase, so this
    wraps both the same way."""


class RosterFormatError(ValueError):
    """Decryption succeeded, but the plaintext isn't the expected JSON
    shape -- a hand-edited or wrong-version roster, never the caller's
    passphrase being at fault."""


def create_roster(*, workspace_repo: str, github_token: str, passphrase: str) -> bytes:
    payload = json.dumps({"workspace_repo": workspace_repo, "github_token": github_token})
    return age_passphrase.encrypt(payload.encode("utf-8"), passphrase)


def read_roster(ciphertext: bytes, *, passphrase: str) -> dict:
    try:
        plaintext = age_passphrase.decrypt(ciphertext, passphrase)
    except DecryptError as exc:
        raise RosterAuthenticationError(str(exc)) from exc

    try:
        return json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise RosterFormatError(f"roster plaintext is not valid JSON: {exc}") from exc
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS

- [ ] **Step 6: Write the failing test for a wrong passphrase**

```python
def test_wrong_passphrase_raises_roster_authentication_error():
    ciphertext = create_roster(
        workspace_repo="owner/repo", github_token="tok", passphrase="right-passphrase",
    )

    from workspace_auth.roster import RosterAuthenticationError

    with pytest.raises(RosterAuthenticationError):
        read_roster(ciphertext, passphrase="wrong-passphrase")
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS (Step 4's `except DecryptError` already covers this; run to
confirm rather than assume)

- [ ] **Step 8: Write the failing test for a truncated/corrupted ciphertext**

```python
def test_truncated_ciphertext_raises_the_same_roster_authentication_error():
    from workspace_auth.roster import RosterAuthenticationError

    ciphertext = create_roster(workspace_repo="owner/repo", github_token="tok", passphrase="p")
    truncated = ciphertext[:20]

    with pytest.raises(RosterAuthenticationError):
        read_roster(truncated, passphrase="p")
```

- [ ] **Step 9: Run test to verify it passes**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS (verified live this session: `pyrage` raises `DecryptError`
for a truncated buffer too, just with a different message — "failed to
fill whole buffer"; run to confirm)

- [ ] **Step 10: Write the failing test for a correct passphrase but non-JSON plaintext**

```python
def test_correct_passphrase_but_non_json_plaintext_raises_roster_format_error():
    from pyrage import passphrase as age_passphrase
    from workspace_auth.roster import RosterFormatError

    ciphertext = age_passphrase.encrypt(b"not json at all {{{", "p")

    with pytest.raises(RosterFormatError):
        read_roster(ciphertext, passphrase="p")
```

- [ ] **Step 11: Run test to verify it fails**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: FAIL (`json.JSONDecodeError` propagating uncaught, if Step 4's
`try/except json.JSONDecodeError` block were missing — it already exists
per Step 4's implementation, so confirm this actually passes instead;
if it fails for a different reason, fix the implementation, not the test)

- [ ] **Step 12: Run test to verify it passes**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS

- [ ] **Step 13: Write the failing test asserting `create_roster`'s real output format**

```python
def test_create_roster_output_is_real_age_binary_format():
    ciphertext = create_roster(workspace_repo="owner/repo", github_token="tok", passphrase="p")
    assert ciphertext.startswith(b"age-encryption.org/v1")
```

- [ ] **Step 14: Run test to verify it passes**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS (verified live this session to be `pyrage`'s actual output
format; run to confirm)

- [ ] **Step 15: Run all of Task 1's tests together**

Run: `.venv/bin/pytest tests/workspace_auth/test_roster.py -v`
Expected: PASS (6 passed)

- [ ] **Step 16: Commit**

```bash
git add pyproject.toml workspace_auth/__init__.py workspace_auth/roster.py tests/workspace_auth/__init__.py tests/workspace_auth/test_roster.py
git commit -m "feat(workspace_auth): add roster encrypt/decrypt via pyrage passphrase mode"
```

---

### Task 2: `workspace-auth` repo — static login page

**Files (in a new sibling checkout, `/work/workspace-auth`):**
- Create: `index.html`
- Create: `age.js` (built artifact, committed — see Step 3)
- Create: `README.md` (documents the roster format and the `age.js`
  regeneration command)
- Create: `rosters/.gitkeep`

**Interfaces:**
- Consumes: nothing from Task 1 directly (the login page has no Python
  dependency at runtime) — Task 3's fixture step consumes Task 1's
  `create_roster` to produce a `.age` file this page can decrypt.
- Produces: a real, deployed static site whose login behavior Task 3 tests
  against.

**STOP before Step 1: this task creates a new public GitHub repository and
enables GitHub Pages on it — a real, externally-visible action. Confirm
the exact repo name and get the operator's explicit go-ahead before
proceeding**, per this plan's Global Constraints and this project's
standing rule for any side effect outside the current worktree.

- [ ] **Step 1: Create the repo (after operator confirmation)**

```bash
gh repo create OpenFASTER-Standard/workspace-auth --public \
  --description "Static, serverless admin login for OpenFASTER annotation workspaces"
git clone https://github.com/OpenFASTER-Standard/workspace-auth.git /work/workspace-auth
```

- [ ] **Step 2: Scaffold the rosters directory**

```bash
mkdir -p /work/workspace-auth/rosters
touch /work/workspace-auth/rosters/.gitkeep
```

- [ ] **Step 3: Build the real `age.js` bundle**

```bash
cd /tmp && mkdir age-build && cd age-build
npm init -y >/dev/null
npm install esbuild age-encryption
npx esbuild --target=es2022 --bundle --minify --outfile=age.js --global-name=age age-encryption
cp age.js /work/workspace-auth/age.js
```

Verify: `head -c 40 /work/workspace-auth/age.js` prints minified JS (not an
error), and `wc -c /work/workspace-auth/age.js` is non-zero (this exact
command was verified live this session to produce a ~150KB working bundle).

- [ ] **Step 4: Write `index.html`**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>OpenFASTER Workspace Login</title>
  <script src="age.js"></script>
</head>
<body>
  <div id="app">Loading...</div>
  <script>
  function getWorkspaceId() {
    return new URLSearchParams(window.location.search).get("workspace");
  }

  function renderNoWorkspace() {
    document.getElementById("app").textContent =
      "Which workspace? Open this page with ?workspace=<workspace-id>.";
  }

  function renderNoSuchWorkspace(workspaceId) {
    document.getElementById("app").textContent =
      "No such workspace: " + workspaceId;
  }

  function renderLoginForm(workspaceId, onSubmit) {
    const app = document.getElementById("app");
    app.textContent = "";

    const heading = document.createElement("p");
    heading.textContent = "Log in to " + workspaceId;
    app.appendChild(heading);

    const input = document.createElement("input");
    input.type = "password";
    input.placeholder = "Passphrase";
    app.appendChild(input);

    const button = document.createElement("button");
    button.textContent = "Log in";
    app.appendChild(button);

    const error = document.createElement("p");
    error.id = "error";
    app.appendChild(error);

    button.addEventListener("click", () => onSubmit(input.value, error));
  }

  function renderLoggedIn(workspaceId) {
    document.getElementById("app").textContent = "Logged in to " + workspaceId;
  }

  async function main() {
    const workspaceId = getWorkspaceId();
    if (!workspaceId) {
      renderNoWorkspace();
      return;
    }

    const response = await fetch("rosters/" + workspaceId + ".age");
    if (!response.ok) {
      renderNoSuchWorkspace(workspaceId);
      return;
    }
    const ciphertext = new Uint8Array(await response.arrayBuffer());

    renderLoginForm(workspaceId, async (enteredPassphrase, errorEl) => {
      try {
        const d = new age.Decrypter();
        d.addPassphrase(enteredPassphrase);
        const plaintext = await d.decrypt(ciphertext, "text");
        const payload = JSON.parse(plaintext);
        window._workspaceAuthToken = payload.github_token;
        renderLoggedIn(workspaceId);
      } catch (e) {
        errorEl.textContent = "Incorrect passphrase.";
      }
    });
  }

  main();
  </script>
</body>
</html>
```

Note: `window._workspaceAuthToken` is a deliberately explicit, greppable
in-memory-only holding place — never `localStorage`/`sessionStorage`/a
cookie, per this plan's Global Constraints. The entered passphrase is read
from `input.value` and passed to `addPassphrase` with no trimming, so
leading/trailing whitespace or non-ASCII characters reach it exactly as
typed.

- [ ] **Step 5: Write `README.md` documenting the roster format and regeneration commands**

Document: the `.age` file format (raw `pyrage.passphrase.encrypt` output,
no armor), the decrypted JSON shape (`{"workspace_repo": ..., "github_token": ...}`),
the exact `esbuild` command from Step 3 for regenerating `age.js`, and the
manual provisioning runbook from the spec's Data Flow section (repo
creation, manual fine-grained PAT creation, running `create_roster`,
sharing the passphrase via Vaultwarden).

- [ ] **Step 6: Commit and push**

```bash
cd /work/workspace-auth
git add index.html age.js README.md rosters/.gitkeep
git commit -m "feat: static, serverless login page for OpenFASTER workspace admins"
git push origin main
```

- [ ] **Step 7: Enable GitHub Pages (after operator confirmation, same gate as Step 1)**

```bash
gh api repos/OpenFASTER-Standard/workspace-auth/pages -X POST \
  -f "source[branch]=main" -f "source[path]=/"
```

Verify: `gh api repos/OpenFASTER-Standard/workspace-auth/pages` shows
`"status"` progressing toward `"built"` (may take a minute to finish
deploying — not blocking for Task 3, which tests the page via a local
static server, not the live Pages URL).

---

### Task 3: End-to-end browser proof + Review Focus coverage

**Files (in `/work/workspace-auth`):**
- Create: `tests/generate_fixtures.py` (one-off script, run manually, not
  part of any CI — produces the committed fixture in Step 1)
- Create: `tests/fixtures/test-workspace.age` (committed binary fixture)
- Create: `tests/package.json`
- Create: `tests/login.spec.mjs` (Playwright test)

**Interfaces:**
- Consumes: `create_roster` (Task 1) — used once, manually, to produce the
  committed fixture; not a runtime dependency of the test suite itself.
- Produces: nothing further — this is the plan's final task.

- [ ] **Step 1: Generate the real test fixture using Task 1's `create_roster`**

```python
# /work/workspace-auth/tests/generate_fixtures.py
"""Run once, manually, from /work/generator's own venv:
    /work/generator/.venv/bin/python /work/workspace-auth/tests/generate_fixtures.py
Regenerate only if the roster payload shape or the pyrage/age-encryption
wire format ever changes -- this is a committed fixture, not built at
test time, so workspace-auth's own test suite has no Python dependency.
"""
from workspace_auth.roster import create_roster

TEST_PASSPHRASE = "test-fixture-passphrase-not-a-real-secret"

ciphertext = create_roster(
    workspace_repo="OpenFASTER-Standard/test-workspace",
    github_token="github_pat_fake_fixture_token",
    passphrase=TEST_PASSPHRASE,
)
with open("/work/workspace-auth/tests/fixtures/test-workspace.age", "wb") as f:
    f.write(ciphertext)
print("wrote", len(ciphertext), "bytes")
```

Run: `mkdir -p /work/workspace-auth/tests/fixtures && /work/generator/.venv/bin/python /work/workspace-auth/tests/generate_fixtures.py`
Expected: prints `wrote <N> bytes`, and `tests/fixtures/test-workspace.age`
exists.

- [ ] **Step 2: Set up the Playwright test project**

```bash
cd /work/workspace-auth/tests
npm init -y >/dev/null
npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 3: Write the failing test for the documented, already-verified success path**

```javascript
// /work/workspace-auth/tests/login.spec.mjs
import { test, expect } from "@playwright/test";
import { execSync } from "node:child_process";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");

test.beforeAll(() => {
  execSync("cp -r " + ROOT + "/rosters /tmp/workspace-auth-test-rosters || true");
});

test("correct passphrase decrypts the roster and shows logged-in state", async ({ page }) => {
  await page.goto("file://" + ROOT + "/index.html?workspace=test-workspace");
  // index.html fetches rosters/<id>.age relative to its own location --
  // for this test, serve the fixture at that path via routing rather
  // than requiring a real HTTP server for a file:// page.
  await page.route("**/rosters/test-workspace.age", (route) =>
    route.fulfill({ path: path.join(ROOT, "tests", "fixtures", "test-workspace.age") })
  );
  await page.reload();

  await page.fill("input[type=password]", "test-fixture-passphrase-not-a-real-secret");
  await page.click("button");

  await expect(page.locator("#app")).toContainText("Logged in to test-workspace");
});
```

- [ ] **Step 4: Run the test**

Run: `cd /work/workspace-auth/tests && npx playwright test`
Expected: PASS — Task 2's `index.html`/`age.js` already implement this
exact behavior, so this is a "run to confirm rather than assume" step, not
a from-scratch RED→GREEN cycle (the feature under test was built in a
prior task; this task's own new artifact is the test itself, whose
"before" state is simply not existing yet — confirm that by checking `npx
playwright test` fails with "no tests found" before this step is written,
not by expecting the page's behavior itself to be broken). If it instead
fails on a real assertion, read the Playwright trace to find the actual
bug (e.g. a route-timing issue) and fix `index.html`, not the test.

- [ ] **Step 5: Write the failing test for the wrong-passphrase case**

```javascript
test("wrong passphrase shows a generic incorrect-passphrase error, not a raw exception", async ({ page }) => {
  await page.route("**/rosters/test-workspace.age", (route) =>
    route.fulfill({ path: path.join(ROOT, "tests", "fixtures", "test-workspace.age") })
  );
  await page.goto("file://" + ROOT + "/index.html?workspace=test-workspace");

  await page.fill("input[type=password]", "definitely-the-wrong-passphrase");
  await page.click("button");

  await expect(page.locator("#error")).toContainText("Incorrect passphrase");
});
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npx playwright test`
Expected: PASS (Task 2's `catch` block already produces this text; run to
confirm rather than assume)

- [ ] **Step 7: Write the failing test for a passphrase with surrounding whitespace (Review Focus)**

```javascript
test("a correct passphrase with surrounding whitespace is treated as a different, wrong passphrase", async ({ page }) => {
  // Proves the page does NOT silently trim -- typing the right passphrase
  // with accidental leading/trailing spaces must behave like a wrong
  // passphrase, not silently succeed via trimming. (A real password
  // manager or terminal copy-paste can introduce this.)
  await page.route("**/rosters/test-workspace.age", (route) =>
    route.fulfill({ path: path.join(ROOT, "tests", "fixtures", "test-workspace.age") })
  );
  await page.goto("file://" + ROOT + "/index.html?workspace=test-workspace");

  await page.fill("input[type=password]", "  test-fixture-passphrase-not-a-real-secret  ");
  await page.click("button");

  await expect(page.locator("#error")).toContainText("Incorrect passphrase");
});
```

- [ ] **Step 8: Run test to verify it passes**

Run: `npx playwright test`
Expected: PASS (Task 2's `index.html` reads `input.value` directly with no
`.trim()` call; run to confirm this is really true rather than assuming)

- [ ] **Step 9: Write the failing test for a missing `?workspace=` parameter (Review Focus)**

```javascript
test("opening the page with no workspace query parameter shows an explicit prompt, not a blank page", async ({ page }) => {
  await page.goto("file://" + ROOT + "/index.html");
  await expect(page.locator("#app")).toContainText("Which workspace?");
});
```

- [ ] **Step 10: Run test to verify it passes**

Run: `npx playwright test`
Expected: PASS

- [ ] **Step 11: Write the failing test for a workspace-id with no roster file (Review Focus)**

```javascript
test("a workspace-id with no roster file shows a no-such-workspace state", async ({ page }) => {
  await page.route("**/rosters/nonexistent-workspace.age", (route) =>
    route.fulfill({ status: 404, body: "" })
  );
  await page.goto("file://" + ROOT + "/index.html?workspace=nonexistent-workspace");

  await expect(page.locator("#app")).toContainText("No such workspace: nonexistent-workspace");
});
```

- [ ] **Step 12: Run test to verify it passes**

Run: `npx playwright test`
Expected: PASS

- [ ] **Step 13: Run the full Playwright suite together**

Run: `npx playwright test`
Expected: PASS (6 passed)

- [ ] **Step 14: Run `generator`'s own full Python test suite to confirm nothing regressed there**

Run: `cd /work/generator && .venv/bin/pytest`
Expected: PASS (all pre-existing tests plus Task 1's new
`tests/workspace_auth/` tests)

- [ ] **Step 15: Commit and push the workspace-auth repo's test suite**

```bash
cd /work/workspace-auth
git add tests/
git commit -m "test: prove the login page's real behavior via headless-browser tests"
git push origin main
```
