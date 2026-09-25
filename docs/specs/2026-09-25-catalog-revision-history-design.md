# Catalog Revision History — Design

## Context

The references catalog's write-path (`docs/specs/2026-09-24-catalog-write-path-design.md`)
deliberately made `save_reference()` add-only: it raises
`DuplicateFactKeyError` if a `fact_key` already exists. That was the right
call for the smallest possible next slice at the time, but it makes the
catalog fundamentally write-once — a `fact_key`'s citation can never be
corrected or updated once set.

This redesigns the catalog around the model that actually makes Wikipedia
(and every other collaboratively-edited reference work) function: a
**page** (a `fact_key`) has an ordered history of **revisions**, each
immutable once written. Browsable pages, edit history, and "live edits,
patrolled afterward" (already how this project's own staleness-sweep +
review pipeline works — drift is caught *after* the fact, not gated
before) all fall out of this one structure. This is a full redesign of
`references_catalog/catalog.py` and `webapp/`, not a bolt-on: nothing
built earlier in this project is legacy to preserve compatibility with,
including this specific module, built one sub-project ago.

Also settled during brainstorming, after researching real prior art from
outside software (NATO intelligence tradecraft, US military technical
publication management, structured after-action review): most of what
was researched doesn't fit here yet, but one piece does. See below.

## Non-Goals

- **Not** an edit *form* / interaction layer. `add_revision()` is still
  called programmatically; nothing here builds a UI for submitting a new
  revision. Named repeatedly across this project's Roadmaps as separate,
  later work.
- **Not** Talk-page-style discussion. A real, natural later extension
  (a page in a different "namespace," using this exact same revision
  mechanism) — not designed here.
- **Not** diffing between revisions. The history view lists revisions
  with their metadata (author, comment, timestamp); it doesn't render
  what changed in the cited content between two revisions.
- **Not** source-reliability tracking (researched: NATO's Admiralty Code,
  a two-axis source-reliability/information-credibility rating). This
  needs real accumulated review history to mean anything, and this
  project has recorded zero real reviews against real data yet —
  building a reliability tracker now would be statistics with no real
  inputs. Revisit once real review history exists.
- **Not** a Union corroboration-independence check (researched:
  intelligence tradecraft's requirement that corroboration be genuinely
  independent, not the same source counted twice). Real and
  well-motivated, but a `reference_model`-level change to `cite_union()`,
  unrelated to the catalog/webapp this design touches. A separate future
  sub-project.
- **Not** AAR-structured reasoning (researched: the military
  after-action-review's four-question debrief format, as a richer
  alternative to a single free-text field). Real and well-motivated, but
  a `review_recording` document-shape change, a different module than
  this design touches. A separate future sub-project.
- **Not** a "revert to a previous revision" operation. A real Wikipedia
  feature, but meaningless without an edit UI to trigger it from.
- **Not** a real-data migration. The real committed
  `ontologies/mikadiv-fm/references.json` is still exactly `{}`, so this
  format change needs no migration.

## What was adopted from the military research

One idea survived contact with "does this need data we don't have, or
belong to a module we're not touching": **US Air Force technical-order
practice distinguishes types of update** (a full Revision vs. a smaller
Change vs. an urgent Interim/Rapid Action Change, later folded into or
rescinded by the next formal revision). The full apparatus doesn't fit —
there's no urgent/provisional workflow anywhere in this project to hang
a Rapid-Action-Change concept off of. But the *simplest* piece of it —
distinguishing "this edit fixes a previous mistake" from "this is a
routine update" — is cheap, real, and immediately useful for a history
view, the same way Wikipedia's own "minor edit" checkbox and Git's
`fix:` commit convention both encode the same distinction. Adopted as
one boolean field, `is_correction`, on every revision. "First revision"
vs. "later edit" needs no separate field — that's just list position.

## `references_catalog/catalog.py` (full redesign)

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
    try:
        return Revision(
            revision_id=data["revision_id"],
            reference=data["reference"],
            author=data["author"],
            comment=data["comment"],
            is_correction=data["is_correction"],
            created_at=data["created_at"],
        )
    except KeyError as e:
        raise CatalogLoadError(f"revision is missing field {e}") from e


def load_catalog(catalog_path: str | Path) -> dict:
    path = Path(catalog_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"{path}: not valid JSON") from e
    if not isinstance(raw, dict):
        raise CatalogLoadError(f"{path}: expected a JSON object")
    for fact_key, value in raw.items():
        if not isinstance(value, list):
            raise CatalogLoadError(
                f"{path}: {fact_key!r} is not a revision list "
                "(pre-revision-history catalog format?)"
            )
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

    # Write to a sibling temp file, then rename over the target -- os.replace()
    # is atomic on POSIX, so a process killed mid-write leaves the original
    # file untouched rather than truncated or partially written. If the write
    # or rename itself fails, remove the temp file rather than leaving an
    # orphan behind in a directory (e.g. the real, git-tracked ontologies
    # checkout) that's supposed to stay clean.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
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

`add_revision()` **replaces** `save_reference()` entirely —
`DuplicateFactKeyError` is removed, not deprecated. Calling it for a
`fact_key` that doesn't exist yet creates the page (its first revision);
calling it again appends another revision. There is no separate "create"
operation, matching how Wikipedia itself doesn't distinguish creating a
page from saving any other edit to it. `is_correction` has no default —
every call must make a real, explicit determination, the same way this
project already requires an explicit `DriftKind`/`Verdict` everywhere
else rather than silently defaulting.

`catalog[fact_key]` in the JSON file is now a **list** of revision
objects (was: one flat serialized `Reference`). `get_current_revision()`
returns `None` for a page that's never had a revision — there is no
"page exists but is empty" state, matching how a page can't exist without
having been created by *some* edit.

## `webapp/app.py` (full redesign)

Two endpoints, replacing the single `GET /api/references`:

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
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
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

`GET /api/references` is removed, not kept alongside the new routes —
"pages," not "references," is the real vocabulary now.

## `webapp/static/index.html` (full redesign)

One static page, two real views, chosen by a `?page=<fact_key>` query
parameter — still no build step, no framework:

- **No `page` param** (the index): fetches `/api/pages`, renders a table
  of every page — its `fact_key` as a link, its current citation's
  family, selector type, and **reference ID** (visually marked if the
  current revision is a correction), and its revision count. The
  reference ID is included specifically because it's the one column that
  actually changes when a correction lands — family and selector type
  are typically identical across revisions of the same page, so without
  it the index can't show *that* something changed, only *how many*
  times. An empty catalog shows an honest "No pages yet." message, same
  convention as before.
- **`?page=<fact_key>`**: fetches `/api/pages/<fact_key>`, renders that
  page's current citation prominently, then a full History table below
  (newest first) showing each revision's timestamp, author, and comment
  — a comment on a correction is visually marked, not just listed
  identically to a routine update.
- A fetch failure (network error, non-2xx status, a 404 for an unknown
  page) renders a distinct, visible error message — never a page stuck
  on "Loading..." forever, matching the fail-loud convention already
  established for this UI.

## Testing strategy

Dogfooded via real `cite()` calls against the real MiKaDiv-FM corpus,
matching the established pattern throughout this project:

- `add_revision()` on a fresh `fact_key` creates a page with exactly one
  revision, matching the real cited reference, author, comment, and
  `is_correction` value passed in.
- A second `add_revision()` call for the same `fact_key` (a different
  real citation) appends a second revision; `get_current_revision()`
  returns the second one; `get_history()` returns both, in order.
- `add_revision()` for one `fact_key` never disturbs another `fact_key`'s
  own history.
- `get_current_revision()`/`get_history()` on a `fact_key` that's never
  been touched return `None`/`[]` respectively, not an error.
- Two `revision_id`s from separate `add_revision()` calls are never
  equal, even for identical arguments — the same non-idempotency
  guarantee `record_review()` already established for review IDs.
- The written catalog file is pretty-printed and key-sorted (as before),
  and a rejected/failed write (malformed existing catalog, an
  interrupted write simulated via a monkeypatched `os.replace`) leaves
  the file byte-for-byte unchanged **and no leftover `.tmp` file** — the
  same guarantees the previous sub-project's own tests already
  established, re-verified against the new list-based format and
  explicitly asserted (not just implied) for the interrupted-write case.
- A catalog written in the pre-revision-history flat shape (or containing
  a revision missing a required field) raises `CatalogLoadError` — never
  an opaque `KeyError`/`TypeError` from deep inside `get_history()`/
  `list_pages()` — since `REFERENCES_CATALOG_PATH` is a user-settable
  environment variable and old-format catalogs genuinely exist from the
  previous, now-replaced sub-project.
- `list_pages()` on a multi-page catalog returns one `PageSummary` per
  page, each with the correct `revision_count` and `current` revision;
  on an empty catalog it returns `{}`.
- `webapp`'s `GET /api/pages` and `GET /api/pages/{fact_key}` are tested
  via `TestClient` against real `tmp_path` catalog fixtures built with
  real `add_revision()` calls — never the real committed catalog. A
  request for an unknown `fact_key` returns a real 404.
- The static page's two views are manually verified in a real browser
  (via the reserved port, the same way every prior `webapp` change in
  this project has been) — the index with a real multi-page,
  multi-revision fixture temporarily written to the real catalog path
  and reverted afterward, and a page-detail view showing a correction
  visually distinguished from a routine update.

## Roadmap: what this enables next

- **The interaction layer** — a real edit form calling `add_revision()`
  with a human's actual input, still the single most-repeated "still
  missing" item across this project's specs. **Must address**
  concurrent writes when it's designed: `add_revision()` today is an
  unlocked read-modify-write (load the whole catalog, mutate in memory,
  atomically replace the file) — two truly concurrent calls for the same
  `fact_key` can silently lose one caller's revision, with no error,
  because the atomic rename makes the second writer's full-catalog
  snapshot win outright. Not reachable today, since nothing yet calls
  `add_revision()` except test code and manual scripts (no concurrent
  caller exists), but the whole premise of a page+revision model is
  repeated, potentially concurrent edits to the same page — the
  interaction layer needs either a file lock or a compare-and-swap on
  the page's last `revision_id` (the real Wikipedia model this design
  follows calls this an "edit conflict") before it can be safely
  multi-user.
- **Talk-page-style discussion**, using this exact revision mechanism in
  a different namespace, once there's a real reason to build it.
- **Diffing between revisions** — showing what actually changed in the
  cited content, not just that something changed.
- **Source-reliability tracking**, once real review history exists to
  compute it from.
- **`cite_union()`'s corroboration-independence check** and
  **AAR-structured review reasoning** — both real, both deferred to
  their own modules' future sub-projects.

## Definition of Done

- `references_catalog/catalog.py` implements `Revision`, `PageSummary`,
  `CatalogLoadError`, `load_catalog()`, `add_revision()`,
  `get_current_revision()`, `get_history()`, and `list_pages()` with the
  semantics above. `save_reference()`/`DuplicateFactKeyError` no longer
  exist.
- `webapp/app.py` serves `GET /api/pages` and `GET /api/pages/{fact_key}`
  (`GET /api/references` removed) with the semantics above.
- `webapp/static/index.html` renders both the page index and a
  page-detail view with visible revision history, manually verified in a
  real browser.
- All tests listed above pass.
- The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}`.
