# Catalog Revision History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the page+revision model from
`docs/specs/2026-09-25-catalog-revision-history-design.md`: a full
redesign (not an addition) of `references_catalog/catalog.py` and
`webapp/`, replacing the add-only catalog with pages that have an
ordered, immutable revision history.

**Architecture:** Three tasks, each a full rewrite of an existing,
already-merged file: the storage layer (`catalog.py`), the API layer
(`app.py`), then the presentation layer (`static/index.html`). Each
later task consumes the previous one's real interface, not a stub.

**Tech Stack:** Python 3.11, `lxml`/`fastapi`/`uvicorn` (already
dependencies), plus the real MiKaDiv-FM corpus.

**Spec:** `docs/specs/2026-09-25-catalog-revision-history-design.md`

## Global Constraints

- `add_revision()` **replaces** `save_reference()` entirely.
  `DuplicateFactKeyError` is **removed**, not deprecated or kept
  alongside. Calling `add_revision()` for a `fact_key` that doesn't exist
  yet creates it; calling it again appends another revision. There is no
  separate "create" operation.
- `is_correction` has **no default** — every `add_revision()` call must
  pass it explicitly.
- `catalog[fact_key]` in the JSON file is now a **list** of revision
  objects (was: one flat serialized `Reference`).
- `GET /api/references` is **removed** entirely, not kept alongside the
  new routes. `GET /api/pages` and `GET /api/pages/{fact_key}` replace it.
- `GET /api/pages/{fact_key}` returns a real HTTP 404 for an unknown
  `fact_key` — never a 200 with an empty history, since a page cannot
  exist with zero revisions (confirmed by `get_history()` already
  returning `[]` uniformly for any untouched key, existing or not).
- The static page still has **no automated test** — this project's own
  established convention (no frontend test runner). A manual, required
  Playwright verification step replaces it, exactly as it has for every
  prior `webapp`-touching plan.
- The real committed `ontologies/mikadiv-fm/references.json` must remain
  exactly `{}` after every manual verification step in this plan — any
  temporary demo data written to it must be reverted.

## Review Focus

- **`add_revision()` on a nonexistent `fact_key` must create the page**,
  while a genuinely **malformed catalog file must prevent any write at
  all** (raise `CatalogLoadError` before touching disk). A reasonable
  person would expect these two very different "not found" situations
  (a missing *page* vs. a missing/broken *file*) to behave completely
  differently, not be conflated into one error path. Tested directly in
  Task 1.
- **`list_pages()`/the index endpoint must reflect the CURRENT (latest)
  revision for a page with multiple revisions**, not just the trivial
  single-revision case. A reasonable person adding a correction would
  expect the index to immediately show the corrected value, not the
  original one it superseded. Tested directly in Task 1 and Task 2.
- **`GET /api/pages/{fact_key}` for an unknown key returns a real 404**,
  not a confusing 200 with an empty history that looks like a data bug.
  Tested directly in Task 2.
- **The old `GET /api/references` route must actually be gone**, not
  left dangling and half-working after the redesign. A reasonable person
  integrating against this API should get a real, unambiguous 404 for
  the old URL. Tested directly in Task 2.
- **A correction revision must be visually distinguishable from a
  routine one** in the rendered history — the entire reason
  `is_correction` exists. A reasonable person reviewing a page's history
  shouldn't have to read every comment string to find out which edits
  were fixes. Verified manually in Task 3.

---

## Task 1: `references_catalog/catalog.py` (full rewrite)

**Files:**
- Modify: `references_catalog/catalog.py` (full rewrite)
- Modify: `tests/references_catalog/test_catalog.py` (full rewrite —
  the current file tests `save_reference()`/`DuplicateFactKeyError`,
  which no longer exist)

**Interfaces:**
- Consumes: `Reference` (`reference_model.model`); `to_json_dict`
  (`reference_model.serialize`) — both already merged, unchanged.
- Produces: `Revision(revision_id, reference, author, comment,
  is_correction, created_at)`, `PageSummary(revision_count, current)`,
  `CatalogLoadError`, `load_catalog(catalog_path) -> dict`,
  `add_revision(catalog_path, fact_key, reference, author, comment,
  is_correction) -> Revision`, `get_current_revision(catalog_path,
  fact_key) -> Revision | None`, `get_history(catalog_path, fact_key) ->
  list[Revision]`, `list_pages(catalog_path) -> dict[str, PageSummary]`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/references_catalog/test_catalog.py`:

```python
import json
from pathlib import Path

import pytest

import references_catalog.catalog as catalog_module
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import (
    CatalogLoadError,
    add_revision,
    get_current_revision,
    get_history,
    list_pages,
    load_catalog,
)

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


def _empty_catalog(tmp_path) -> str:
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    return str(catalog_path)


def test_add_revision_creates_a_page_with_one_revision(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    revision = add_revision(catalog_path, "fact-1", leaf, "julian", "initial citation", False)

    history = get_history(catalog_path, "fact-1")
    assert len(history) == 1
    assert history[0].revision_id == revision.revision_id
    assert history[0].reference == to_json_dict(leaf)
    assert history[0].author == "julian"
    assert history[0].comment == "initial citation"
    assert history[0].is_correction is False


def test_add_revision_appends_a_second_revision_and_becomes_current(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "initial citation", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf_2, "julian", "corrected the citation", True)

    history = get_history(catalog_path, "fact-1")
    assert len(history) == 2
    assert history[1].revision_id == revision_2.revision_id
    assert history[1].is_correction is True

    current = get_current_revision(catalog_path, "fact-1")
    assert current.revision_id == revision_2.revision_id
    assert current.reference == to_json_dict(leaf_2)


def test_add_revision_preserves_other_pages(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first fact", False)
    add_revision(catalog_path, "fact-2", leaf_2, "julian", "second fact", False)

    assert len(get_history(catalog_path, "fact-1")) == 1
    assert len(get_history(catalog_path, "fact-2")) == 1
    assert get_current_revision(catalog_path, "fact-1").reference == to_json_dict(leaf_1)
    assert get_current_revision(catalog_path, "fact-2").reference == to_json_dict(leaf_2)


def test_get_current_revision_returns_none_for_untouched_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert get_current_revision(catalog_path, "never-touched") is None


def test_get_history_returns_empty_list_for_untouched_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert get_history(catalog_path, "never-touched") == []


def test_revision_ids_are_unique_across_calls(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    revision_1 = add_revision(catalog_path, "fact-1", leaf, "julian", "same args", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf, "julian", "same args", False)

    assert revision_1.revision_id != revision_2.revision_id


def test_add_revision_writes_pretty_printed_sorted_json_with_trailing_newline(tmp_path):
    catalog_path = Path(_empty_catalog(tmp_path))
    leaf_1 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    add_revision(catalog_path, "z-fact", leaf_1, "julian", "z", False)
    add_revision(catalog_path, "a-fact", leaf_2, "julian", "a", False)

    raw = catalog_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert "\n" in raw
    assert raw.index('"a-fact"') < raw.index('"z-fact"')

    # The raw file, re-parsed, matches json.dumps(<same content>, indent=2,
    # sort_keys=True) + "\n" exactly -- an exact structural check on
    # formatting, not a weak proxy, without needing to hand-predict the
    # dynamic revision_id/created_at values.
    parsed = json.loads(raw)
    reformatted = json.dumps(parsed, indent=2, sort_keys=True) + "\n"
    assert raw == reformatted


def test_add_revision_raises_when_catalog_file_does_not_exist(tmp_path):
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    missing_path = tmp_path / "does-not-exist.json"

    with pytest.raises(FileNotFoundError):
        add_revision(str(missing_path), "fact-1", leaf, "julian", "x", False)

    assert not missing_path.exists()


def test_add_revision_on_malformed_catalog_raises_without_writing(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("[]", encoding="utf-8")
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    with pytest.raises(CatalogLoadError):
        add_revision(str(catalog_path), "fact-1", leaf, "julian", "x", False)

    assert catalog_path.read_text(encoding="utf-8") == "[]"


def test_add_revision_leaves_original_file_intact_if_write_is_interrupted(tmp_path, monkeypatch):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first", False)
    before = Path(catalog_path).read_text(encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("simulated crash during rename")

    monkeypatch.setattr(catalog_module.os, "replace", _boom)

    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    with pytest.raises(OSError):
        add_revision(catalog_path, "fact-2", leaf_2, "julian", "second", False)

    after = Path(catalog_path).read_text(encoding="utf-8")
    assert after == before


def test_add_revision_leaves_no_leftover_temp_file(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    add_revision(catalog_path, "fact-1", leaf, "julian", "x", False)

    leftover = list(Path(tmp_path).glob("*.tmp"))
    assert leftover == []


def test_load_catalog_raises_catalog_load_error_on_malformed_json(tmp_path):
    catalog_path = tmp_path / "bad.json"
    catalog_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CatalogLoadError, match="not valid JSON"):
        load_catalog(str(catalog_path))


def test_load_catalog_raises_catalog_load_error_on_non_object_json(tmp_path):
    catalog_path = tmp_path / "array.json"
    catalog_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(CatalogLoadError, match="expected a JSON object"):
        load_catalog(str(catalog_path))


def test_list_pages_summarizes_every_page_with_correct_revision_count_and_current(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    add_revision(catalog_path, "fact-1", leaf_1, "julian", "first version", False)
    revision_2 = add_revision(catalog_path, "fact-1", leaf_2, "julian", "second version", True)
    add_revision(catalog_path, "fact-2", leaf_1, "julian", "only version", False)

    pages = list_pages(catalog_path)

    assert pages["fact-1"].revision_count == 2
    assert pages["fact-1"].current.revision_id == revision_2.revision_id
    assert pages["fact-2"].revision_count == 1


def test_list_pages_on_empty_catalog_returns_empty_dict(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    assert list_pages(catalog_path) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/references_catalog/test_catalog.py -v`
Expected: FAIL — every test errors on collection or fails, since
`add_revision`/`get_current_revision`/`get_history`/`list_pages` don't
exist yet in the current `references_catalog/catalog.py`
(`ImportError: cannot import name 'add_revision' from 'references_catalog.catalog'`).

- [ ] **Step 3: Replace the full contents of `references_catalog/catalog.py`**

```python
"""Reads and writes the references catalog: a page (fact_key) has an
ordered history of immutable revisions. See
docs/specs/2026-09-25-catalog-revision-history-design.md.
"""
from __future__ import annotations

import dataclasses
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class CatalogLoadError(Exception):
    pass


@dataclass(frozen=True)
class Revision:
    revision_id: str
    reference: dict
    author: str
    comment: str
    is_correction: bool
    created_at: str


@dataclass(frozen=True)
class PageSummary:
    revision_count: int
    current: Revision


def _revision_from_dict(data: dict) -> Revision:
    return Revision(
        revision_id=data["revision_id"],
        reference=data["reference"],
        author=data["author"],
        comment=data["comment"],
        is_correction=data["is_correction"],
        created_at=data["created_at"],
    )


def load_catalog(catalog_path: str | Path) -> dict:
    path = Path(catalog_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"{path}: not valid JSON") from e
    if not isinstance(raw, dict):
        raise CatalogLoadError(f"{path}: expected a JSON object")
    return raw


def add_revision(
    catalog_path: str | Path,
    fact_key: str,
    reference: Reference,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    path = Path(catalog_path)
    catalog = load_catalog(path)
    page = catalog.setdefault(fact_key, [])
    revision = Revision(
        revision_id=str(uuid.uuid4()),
        reference=to_json_dict(reference),
        author=author,
        comment=comment,
        is_correction=is_correction,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    page.append(dataclasses.asdict(revision))

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
    return revision


def get_current_revision(catalog_path: str | Path, fact_key: str) -> Revision | None:
    page = load_catalog(catalog_path).get(fact_key)
    if not page:
        return None
    return _revision_from_dict(page[-1])


def get_history(catalog_path: str | Path, fact_key: str) -> list[Revision]:
    page = load_catalog(catalog_path).get(fact_key, [])
    return [_revision_from_dict(r) for r in page]


def list_pages(catalog_path: str | Path) -> dict[str, PageSummary]:
    catalog = load_catalog(catalog_path)
    return {
        fact_key: PageSummary(revision_count=len(revisions), current=_revision_from_dict(revisions[-1]))
        for fact_key, revisions in catalog.items()
        if revisions
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/references_catalog/test_catalog.py -v`
Expected: PASS (15 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (167 tests: 166 previously passing, minus 14 replaced,
plus 15 new — net +1)

- [ ] **Step 6: Commit**

```bash
git add references_catalog/catalog.py tests/references_catalog/test_catalog.py
git commit -m "Redesign references_catalog.catalog around pages with revision history"
```

---

## Task 2: `webapp/app.py` (full rewrite)

**Files:**
- Modify: `webapp/app.py` (full rewrite)
- Modify: `tests/webapp/test_app.py` (full rewrite — the current file's
  4 tests all reference the removed `/api/references` endpoint and the
  old flat-reference catalog shape)

**Interfaces:**
- Consumes: `get_history`, `list_pages` (`references_catalog.catalog`,
  Task 1).
- Produces: `GET /api/pages` and `GET /api/pages/{fact_key}` on
  `webapp.app.app`. `GET /api/references` no longer exists.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/webapp/test_app.py`:

```python
from fastapi.testclient import TestClient

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision
from webapp.app import app

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def test_list_pages_endpoint_returns_empty_object_when_catalog_is_empty(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages")

    assert response.status_code == 200
    assert response.json() == {}


def test_list_pages_endpoint_returns_real_pages_built_via_add_revision(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(str(catalog_path), "fact-1", leaf, "julian", "initial", False)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages")

    assert response.status_code == 200
    body = response.json()
    assert body["fact-1"]["revision_count"] == 1
    assert body["fact-1"]["current"]["author"] == "julian"
    assert body["fact-1"]["current"]["comment"] == "initial"


def test_get_page_endpoint_returns_full_history_for_a_real_page(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    add_revision(str(catalog_path), "fact-1", leaf_1, "julian", "first", False)
    add_revision(str(catalog_path), "fact-1", leaf_1, "julian", "second", True)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages/fact-1")

    assert response.status_code == 200
    body = response.json()
    assert body["fact_key"] == "fact-1"
    assert len(body["history"]) == 2
    assert body["current"]["comment"] == "second"
    assert body["current"]["is_correction"] is True


def test_get_page_endpoint_returns_404_for_an_unknown_fact_key(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))

    client = TestClient(app)
    response = client.get("/api/pages/no-such-fact")

    assert response.status_code == 404


def test_list_pages_endpoint_returns_a_server_error_when_catalog_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "does-not-exist.json"))

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/pages")

    assert response.status_code == 500


def test_static_index_page_is_served_at_root():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_old_references_endpoint_no_longer_exists():
    client = TestClient(app)
    response = client.get("/api/references")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/webapp/test_app.py -v`
Expected: FAIL — `/api/pages` and `/api/pages/{fact_key}` don't exist yet
in the current `webapp/app.py` (each returns 404 against the *new*
tests' expectations of 200, and `test_old_references_endpoint_no_longer_exists`
itself currently fails since `/api/references` still exists and returns 200).

- [ ] **Step 3: Replace the full contents of `webapp/app.py`**

```python
"""Serves the references catalog as browsable pages with revision
history. See docs/specs/2026-09-25-catalog-revision-history-design.md.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from references_catalog.catalog import get_history, list_pages

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"

app = FastAPI()


def _catalog_path() -> Path:
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


@app.get("/api/pages")
def list_pages_endpoint() -> dict:
    pages = list_pages(_catalog_path())
    return {
        fact_key: {
            "revision_count": summary.revision_count,
            "current": dataclasses.asdict(summary.current),
        }
        for fact_key, summary in pages.items()
    }


@app.get("/api/pages/{fact_key}")
def get_page(fact_key: str) -> dict:
    history = get_history(_catalog_path(), fact_key)
    if not history:
        raise HTTPException(status_code=404, detail=f"No such page: {fact_key!r}")
    return {
        "fact_key": fact_key,
        "current": dataclasses.asdict(history[-1]),
        "history": [dataclasses.asdict(r) for r in history],
    }


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (170 tests: 167 from Task 1, minus 4 replaced, plus 7 new
— net +3)

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/webapp/test_app.py
git commit -m "Redesign webapp: GET /api/pages and GET /api/pages/{fact_key}, /api/references removed"
```

---

## Task 3: `webapp/static/index.html` (full rewrite) + manual verification

**Files:**
- Modify: `webapp/static/index.html` (full rewrite)

**Interfaces:**
- Consumes: `GET /api/pages`, `GET /api/pages/{fact_key}` (Task 2), via
  the browser's own `fetch()`.
- Produces: nothing new for other code — this is the leaf of the stack.

No automated test for this file, per this project's own established
convention (no frontend test runner). The completion gate is the manual
verification in Steps 3-6 below, which is required, not optional.

- [ ] **Step 1: Replace the full contents of `webapp/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MiKaDiv-FM References</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    th { background: #f0f0f0; }
    #empty, #error { color: #666; font-style: italic; }
    .correction { color: #a00; font-weight: bold; }
    a { color: #06c; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1><a href="/">MiKaDiv-FM References</a></h1>
  <div id="content">Loading...</div>
  <script>
    function cell(text) {
      const td = document.createElement("td");
      td.textContent = text;
      return td;
    }

    function renderError(message) {
      const content = document.getElementById("content");
      content.innerHTML = "";
      const p = document.createElement("p");
      p.id = "error";
      p.textContent = message;
      content.appendChild(p);
    }

    function renderIndex(pages) {
      const content = document.getElementById("content");
      const factKeys = Object.keys(pages);
      content.innerHTML = "";
      if (factKeys.length === 0) {
        const p = document.createElement("p");
        p.id = "empty";
        p.textContent = "No pages yet.";
        content.appendChild(p);
        return;
      }
      const table = document.createElement("table");
      table.innerHTML = "<thead><tr><th>Page</th><th>Family</th><th>Selector type</th><th>Revisions</th></tr></thead>";
      const tbody = document.createElement("tbody");
      factKeys.forEach((factKey) => {
        const page = pages[factKey];
        const reference = page.current.reference;
        const family = reference.subject_document ? reference.subject_document.family : "";
        const selectorType = reference.selector ? reference.selector.type : "";
        const row = document.createElement("tr");
        const linkCell = document.createElement("td");
        const link = document.createElement("a");
        link.href = `?page=${encodeURIComponent(factKey)}`;
        link.textContent = factKey;
        linkCell.appendChild(link);
        row.appendChild(linkCell);
        [family, selectorType, String(page.revision_count)].forEach((value) => row.appendChild(cell(value)));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      content.appendChild(table);
    }

    function renderPage(factKey, page) {
      const content = document.getElementById("content");
      content.innerHTML = "";

      const heading = document.createElement("h2");
      heading.textContent = factKey;
      content.appendChild(heading);

      const reference = page.current.reference;
      const summary = document.createElement("p");
      const family = reference.subject_document ? reference.subject_document.family : "";
      const selectorType = reference.selector ? reference.selector.type : "";
      summary.textContent = `${family} / ${selectorType} / ${reference.reference_id || ""}`;
      content.appendChild(summary);

      const historyHeading = document.createElement("h3");
      historyHeading.textContent = "History";
      content.appendChild(historyHeading);

      const table = document.createElement("table");
      table.innerHTML = "<thead><tr><th>When</th><th>Author</th><th>Comment</th></tr></thead>";
      const tbody = document.createElement("tbody");
      [...page.history].reverse().forEach((revision) => {
        const row = document.createElement("tr");
        row.appendChild(cell(revision.created_at));
        row.appendChild(cell(revision.author));
        const commentCell = cell(revision.is_correction ? `[correction] ${revision.comment}` : revision.comment);
        if (revision.is_correction) {
          commentCell.classList.add("correction");
        }
        row.appendChild(commentCell);
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      content.appendChild(table);
    }

    const params = new URLSearchParams(window.location.search);
    const factKey = params.get("page");

    if (factKey) {
      fetch(`/api/pages/${encodeURIComponent(factKey)}`)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
          }
          return response.json();
        })
        .then((page) => renderPage(factKey, page))
        .catch((error) => renderError(`Failed to load this page: ${error.message}`));
    } else {
      fetch("/api/pages")
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
          }
          return response.json();
        })
        .then(renderIndex)
        .catch((error) => renderError(`Failed to load the page index: ${error.message}`));
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Run the full test suite (confirm the rewrite broke nothing automated)**

Run: `pytest tests/ -v`
Expected: PASS (170 tests — unchanged from Task 2; this task adds no
automated tests)

- [ ] **Step 3: Commit**

```bash
git add webapp/static/index.html
git commit -m "Redesign webapp UI: browsable page index + per-page view with revision history"
```

- [ ] **Step 4: Manual verification — empty state**

```bash
cd /work/generator
nohup uvicorn webapp.app:app --host 0.0.0.0 --port 8012 > /tmp/webapp-revision.log 2>&1 &
disown
sleep 2
curl -s http://localhost:8012/api/pages
```

Expected: `{}` (the real committed catalog from before). Then use
Playwright to load `http://localhost:8012/` and confirm the page shows
"No pages yet." — not stuck on "Loading...", not blank.

- [ ] **Step 5: Manual verification — populated state, with a real correction**

```bash
cp /work/ontologies/mikadiv-fm/references.json /tmp/references-backup.json
python3 -c "
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision

subject_document = SubjectDocument(
    family='MiKaDiv_FM_Meldeart23',
    version='1.02',
    retrieval_uri='/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd',
)
aordnr_xpath = (
    \"/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']\"
    \"/xs:sequence/xs:element[@name='AOrdNr']\"
)
abgef_xpath = (
    \"/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent\"
    \"/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']\"
)
leaf_1 = cite(subject_document, XPathSelector.create(aordnr_xpath))
leaf_2 = cite(subject_document, XPathSelector.create(abgef_xpath))
add_revision('/work/ontologies/mikadiv-fm/references.json', 'aordnr-demo', leaf_1, 'julian', 'initial citation', False)
add_revision('/work/ontologies/mikadiv-fm/references.json', 'aordnr-demo', leaf_2, 'julian', 'fixed the citation', True)
add_revision('/work/ontologies/mikadiv-fm/references.json', 'second-page-demo', leaf_1, 'julian', 'only version', False)
print('seeded')
"
curl -s http://localhost:8012/api/pages
```

Expected: `seeded`, then a real JSON object with two pages
(`aordnr-demo` with `revision_count: 2`, `second-page-demo` with
`revision_count: 1`). Then via Playwright: load `http://localhost:8012/`
and confirm the index table lists both pages with the correct revision
counts; navigate to `http://localhost:8012/?page=aordnr-demo` and
confirm the History table shows two rows, the second one visibly marked
as a correction (the `.correction` CSS class / `[correction]` prefix),
newest first.

- [ ] **Step 6: Revert the temporary demo data and stop the server**

```bash
cp /tmp/references-backup.json /work/ontologies/mikadiv-fm/references.json
rm /tmp/references-backup.json
cd /work/ontologies && git status
pkill -f "uvicorn webapp.app"
```

Expected: `git status` shows a clean working tree — the demo edit is
fully reverted, matching the committed `{}` exactly. Confirm the
`uvicorn` process is stopped (`curl` to port 8012 fails to connect).

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `references_catalog/catalog.py` implements `Revision`,
  `PageSummary`, `CatalogLoadError`, `load_catalog()`, `add_revision()`,
  `get_current_revision()`, `get_history()`, and `list_pages()` with the
  semantics above. `save_reference()`/`DuplicateFactKeyError` no longer
  exist.
- [ ] `webapp/app.py` serves `GET /api/pages` and
  `GET /api/pages/{fact_key}` (`GET /api/references` removed).
- [ ] `webapp/static/index.html` renders both the page index and a
  page-detail view with visible revision history, manually verified in a
  real browser.
- [ ] All automated tests pass: `pytest tests/ -v` → 170 passed.
- [ ] The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}`.
