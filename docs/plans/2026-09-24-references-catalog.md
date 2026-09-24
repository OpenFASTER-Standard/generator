# References Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the read-side skeleton from
`docs/specs/2026-09-24-references-catalog-design.md`: a plain, git-committed,
empty JSON catalog file for `Reference`s, plus a minimal UI (one FastAPI
endpoint, one static HTML page) to view it. No discovery, no write-path —
both are deliberately deferred.

**Architecture:** Three independent pieces: (1) a one-time data file
committed in the separate `ontologies` repo, (2) a thin serialization
function in `reference_model` (already free via `dataclasses.asdict()`,
confirmed JSON-safe for every selector type), and (3) a small FastAPI app
serving that function's output shape plus a static page rendering it.

**Tech Stack:** Python 3.11, `fastapi`/`uvicorn`/`httpx` (new dependencies,
already present in the environment — this plan only needs to declare them),
plus `reference_model` (already merged to `main`).

**Spec:** `docs/specs/2026-09-24-references-catalog-design.md`

## Global Constraints

- The catalog file lives at `ontologies/mikadiv-fm/references.json` — a
  **separate git repository** from `generator` (mounted at
  `/work/ontologies`), not `generator/ontologies/...`. It contains exactly
  `{}` and is committed there, never in `generator`.
- **Never push the `ontologies` repo's commit without asking first.**
  Committing locally in that repo is part of this plan; pushing it to its
  remote is a side effect on a separate shared repository and needs an
  explicit go-ahead in the moment, per this box's own norms around pushes
  to shared repos — stop and ask before running `git push` there.
- `to_json_dict()` is a thin `dataclasses.asdict()` wrapper — no
  special-casing per selector type, no `from_json_dict()`. Every selector
  type (`XPathSelector`, `SvgSelector`, `JsonSelector`) is already a flat
  dataclass of `str`/`int` fields only, so this is already fully JSON-safe.
- `webapp/app.py`'s `GET /api/references` endpoint reads the catalog path
  from the `REFERENCES_CATALOG_PATH` environment variable **at request
  time**, not at import time, defaulting to
  `/work/ontologies/mikadiv-fm/references.json` when unset.
- Nothing in this plan writes to the real committed catalog file after
  Task 1's one-time creation. Tests only ever read `tmp_path` fixtures.
- The static HTML page (`webapp/static/index.html`) has no automated
  test — this project has no frontend test runner, and one page rendering
  one table doesn't justify introducing one. It gets an explicit **manual
  verification step** instead (start the server, check in a real browser
  via the already-reserved `generator-webapp` port 8012), covering both
  the empty-catalog state and a state with real temporary fixture data.
  This step is required, not optional.

## Review Focus

- **The committed catalog file's exact bytes.** A reasonable person
  reading "starts as `{}`" would expect a minimal, clean JSON object —
  not e.g. `{}\n` with a trailing newline nobody decided on, or
  pretty-printed whitespace. Tested directly by reading the real file
  right after creation in Task 1.
- **A `Union`'s serialized `parts` must exactly match each part's own
  standalone `to_json_dict()` output.** A reasonable person building a
  future consumer (e.g. matching a `leaf_reference_id` the way
  `review_consultation` already does) would expect no divergence between
  a leaf serialized alone vs. nested inside a union. Tested directly in
  Task 2.
- **`REFERENCES_CATALOG_PATH` must be read per-request, not captured once
  at import time.** A reasonable person writing a test with
  `monkeypatch.setenv` before constructing `TestClient` would expect the
  override to take effect immediately; capturing it as a module-level
  constant would silently ignore the override and read the real
  production file in every test instead. Tested directly in Task 3 by
  overriding it per-test and asserting the override took effect.
- **A missing catalog file at request time.** A reasonable person
  deploying this would want to know this fails loudly (an HTTP 500), not
  silently returns `{}` as if the catalog were merely empty — those are
  different facts (misconfigured vs. genuinely empty) and conflating them
  would hide a real deployment mistake. Tested directly in Task 3.
- **The static page is actually reachable at `/`, not just `/api/references`
  working.** A reasonable person visiting the reserved port URL expects to
  see the page, not a 404 because the `StaticFiles` mount or the file
  itself is missing. Tested directly (automated, at the HTTP layer) in
  Task 3; the page's actual rendering is covered by the manual step.

---

## Task 1: Commit the empty references catalog

**Files:**
- Create: `/work/ontologies/mikadiv-fm/references.json` (separate repo, NOT under `/work/generator`)

**Interfaces:**
- Consumes: nothing.
- Produces: a real file at `/work/ontologies/mikadiv-fm/references.json`
  containing exactly `{}`, which Task 3's `webapp/app.py` defaults to
  reading in production (never read directly by any automated test in
  this plan).

This is a one-time data file, not logic — no TDD cycle applies (per
`superpowers:test-driven-development`'s own stated exception for
configuration/data files).

- [ ] **Step 1: Create the file**

```bash
printf '{}' > /work/ontologies/mikadiv-fm/references.json
```

- [ ] **Step 2: Verify its exact content**

Run: `cat -A /work/ontologies/mikadiv-fm/references.json`
Expected: `{}` with **no trailing `$` on its own line** — `cat -A` marks
line endings with `$`; the output should be exactly `{}$` with nothing
after it, confirming no trailing newline or extra whitespace was written.

- [ ] **Step 3: Verify it's valid, empty JSON**

Run: `python3 -c "import json; d = json.load(open('/work/ontologies/mikadiv-fm/references.json')); assert d == {}, d; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit in the `ontologies` repo (not `generator`)**

```bash
cd /work/ontologies
git add mikadiv-fm/references.json
git commit -m "Add empty references catalog for the generator's references-catalog UI"
git status
```

Expected: `git status` shows a clean working tree and `Your branch is
ahead of 'origin/main' by 1 commit` (or similar) — committed locally, **not
yet pushed**.

- [ ] **Step 5: Stop and ask before pushing**

Per this plan's Global Constraints, do not run `git push` in the
`ontologies` repo as part of this task. Surface the pending local commit
to your human partner and wait for explicit confirmation before pushing
it, exactly as you would for any other push to a shared repo.

---

## Task 2: `reference_model/serialize.py`

**Files:**
- Create: `reference_model/serialize.py`
- Test: `tests/reference_model/test_serialize.py`

**Interfaces:**
- Consumes: `Reference` (`reference_model.model`); `cite`, `cite_union`
  (`reference_model.cite`, already merged); `XPathSelector`
  (`reference_model.selectors.xpath_selector`, already merged).
- Produces: `to_json_dict(reference: Reference) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/reference_model/test_serialize.py`:

```python
import json

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def test_to_json_dict_serializes_a_real_leaf():
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    result = to_json_dict(leaf)

    assert result["reference_id"] == leaf.reference_id
    assert result["content_hash"]["algorithm"] == leaf.content_hash.algorithm
    assert result["content_hash"]["digest"] == leaf.content_hash.digest
    assert result["subject_document"]["family"] == "MiKaDiv_FM_Meldeart23"
    assert result["subject_document"]["version"] == "1.02"
    assert result["selector"]["type"] == "XPathSelector"
    assert result["selector"]["value"] == AORDNR_XPATH


def test_to_json_dict_survives_a_real_json_round_trip():
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    result = to_json_dict(leaf)
    round_tripped = json.loads(json.dumps(result))

    assert round_tripped == result


def test_to_json_dict_serializes_a_union_recursively():
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    union = cite_union([leaf_1, leaf_2])

    result = to_json_dict(union)

    assert result["reference_id"] == union.reference_id
    assert len(result["parts"]) == 2
    assert result["parts"][0] == to_json_dict(leaf_1)
    assert result["parts"][1] == to_json_dict(leaf_2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.serialize'`

- [ ] **Step 3: Implement `reference_model/serialize.py`**

```python
"""Serializes a Reference to a plain JSON-safe dict. See
docs/specs/2026-09-24-references-catalog-design.md.
"""
from __future__ import annotations

import dataclasses

from reference_model.model import Reference


def to_json_dict(reference: Reference) -> dict:
    return dataclasses.asdict(reference)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_serialize.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (134 tests: 131 previously passing, plus 3 new)

- [ ] **Step 6: Commit**

```bash
cd /work/generator
git add reference_model/serialize.py tests/reference_model/test_serialize.py
git commit -m "Add to_json_dict(): serialize a Reference to a plain JSON-safe dict"
```

---

## Task 3: `webapp` (API + static UI)

**Files:**
- Create: `webapp/__init__.py`
- Create: `webapp/app.py`
- Create: `webapp/static/index.html`
- Create: `tests/webapp/__init__.py`
- Test: `tests/webapp/test_app.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing from Task 1/2 at runtime (the endpoint reads a plain
  JSON file directly, not through `to_json_dict()` — the catalog file
  already contains plain JSON on disk by the time this app reads it).
- Produces: `app` (a `FastAPI` instance), importable as `webapp.app.app`.

- [ ] **Step 1: Add new dependencies and register the package**

Modify `pyproject.toml`:

```toml
[project]
name = "openfaster-generator"
version = "0.1.0"
description = "Source reference model and staleness-sweep tooling for OpenFASTER's MiKaDiv-FM regulatory schema"
requires-python = ">=3.11"
dependencies = [
    "lxml>=5.0",
    "pdfplumber>=0.11",
    "shapely>=2.0",
    "fastapi>=0.100",
    "uvicorn>=0.23",
    "httpx>=0.24",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "reportlab>=4.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*", "webapp*"]
```

- [ ] **Step 2: Reinstall**

```bash
cd /work/generator
python3 -m pip install --break-system-packages -e ".[dev]"
```

Expected: installs successfully (fastapi/uvicorn/httpx are already present
in this environment, so this is a metadata-only update, not a fresh
download).

- [ ] **Step 3: Create package skeletons**

`webapp/__init__.py`:

```python
"""Serves the references catalog: one JSON API endpoint, one static page
that renders it. See docs/specs/2026-09-24-references-catalog-design.md.
"""
```

`tests/webapp/__init__.py`: empty file.

- [ ] **Step 4: Write the failing tests**

`tests/webapp/test_app.py`:

```python
import json

from fastapi.testclient import TestClient

from webapp.app import app


def test_returns_empty_object_when_catalog_is_empty(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 200
    assert response.json() == {}


def test_returns_the_catalogs_real_content_when_populated(tmp_path, monkeypatch):
    fixture = {
        "fact-1": {
            "reference_id": "abc123",
            "subject_document": {
                "family": "MiKaDiv_FM_Meldeart23",
                "version": "1.02",
                "retrieval_uri": "/some/path.xsd",
            },
            "selector": {"type": "XPathSelector", "value": "/xs:schema"},
            "content_hash": {"algorithm": "sha256", "digest": "deadbeef"},
            "captured_at": "2026-09-24T00:00:00+00:00",
        }
    }
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 200
    assert response.json() == fixture


def test_returns_a_server_error_when_catalog_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "does-not-exist.json"))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/references")

    assert response.status_code == 500


def test_static_index_page_is_served_at_root():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/webapp/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.app'`

- [ ] **Step 6: Implement `webapp/app.py`**

```python
"""Serves the references catalog: one JSON API endpoint, one static page
that renders it. See docs/specs/2026-09-24-references-catalog-design.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


@app.get("/api/references")
def list_references() -> dict:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
```

- [ ] **Step 7: Implement `webapp/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MiKaDiv-FM References Catalog</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    th { background: #f0f0f0; }
    #empty { color: #666; font-style: italic; }
  </style>
</head>
<body>
  <h1>MiKaDiv-FM References Catalog</h1>
  <div id="content">Loading...</div>
  <script>
    fetch("/api/references")
      .then((response) => response.json())
      .then((catalog) => {
        const content = document.getElementById("content");
        const factKeys = Object.keys(catalog);
        if (factKeys.length === 0) {
          content.innerHTML = "<p id='empty'>No references yet.</p>";
          return;
        }
        const rows = factKeys.map((factKey) => {
          const reference = catalog[factKey];
          const family = reference.subject_document ? reference.subject_document.family : "";
          const selectorType = reference.selector ? reference.selector.type : "";
          const referenceId = reference.reference_id || "";
          return `<tr><td>${factKey}</td><td>${family}</td><td>${selectorType}</td><td>${referenceId}</td></tr>`;
        }).join("");
        content.innerHTML = `
          <table>
            <thead><tr><th>Fact key</th><th>Family</th><th>Selector type</th><th>Reference ID</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        `;
      });
  </script>
</body>
</html>
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS (4 tests)

- [ ] **Step 9: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (138 tests: 134 from Task 2, plus 4 new)

- [ ] **Step 10: Commit**

```bash
git add webapp/ tests/webapp/ pyproject.toml
git commit -m "Add webapp: GET /api/references endpoint plus a static catalog viewer page"
```

- [ ] **Step 11: Manual verification — empty-catalog state**

```bash
cd /work/generator
nohup uvicorn webapp.app:app --host 0.0.0.0 --port 8012 > /tmp/webapp.log 2>&1 & disown
sleep 1
curl -s http://localhost:8012/api/references
```

Expected: `{}` (the real committed catalog from Task 1). Then open
`http://cloud-admin-box.admin-toolbox.svc.cluster.local:8012/` in a
browser and confirm the page shows "No references yet." — not a blank
page, not a loading spinner stuck forever, not a JS error in the console.

- [ ] **Step 12: Manual verification — populated state**

```bash
cp /work/ontologies/mikadiv-fm/references.json /tmp/references-backup.json
cat > /work/ontologies/mikadiv-fm/references.json << 'EOF'
{
  "demo-fact": {
    "reference_id": "demo-reference-id",
    "subject_document": {"family": "MiKaDiv_FM_Meldeart23", "version": "1.02", "retrieval_uri": "/demo.xsd"},
    "selector": {"type": "XPathSelector", "value": "/xs:schema"},
    "content_hash": {"algorithm": "sha256", "digest": "deadbeef"},
    "captured_at": "2026-09-24T00:00:00+00:00"
  }
}
EOF
curl -s http://localhost:8012/api/references
```

Expected: the demo JSON just written. Refresh the same browser tab and
confirm the page now shows a one-row table: `demo-fact` /
`MiKaDiv_FM_Meldeart23` / `XPathSelector` / `demo-reference-id`.

- [ ] **Step 13: Revert the temporary demo data and stop the server**

```bash
cp /tmp/references-backup.json /work/ontologies/mikadiv-fm/references.json
rm /tmp/references-backup.json
cd /work/ontologies && git status
```

Expected: `git status` shows a clean working tree — the temporary demo
edit is fully reverted, matching Task 1's committed `{}` exactly. Then
stop the `uvicorn` process started in Step 11 (`pkill -f "uvicorn webapp.app"`).

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `ontologies/mikadiv-fm/references.json` exists, is committed, and
  contains exactly `{}`.
- [ ] `reference_model/serialize.py`'s `to_json_dict()` is implemented and
  tested with the semantics above.
- [ ] `webapp/app.py`'s `GET /api/references` endpoint is implemented,
  configurable via `REFERENCES_CATALOG_PATH`, and tested with the
  semantics above.
- [ ] `webapp/static/index.html` renders the catalog with an honest empty
  state, manually verified in a real browser via port 8012.
- [ ] All automated tests pass: `pytest tests/ -v` → 138 passed.
