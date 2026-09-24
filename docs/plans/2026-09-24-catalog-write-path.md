# Catalog Write-Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `references_catalog/catalog.py` from
`docs/specs/2026-09-24-catalog-write-path-design.md`: a mechanical,
add-only way to write one entry into the committed references catalog,
plus refactor `webapp/app.py` to read through the same module instead of
duplicating JSON-loading logic.

**Architecture:** One new small module (`load_catalog()`/`save_reference()`/
`DuplicateFactKeyError`) built on top of `reference_model.serialize`
(already merged), plus a pure, behavior-preserving refactor of the one
existing consumer of catalog-reading logic.

**Tech Stack:** Python 3.11, stdlib only, plus `reference_model` (already
merged to `main`).

**Spec:** `docs/specs/2026-09-24-catalog-write-path-design.md`

## Global Constraints

- `save_reference()` **raises `DuplicateFactKeyError`** (never silently
  overwrites) if `fact_key` already exists in the catalog.
- Catalog writes use `json.dumps(catalog, indent=2, sort_keys=True)` —
  pretty-printed and key-sorted, deliberately, so a future `git diff`
  adding one entry stays a small, readable diff regardless of insertion
  order.
- Neither `load_catalog()` nor `save_reference()` performs any git
  operation. Writing to disk and committing stay separate, matching
  `record_review()`'s own established precedent.
- `save_reference()` assumes the catalog file already exists; a missing
  file raises `FileNotFoundError` naturally — not handled defensively,
  matching `webapp/app.py`'s own existing "missing catalog → loud 500,
  never a silently-invented `{}`" behavior.
- The real committed `ontologies/mikadiv-fm/references.json` is never
  touched by this plan — every test in this plan operates against a
  `tmp_path` fixture, never the real file.
- The `webapp/app.py` refactor must be a **pure refactor**: all 4 existing
  tests in `tests/webapp/test_app.py` must keep passing completely
  unchanged, proving no observable behavior changed.

## Review Focus

- **A rejected duplicate-key write must leave the catalog file
  byte-for-byte unchanged**, not truncated or partially written. A
  reasonable person would be alarmed if a mistaken duplicate save
  corrupted real, already-saved data instead of cleanly failing. Tested
  directly in Task 1.
- **Adding a second fact must preserve the first fact's entry exactly.**
  A reasonable person adding one new citation would not expect it to
  silently erase unrelated existing entries. Tested directly in Task 1.
- **The webapp refactor must change zero observable behavior** across all
  4 of its existing scenarios (empty catalog, populated catalog, missing
  file → 500, static page at `/`). A reasonable person reviewing a
  "just a refactor" commit would expect identical test output before and
  after, not a behavior change discovered later in production. Verified
  directly in Task 2 by re-running the same, unmodified test file.
- **The catalog's pretty-printed, sorted-key output.** A reasonable
  person reviewing a future `git diff` of this file would expect adding
  one entry to show up as a small, readable insertion — not a
  single-line reformat of the entire file that makes every future
  addition look like a full-file rewrite. Tested directly in Task 1 by
  asserting sorted key order and multi-line formatting.
- **`save_reference()` against a catalog path that doesn't exist.** A
  reasonable person misconfiguring the path would expect an immediate,
  clear `FileNotFoundError` — not a silently-created new catalog file
  that discards the assumption "this path is git-tracked, real content
  already exists here." Tested directly in Task 1.

---

## Task 1: `references_catalog/catalog.py`

**Files:**
- Create: `references_catalog/__init__.py`
- Create: `references_catalog/catalog.py`
- Create: `tests/references_catalog/__init__.py`
- Test: `tests/references_catalog/test_catalog.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `Reference` (`reference_model.model`, already merged);
  `to_json_dict` (`reference_model.serialize`, already merged); `cite`
  (`reference_model.cite`, already merged); `XPathSelector`
  (`reference_model.selectors.xpath_selector`, already merged).
- Produces: `load_catalog(catalog_path: str) -> dict`,
  `save_reference(catalog_path: str, fact_key: str, reference: Reference) -> None`,
  `DuplicateFactKeyError` (exception class).

- [ ] **Step 1: Create the package skeletons**

`references_catalog/__init__.py`:

```python
"""Reads and writes the references catalog file. See
docs/specs/2026-09-24-catalog-write-path-design.md.
"""
```

`tests/references_catalog/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/references_catalog/test_catalog.py`:

```python
import json
from pathlib import Path

import pytest

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import DuplicateFactKeyError, load_catalog, save_reference

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


def test_save_reference_writes_a_real_leaf(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    save_reference(catalog_path, "fact-1", leaf)

    catalog = load_catalog(catalog_path)
    assert catalog == {"fact-1": to_json_dict(leaf)}


def test_save_reference_raises_on_duplicate_fact_key(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    save_reference(catalog_path, "fact-1", leaf)

    with pytest.raises(DuplicateFactKeyError):
        save_reference(catalog_path, "fact-1", leaf)


def test_save_reference_duplicate_rejection_leaves_file_byte_for_byte_unchanged(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    save_reference(catalog_path, "fact-1", leaf)
    before = Path(catalog_path).read_text(encoding="utf-8")

    with pytest.raises(DuplicateFactKeyError):
        save_reference(catalog_path, "fact-1", leaf)

    after = Path(catalog_path).read_text(encoding="utf-8")
    assert after == before


def test_save_reference_preserves_existing_entries_when_adding_a_new_one(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))

    save_reference(catalog_path, "fact-1", leaf_1)
    save_reference(catalog_path, "fact-2", leaf_2)

    catalog = load_catalog(catalog_path)
    assert catalog == {"fact-1": to_json_dict(leaf_1), "fact-2": to_json_dict(leaf_2)}


def test_load_catalog_returns_all_entries_from_a_hand_written_multi_entry_catalog(tmp_path):
    fixture = {
        "fact-a": {"reference_id": "aaa"},
        "fact-b": {"reference_id": "bbb"},
    }
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps(fixture), encoding="utf-8")

    assert load_catalog(str(catalog_path)) == fixture


def test_save_reference_writes_pretty_printed_sorted_json(tmp_path):
    catalog_path = _empty_catalog(tmp_path)
    leaf_1 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    save_reference(catalog_path, "z-fact", leaf_1)
    save_reference(catalog_path, "a-fact", leaf_2)

    raw = Path(catalog_path).read_text(encoding="utf-8")
    assert "\n" in raw  # pretty-printed, not a single line
    assert raw.index('"a-fact"') < raw.index('"z-fact"')  # sorted regardless of insertion order


def test_save_reference_raises_when_catalog_file_does_not_exist(tmp_path):
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    with pytest.raises(FileNotFoundError):
        save_reference(str(tmp_path / "does-not-exist.json"), "fact-1", leaf)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/references_catalog/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'references_catalog.catalog'`

- [ ] **Step 4: Implement `references_catalog/catalog.py`**

```python
"""Reads and writes the references catalog file. See
docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class DuplicateFactKeyError(Exception):
    pass


def load_catalog(catalog_path: str) -> dict:
    return json.loads(Path(catalog_path).read_text(encoding="utf-8"))


def save_reference(catalog_path: str, fact_key: str, reference: Reference) -> None:
    catalog = load_catalog(catalog_path)
    if fact_key in catalog:
        raise DuplicateFactKeyError(f"{fact_key!r} already exists in {catalog_path}")
    catalog[fact_key] = to_json_dict(reference)
    Path(catalog_path).write_text(
        json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/references_catalog/test_catalog.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Register the new package**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` section:

```toml
[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*", "webapp*", "references_catalog*"]
```

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
```

Expected: installs successfully (metadata-only update, no new
third-party dependency).

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (146 tests: 139 previously passing, plus 7 new)

- [ ] **Step 8: Commit**

```bash
git add references_catalog/ tests/references_catalog/ pyproject.toml
git commit -m "Add references_catalog.catalog: load_catalog()/save_reference(), add-only"
```

---

## Task 2: Refactor `webapp/app.py` to use `load_catalog()`

**Files:**
- Modify: `webapp/app.py`
- Test: `tests/webapp/test_app.py` (unchanged — used as the refactor's
  regression check, not edited)

**Interfaces:**
- Consumes: `load_catalog(catalog_path: str) -> dict` (Task 1).
- Produces: no change to `webapp.app.app`'s route or observable
  behavior — `list_references()`'s body changes, its contract does not.

This is a pure refactor. There is no new behavior to write a failing test
for; the existing 4 tests already fully specify what must keep working.
The task's own gate is: identical pass/fail results before and after.

- [ ] **Step 1: Confirm the existing tests currently pass (baseline)**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS (4 tests) — this is the pre-refactor baseline; none of
these tests are modified by this task.

- [ ] **Step 2: Implement the refactor**

Replace the full contents of `webapp/app.py`:

```python
"""Serves the references catalog: one JSON API endpoint, one static page
that renders it. See docs/specs/2026-09-24-references-catalog-design.md
and docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from references_catalog.catalog import load_catalog

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


@app.get("/api/references")
def list_references() -> dict:
    return load_catalog(str(_catalog_path()))


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
```

Note `import json` is removed — nothing in this file calls `json.loads`
directly anymore; that logic now lives entirely in
`references_catalog.catalog.load_catalog()`.

- [ ] **Step 3: Run tests to verify they still pass, unchanged**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS (4 tests) — the exact same 4 test names as Step 1, all
still passing, proving the refactor changed no observable behavior.

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (146 tests — unchanged from Task 1's count; this task adds
no new tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py
git commit -m "Refactor webapp: read the catalog through references_catalog.catalog.load_catalog()"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `references_catalog/catalog.py` implements `load_catalog()`,
  `save_reference()`, and `DuplicateFactKeyError` with the semantics
  above.
- [ ] `webapp/app.py`'s endpoint is refactored to call `load_catalog()`
  instead of its own inline JSON parsing, with all of its existing tests
  still passing unchanged.
- [ ] All tests pass: `pytest tests/ -v` → 146 passed.
- [ ] The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}` — untouched by any test or step in this plan.
