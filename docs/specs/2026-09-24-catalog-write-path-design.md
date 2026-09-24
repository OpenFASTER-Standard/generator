# Catalog Write-Path — Design

## Context

This is the next slice after `references_catalog`
(`docs/specs/2026-09-24-references-catalog-design.md`), whose own Roadmap
named this as the smallest next step: a way to actually add an entry to
the committed references catalog. Everything else that sub-project
deferred — deciding what to cite, drift status, search/filter — remains
deferred here too; this sub-project only builds the mechanical,
one-at-a-time write operation.

## Non-Goals

- **Not** a discovery/extraction pipeline. Nothing here decides what
  needs citing.
- **Not** a deserializer into typed `Leaf`/`Union` objects. `load_catalog()`
  returns the same raw JSON shape `webapp/app.py` already reads today —
  reconstructing typed `Reference`s is still deferred to whenever
  drift-status integration is designed.
- **Not** concurrency-safe. A read-modify-write race between two
  concurrent `save_reference()` calls is unhandled, consistent with how
  this project already treats `reviews_dir` (a single-operator tool, not
  a multi-writer service).
- **Not** a git integration. `save_reference()` only writes the catalog
  file to disk. Committing (and pushing) that change to the `ontologies`
  repo remains a separate, human-directed action — the same separation
  `record_review()` already established for review documents.
- **Not** seeding the real committed catalog with real content. This
  sub-project's own Definition of Done leaves the real
  `ontologies/mikadiv-fm/references.json` exactly as `references_catalog`
  left it: `{}`. Using `save_reference()` for real is later work.
- **Not** an "update" operation. Calling `save_reference()` for a
  `fact_key` that already exists is a mistake, not a re-citation — it
  raises rather than silently replacing what's there (settled during
  brainstorming; see Roadmap below for why an explicit update operation
  is real, foreseeable, future work, not this).

## `references_catalog/catalog.py`

New top-level package — `references_catalog/` — since "a persisted
catalog of many references keyed by `fact_key`" is a genuinely distinct
concept `reference_model` doesn't otherwise model (it only knows how to
build and check one `Reference` at a time).

```python
"""Reads and writes the references catalog file. See
docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class DuplicateFactKeyError(Exception):
    pass


class CatalogLoadError(Exception):
    pass


def load_catalog(catalog_path: str | Path) -> dict:
    path = Path(catalog_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"{path}: not valid JSON") from e
    if not isinstance(raw, dict):
        raise CatalogLoadError(f"{path}: expected a JSON object")
    return raw


def save_reference(catalog_path: str | Path, fact_key: str, reference: Reference) -> None:
    path = Path(catalog_path)
    catalog = load_catalog(path)
    if fact_key in catalog:
        raise DuplicateFactKeyError(f"{fact_key!r} already exists in {path}")
    catalog[fact_key] = to_json_dict(reference)

    # Write to a sibling temp file, then rename over the target -- os.replace()
    # is atomic on POSIX, so a process killed mid-write leaves the original
    # file untouched rather than truncated or partially written.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
```

`load_catalog()` validates that the parsed JSON is genuinely an object
(mirroring `staleness_sweep`'s `CorpusIntegrityError` and
`review_consultation`'s `ReviewLoadError`, both already established
precedents in this project for exactly this check) — without it, a
truncated or hand-edited catalog file produces a bare `TypeError` from
deep inside dict-subscript code instead of a typed, readable error naming
the actual problem file.

`save_reference()` requires the catalog file to already exist — true by
construction, since `references_catalog`'s own Definition of Done
guarantees it — and lets a missing file raise `FileNotFoundError`
naturally rather than defensively handling a case that shouldn't occur
(consistent with `webapp/app.py`'s own endpoint already treating a
missing catalog as a loud 500, not a silently-invented `{}`).

Written with `indent=2, sort_keys=True`: the committed file starts as the
2-byte `{}` (no formatting at all, per the previous sub-project), but
every write after the first real entry pretty-prints it. This is a
deliberate choice, not an incidental one — the catalog is meant to be
read via `git diff`/`git log` like every other real artifact in this
project, and an unsorted, unindented JSON blob makes that unreadable the
moment it has more than one key. `sort_keys=True` also keeps the diff for
adding one new key to an N-key catalog a clean one-entry insertion,
regardless of the order entries happened to be added in.

The write itself goes through a sibling `.tmp` file plus `os.replace()`
rather than a direct `Path.write_text()` — `write_text()` truncates its
target before writing, so a process killed mid-write (an interrupted
Ctrl-C, an OOM kill) would leave the real catalog empty or partially
written; `os.replace()` is atomic on POSIX, so the original file is either
fully replaced or untouched, never caught in between.

## Refactor: `webapp/app.py` calls into this module

`webapp/app.py`'s endpoint currently does its own inline
`json.loads(path.read_text(encoding="utf-8"))`. Replaced with a call to
`load_catalog()`, so read logic lives in exactly one place instead of
being duplicated between the module that reads the catalog for display
and the one that now reads-then-writes it:

```python
from references_catalog.catalog import load_catalog

@app.get("/api/references")
def list_references() -> dict:
    return load_catalog(_catalog_path())
```

This is a pure refactor — every existing `webapp` test (empty catalog,
populated catalog, missing file → 500, static page at `/`) must keep
passing unchanged, proving the refactor didn't alter behavior.

## Testing strategy

Dogfooded via real `cite()` calls, matching the established pattern:

- `save_reference()` writes a real `cite()`'d `Leaf` into a `tmp_path`
  catalog file; `load_catalog()` on the same path returns a dict whose
  entry matches `to_json_dict(leaf)` exactly.
- Calling `save_reference()` twice with the same `fact_key` raises
  `DuplicateFactKeyError`; the catalog file's content is unchanged after
  the rejected second call — a reasonable person would not expect a
  rejected write to truncate or corrupt what was already there.
- `save_reference()` for a second, different `fact_key` against the same
  catalog file preserves the first entry — a reasonable person adding one
  new fact would not expect it to silently erase everything else already
  in the catalog.
- `load_catalog()` on a real catalog with multiple entries returns all of
  them.
- `webapp`'s `GET /api/references` endpoint, re-tested through the
  refactored `load_catalog()` call, still behaves identically for the
  empty/populated/missing-file cases already established in the previous
  sub-project — pinning that the refactor changed no behavior.

## Roadmap: what this enables next

- The interaction layer / an eventual discovery pipeline can now call
  `save_reference()` for real, growing the committed catalog one entry at
  a time.
- Once the catalog has real content, **drift-status integration**
  (running `sweep()` against catalog entries) becomes the natural next
  question — which will need a real deserializer back into typed
  `Reference` objects, still not built anywhere in this project.
- An explicit **update operation** (deliberately replacing an existing
  `fact_key`'s citation, e.g. because a schema restructure moved the
  cited element) is real, foreseeable future work once facts actually
  need re-citing — out of scope here per this sub-project's own
  "refuse if it exists" ruling.

## Definition of Done

- `references_catalog/catalog.py` implements `load_catalog()`,
  `save_reference()`, and `DuplicateFactKeyError` with the semantics
  above.
- `webapp/app.py`'s endpoint is refactored to call `load_catalog()`
  instead of its own inline JSON parsing, with all of its existing tests
  still passing unchanged.
- All tests listed above pass.
- The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}` — this sub-project builds a capability, it does not use it
  for real.
