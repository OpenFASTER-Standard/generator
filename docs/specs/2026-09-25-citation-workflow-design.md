# Citation Workflow — Design

## Context

This is the interaction layer: the single most-repeated "still missing"
item named across nearly every spec so far this session. Everything it
needs already exists as real, working, merged code — this sub-project's
whole job is connecting them:

- `discovery.xsd_discoverer.discover_candidates()` mechanically finds
  citable candidates in one real XSD file.
- `staleness_sweep.resolve.resolve_current_location()` resolves a
  `family` name to its real current file — but only one family at a
  time; there is no "list every family" equivalent yet.
- `reference_model.cite()` turns a `SubjectDocument` + selector into a
  real `Leaf`.
- `references_catalog.catalog.add_revision()` already unifies "create a
  page" and "edit a page" into one call — the exact unification a real
  edit form needs, already built two sub-projects ago.

Verified live before writing this down: browsing all 13 real XSD
families' candidates via `discover_candidates()` yields 422 real,
zero-excluded candidates across the corpus; citing one of them
end-to-end (`resolve_current_location()` → `cite()` → `add_revision()`)
works exactly as designed, using only already-merged code.

## Non-Goals

- **Not** a drift-review UI. Reviewing flagged staleness-sweep drift
  (`review_surfacing`/`review_recording`/`review_consultation`) is a
  separate interaction flow, operating on a different pipeline that
  isn't wired into `webapp` at all yet — a distinct, later sub-project.
- **Not** a PDF citation flow. No PDF discoverer exists; `GET /api/candidates`
  only ever lists XSD families, exactly matching `discover_candidates()`'s
  own existing scope.
- **Not** search/filter within a family's candidate list. Some families
  have 100+ candidates (`Personentypen`: 127) — real, but a cheap later
  refinement, not a blocker for a first working flow.
- **Not** full optimistic-concurrency (compare-and-swap) protection
  against two genuinely concurrent edits to the same page. **Named as a
  concrete prerequisite for this exact sub-project by the previous
  sub-project's own final review** — reconsidered here, not silently
  dropped: the race window this specific flow exposes is only the brief
  span between a human choosing a candidate and one HTTP `POST` landing
  (seconds), not an editing session with a text field open for minutes
  the way a real prose-editing form would be. Given this project's
  current real usage (one curator, not a public multi-editor
  free-for-all) and YAGNI, still deferred — but if this flow ever grows
  a longer-lived draft/edit-in-progress state, that reasoning no longer
  holds and CAS becomes load-bearing, not optional.
- **Not** a general "browse and edit any existing page" flow. Submitting
  the same `fact_key` again naturally appends another revision (per
  `add_revision()`'s own existing semantics), but this UI's candidate
  browser doesn't yet show "here's what's already cited for this
  fact_key" before you pick a new candidate for it — a real, cheap
  future refinement once this first flow is working.

## `staleness_sweep/resolve.py` (extended, not just added to)

`resolve_current_location()`'s own internals — reading `_current`,
validating containment, reading and validating `_manifest.json` — are
exactly what a new "list every family in the current snapshot" function
also needs. Refactored to share that logic via two private helpers,
verified live to leave `resolve_current_location()`'s own observable
behavior completely unchanged (the full existing test suite, 175 tests,
passes against the refactored file with zero modifications):

```python
"""Resolves a family name to its current real file, using the real
ontologies-repo convention: a plain-text _current pointer naming the
current snapshot version, and a per-snapshot _manifest.json mapping every
family to its real filename (relative to that snapshot's own directory).
No filename parsing anywhere. See
docs/specs/2026-09-23-staleness-sweep-design.md and
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from reference_model.model import ResolutionOutcome, Status


class CorpusIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class FamilyLocation:
    family: str
    version: str
    retrieval_uri: str


def _load_current_manifest(module_root: str):
    module_root_path = Path(module_root)
    current_path = module_root_path / "_current"
    if not current_path.exists():
        return None
    snapshot = current_path.read_text().strip()
    resolved_module_root = module_root_path.resolve()
    snapshot_dir = (module_root_path / snapshot).resolve()
    if not snapshot_dir.is_relative_to(resolved_module_root):
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r}, which escapes module_root {module_root!r}"
        )
    manifest_path = snapshot_dir / "_manifest.json"
    if not manifest_path.exists():
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r} but {manifest_path} does not exist"
        )
    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as exc:
        raise CorpusIntegrityError(f"{manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise CorpusIntegrityError(
            f"{manifest_path} must contain a JSON object, got {type(manifest).__name__}"
        )
    return snapshot_dir, manifest, snapshot


def _resolve_family_path(snapshot_dir: Path, family: str, manifest: dict) -> str:
    resolved_path = (snapshot_dir / manifest[family]).resolve()
    if not resolved_path.is_relative_to(snapshot_dir):
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot_dir.name!r} names {manifest[family]!r} "
            f"for family {family!r}, which escapes the snapshot directory {snapshot_dir}"
        )
    if not resolved_path.is_file():
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot_dir.name!r} names {manifest[family]!r} "
            f"for family {family!r}, but {resolved_path} is not a real file"
        )
    return str(resolved_path)


def resolve_current_location(module_root: str, family: str) -> ResolutionOutcome:
    result = _load_current_manifest(module_root)
    if result is None:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    snapshot_dir, manifest, _snapshot = result
    if family not in manifest:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    resolved_path = _resolve_family_path(snapshot_dir, family, manifest)
    return ResolutionOutcome(status=Status.RESOLVED, raw_content=resolved_path)


def list_current_locations(module_root: str) -> list[FamilyLocation]:
    result = _load_current_manifest(module_root)
    if result is None:
        return []
    snapshot_dir, manifest, snapshot = result
    return [
        FamilyLocation(
            family=family,
            version=snapshot,
            retrieval_uri=_resolve_family_path(snapshot_dir, family, manifest),
        )
        for family in sorted(manifest.keys())
    ]
```

`list_current_locations()` on a corpus with no `_current` pointer at all
returns `[]` (matching `resolve_current_location()`'s own `NOT_FOUND` for
the same situation), not an error — an empty/uninitialized corpus is a
normal state, not a fault.

## `discovery/corpus_candidates.py` (new)

Combines `list_current_locations()` (XSD families only — anything not
ending in `.xsd` is skipped, since no PDF discoverer exists) with
`discover_candidates()`, grouped by family:

```python
"""Discovers citable candidates across every real XSD family in the
current corpus snapshot, not just one file. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from discovery.xsd_discoverer import discover_candidates
from staleness_sweep.resolve import list_current_locations


@dataclass(frozen=True)
class CorpusCandidate:
    tag: str
    name: str
    xpath: str


def list_corpus_candidates(module_root: str) -> dict[str, list[CorpusCandidate]]:
    result = {}
    for location in list_current_locations(module_root):
        if not location.retrieval_uri.endswith(".xsd"):
            continue
        discovery_result = discover_candidates(location.retrieval_uri)
        result[location.family] = [
            CorpusCandidate(tag=c.tag, name=c.name, xpath=c.xpath)
            for c in discovery_result.candidates
        ]
    return result
```

`family`/`version`/`retrieval_uri` are deliberately **not** carried on
`CorpusCandidate` — the citation-submission step below always
re-resolves `family` itself, server-side, rather than trusting a value a
client could have sent stale or tampered with.

## `citation_workflow/add_citation.py` (new)

The actual orchestration a submit action calls — re-resolve, cite, add a
revision, all in one place:

```python
"""Turns a human's choice of a discovered candidate into a real citation
and revision. See docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from pathlib import Path

from reference_model.cite import cite
from reference_model.model import Status, SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import Revision, add_revision
from staleness_sweep.resolve import resolve_current_location


class FamilyNotFoundError(Exception):
    pass


def add_citation(
    module_root: str,
    catalog_path: str,
    family: str,
    xpath: str,
    fact_key: str,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    outcome = resolve_current_location(module_root, family)
    if outcome.status != Status.RESOLVED:
        raise FamilyNotFoundError(f"{family!r} not found in the current corpus snapshot")
    version = Path(module_root, "_current").read_text().strip()
    subject_document = SubjectDocument(family=family, version=version, retrieval_uri=outcome.raw_content)
    leaf = cite(subject_document, XPathSelector.create(xpath))
    return add_revision(catalog_path, fact_key, leaf, author, comment, is_correction)
```

`cite()`'s own `CitationError` (the chosen `xpath` no longer resolves
cleanly — a real possibility if the corpus changed between when the
candidate list was fetched and when this was submitted) propagates
unchanged; the webapp layer below maps both it and `FamilyNotFoundError`
to a real 400.

## `webapp/app.py` (extended)

Two new routes, alongside the existing page-browsing ones:

```python
from pydantic import BaseModel

from citation_workflow.add_citation import FamilyNotFoundError, add_citation
from discovery.corpus_candidates import list_corpus_candidates
from reference_model.cite import CitationError

DEFAULT_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _module_root() -> str:
    return os.environ.get("MIKADIV_MODULE_ROOT", DEFAULT_MODULE_ROOT)


class AddCitationRequest(BaseModel):
    family: str
    xpath: str
    fact_key: str
    author: str
    comment: str
    is_correction: bool


@app.get("/api/candidates")
def list_candidates_endpoint() -> dict:
    candidates = list_corpus_candidates(_module_root())
    return {
        family: [dataclasses.asdict(c) for c in family_candidates]
        for family, family_candidates in candidates.items()
    }


@app.post("/api/citations")
def add_citation_endpoint(body: AddCitationRequest) -> dict:
    try:
        revision = add_citation(
            _module_root(),
            str(_catalog_path()),
            body.family,
            body.xpath,
            body.fact_key,
            body.author,
            body.comment,
            body.is_correction,
        )
    except (FamilyNotFoundError, CitationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"fact_key": body.fact_key, "revision": dataclasses.asdict(revision)}
```

`MIKADIV_MODULE_ROOT` follows the exact same call-time-read,
env-var-overridable pattern `REFERENCES_CATALOG_PATH`/`_catalog_path()`
already established, for the same reason: tests override it via
`monkeypatch.setenv()` without needing a fresh process per test.

## `webapp/static/index.html` (extended with a third view)

A new `?add=1` mode, alongside the existing no-param (index) and
`?page=<fact_key>` (page detail) modes:

- Fetches `/api/candidates` once; renders the family list as clickable
  buttons.
- Clicking a family renders that family's candidates as a table (tag,
  name, xpath) with a "Cite this" button per row — pure client-side
  state, no page reload.
- Clicking "Cite this" reveals a form (fact_key, author, comment, an
  "is a correction" checkbox, Submit) below the table, with the chosen
  candidate's `family`/`xpath` held in JS state, never re-typed by the
  human.
- Submitting `POST`s to `/api/citations`; on success, navigates to
  `?page=<fact_key>` — landing on the exact page-detail view this
  session's previous sub-project already built, showing the citation
  that was just added as its newest revision. On failure (400 or 500),
  shows a distinct, visible error message in place of the form — never a
  silent failure or a page stuck mid-submit.
- The index view (no query param) gets one new link: "Add citation" →
  `?add=1`.

## Testing strategy

Dogfooded against the real MiKaDiv-FM corpus throughout, matching this
project's established pattern:

- `list_current_locations()` on the real corpus returns all 21 real
  families (13 XSD + 8 PDF), each with the correct, real, resolved
  `retrieval_uri` and the real current version (`"1.02"`); on a corpus
  with no `_current` pointer it returns `[]`.
- `resolve_current_location()`'s own existing test suite is re-run
  unchanged against the refactored file and still fully passes — proving
  the refactor changed no observable behavior.
- `list_corpus_candidates()` on the real corpus returns exactly the 13
  real XSD families as keys (never any of the 8 PDF families), and the
  real per-family candidate counts already verified live during design
  (e.g. `Meldeart23`: 5, `Personentypen`: 127).
- `add_citation()` against the real corpus and a `tmp_path` catalog: a
  real family + a real candidate's `xpath` produces a page with exactly
  one revision, whose cited content matches what `cite()` would produce
  directly.
- `add_citation()` for a nonexistent family raises `FamilyNotFoundError`
  without creating any page.
- `add_citation()` called twice for the same `fact_key` (two different
  real candidates) appends a second revision — the create/edit
  unification, exercised through this new orchestration layer, not just
  `add_revision()` directly.
- `webapp`'s `GET /api/candidates` and `POST /api/citations` are tested
  via `TestClient` against real `tmp_path` catalog fixtures and the real
  corpus (never a synthetic candidate list) — including the 400 case for
  an unknown family and a stale/invalid `xpath`.
- The static page's new `?add=1` view is manually verified in a real
  browser (via the reserved port, matching every prior `webapp` change
  this session): browse a real family's real candidates, submit a real
  citation, land on the resulting page's detail view showing the new
  revision — then the temporary citation is reverted from the real
  committed catalog afterward.

## Roadmap: what this enables next

- **The drift-review UI** — the same webapp, extended with a page for
  `review_surfacing`'s flagged drift and a form calling `record_review()`
  — the other half of "the interaction layer," deliberately not built
  here.
- **Search/filter within a family's candidate list**, once 100+-item
  families make plain browsing genuinely slow.
- **Showing existing citation state before re-citing a `fact_key`** —
  letting a human see what a page already says before adding a
  correction to it, right from the candidate browser.
- **Real optimistic-concurrency protection**, if this flow ever grows a
  longer-lived draft state where the "not really concurrent" reasoning
  in this document's own Non-Goals stops holding.

## Definition of Done

- `staleness_sweep/resolve.py` implements `FamilyLocation` and
  `list_current_locations()` with the semantics above;
  `resolve_current_location()`'s own existing test suite still fully
  passes, unmodified.
- `discovery/corpus_candidates.py` implements `CorpusCandidate` and
  `list_corpus_candidates()` with the semantics above.
- `citation_workflow/add_citation.py` implements `FamilyNotFoundError`
  and `add_citation()` with the semantics above.
- `webapp/app.py` serves `GET /api/candidates` and
  `POST /api/citations` with the semantics above.
- `webapp/static/index.html` supports the `?add=1` view, manually
  verified end-to-end in a real browser: browse, pick, submit, land on
  the resulting page.
- All automated tests pass.
- The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}` after all of this sub-project's work, including the
  manual verification's temporary citation.
