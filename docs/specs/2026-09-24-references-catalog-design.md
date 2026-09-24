# References Catalog — Design

## Context

This is the first slice of the reference-model spec's 4th and last
original Roadmap item (`docs/specs/2026-09-23-source-reference-model-design.md`,
item 4: "the actual process that walks the real XSD/PDF sources and calls
`cite()` to build facts and their `Reference`s"), approached surgically
per explicit direction: rather than attempting automatic discovery of what
needs citing, or even a manual add-path, this sub-project builds only the
**read-side skeleton** — a plain, git-committed catalog file for
`Reference`s, and a minimal UI to view it. Both discovery (deciding what
to cite) and the write-path (adding a `Reference` to the catalog) are
explicitly deferred to later sub-projects.

Consistent with how this project already treats persistence everywhere
else (corpus versions, review records): a `Reference` is just data, so it
gets serialized to a plain file and committed to git — no database, no
store abstraction.

## Non-Goals

- **Not** an extraction/discovery pipeline. Nothing here decides what
  needs citing or walks the XSD/PDF sources to find candidates.
- **Not** a write-path. Nothing here adds a `Reference` to the catalog.
  The catalog starts, and for the duration of this sub-project remains,
  `{}`.
- **Not** a deserializer back into typed `Leaf`/`Union` objects. The UI
  displays raw JSON fields; nothing here needs to reconstruct a real
  `Reference` from the catalog.
- **Not** the interaction layer named in `review_recording`'s/
  `review_consultation`'s own Roadmaps (collecting a verdict, calling
  `record_review()`). This is a read-only listing of citations, not a
  review workflow.
- **Not** drift status. This UI shows what's cited, not whether it's
  currently healthy or flagged — that would mean running a real
  `sweep()` against the catalog, which is real, useful, later work.

## Catalog file

`ontologies/mikadiv-fm/references.json` — same real, git-tracked-history
convention as `sources/` and `reviews/` in that repo. Shape: a JSON object
mapping `fact_key` (a plain string, the same key concept `sweep()` already
uses) to a serialized `Reference`:

```json
{}
```

Starts as `{}`, committed as part of this sub-project. No code in this
sub-project, or any consumer yet, ever writes to it after that initial
commit.

## Serialization

New module, `reference_model/serialize.py`:

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

Confirmed live: every selector type (`XPathSelector`, `SvgSelector`,
`JsonSelector`) is a flat dataclass of `str`/`int` fields only —
`SvgSelector`'s `shapely.Polygon` is constructed on demand inside its own
`polygon()` method, never stored as a field — so `dataclasses.asdict()` is
already fully JSON-safe for both `Leaf` and `Union`, recursively, with
zero special-casing needed anywhere in this function. It exists to give
the catalog's JSON shape one canonical, tested source of truth (rather
than "`asdict()` happens to produce something reasonable, undocumented"),
and so this sub-project's own UI tests can build a realistic fixture from
a real `cite()` call rather than hand-typed JSON that could silently drift
from what real code actually produces.

Deliberately **not** round-tripped: no `from_json_dict()`. Nothing in this
sub-project, or any consumer yet, needs to reconstruct a typed
`Leaf`/`Union` from catalog JSON — the UI only ever displays raw fields.

## UI

New top-level directory `webapp/` (the old `webapp/` from before this
session's from-scratch reset was fully deleted; this is unrelated, new
code). A minimal FastAPI backend, one endpoint, plus one static HTML page
with vanilla JS — no build step, no frontend framework, since a read-only
table over a JSON object doesn't need one.

`webapp/app.py`:

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

`webapp/static/index.html` — fetches `/api/references` and renders a
table of `fact_key` / `family` / selector `type` / `reference_id`, one row
per entry; an explicit, honest message ("No references yet.") when the
object is empty, not a blank page a viewer might mistake for a loading
failure.

Run via the `generator-webapp` port 8012 slot already reserved for this
exact project in `cloud-admin-box`'s own config:
`uvicorn webapp.app:app --host 0.0.0.0 --port 8012` (backgrounded via
`nohup ... & disown`, matching the box's established ad hoc demo-server
pattern).

## New dependencies

`fastapi` and `uvicorn`, added to `pyproject.toml`'s main `dependencies`
since they're needed to actually run the UI, not just to test it. `httpx`
is needed only by FastAPI's own `TestClient` (used in this sub-project's
backend tests) — nothing in `webapp/app.py` itself imports it — so it goes
in the `dev` extra instead, alongside `pytest`/`reportlab`.

## Testing strategy

Backend endpoint, tested via `fastapi.testclient.TestClient` against a
real `tmp_path` file (never the real committed catalog, whose content is
free to grow in later sub-projects without invalidating these tests):

- The endpoint returns `{}` with a 200 when the catalog file's real
  content is `{}`.
- The endpoint returns the catalog's exact real content when populated
  with a hand-written fixture object (a plain dict, not built via
  `cite()` — this test is about the HTTP layer, not serialization).

Serialization, tested against real `cite()` calls (the same real
MiKaDiv-FM elements already used throughout this session's tests):

- `to_json_dict()` on a real `Leaf` produces a dict whose `reference_id`,
  `content_hash`, `subject_document`, and `selector` fields match the
  `Leaf`'s own real attribute values, and the whole result survives a
  real `json.dumps()`/`json.loads()` round-trip unchanged.
- `to_json_dict()` on a real `Union` (via `cite_union()`) produces a dict
  with a `parts` key holding a list of two dicts, each shaped exactly
  like a `Leaf`'s own `to_json_dict()` output.

The static HTML/JS page has no automated test in this sub-project (this
project has no frontend test runner, and one page rendering a table over
one JSON object doesn't justify introducing one) — verified manually, in
a real browser via the reserved port, once implementation is done,
covering both the empty-catalog state and a state with real fixture data
temporarily written to the real catalog path for the check and then
reverted.

## Roadmap: what this enables next

The real, natural next questions, all still open:

- **The write-path.** A `save_reference(catalog_path, fact_key, reference)`
  function that actually appends to the committed catalog file — the
  smallest next slice, and the one this sub-project deliberately stops
  short of.
- **The extraction/discovery pipeline itself** — deciding *what* needs
  citing from the real XSD/PDF sources in the first place, the original
  Roadmap item this sub-project only takes the first surgical step
  toward.
- **Drift status in the UI.** Once the catalog has real content, running
  a real `sweep()`/`summarize_for_review()` against it and showing
  healthy/flagged status per entry, not just the bare citation.
- **Search/filter** once the catalog is large enough that a flat table
  stops being usable.

## Definition of Done

- `ontologies/mikadiv-fm/references.json` exists, is committed, and
  contains exactly `{}`.
- `reference_model/serialize.py`'s `to_json_dict()` is implemented and
  tested with the semantics above.
- `webapp/app.py`'s `GET /api/references` endpoint is implemented,
  configurable via `REFERENCES_CATALOG_PATH`, and tested with the
  semantics above.
- `webapp/static/index.html` renders the catalog with an honest empty
  state, manually verified in a real browser via port 8012.
- All automated tests pass.
