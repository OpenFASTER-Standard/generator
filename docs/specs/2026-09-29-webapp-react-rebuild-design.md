# Webapp React Rebuild — Design

## Context

`generator`'s webapp today is a FastAPI backend (`webapp/app.py`) plus one
hand-written `webapp/static/index.html`: vanilla JS, manual
escaping-safe DOM construction, three views toggled by query params
(`?page=`, `?add=1`, and a default family-list view). No build step, no
bundler, no framework.

Since then, `OpenFASTER-Standard/ui` (`@openfaster-standard/ui`) was
built and published: a real, tested, npm-published React 19 + Base UI
component library, with a working CI/release pipeline (npm Trusted
Publishing, no standing credential). The operator's own instruction is
to rebuild this webapp fully on top of it, in one pass, not staged:

1. Replace all 3 existing vanilla-JS views with real React views built
   on `@openfaster-standard/ui`.
2. Add the still-missing review/drift-review view — `review_surfacing`,
   `review_recording`, and `review_consultation` are all built and
   tested (see their own specs) but have **zero webapp entry point**
   today.
3. Build the catalog→sweep bridge — `staleness_sweep.sweep()` takes
   `dict[str, Reference]` (real objects), but `references_catalog`
   only stores/returns plain JSON dicts (`Revision.reference: dict`).
   `reference_model/serialize.py` has `to_json_dict()`; there is no
   reverse. Zero code coupling exists between the catalog and the sweep
   today — verified directly by reading both modules.
4. Conclude with a deliberate architectural-fitness audit across
   `generator` and `ui` together, fixing every finding regardless of
   severity (this box's own standing rule — see `/work/CLAUDE.md`).

Decided during brainstorming, so it isn't re-litigated later:

- **No new OpenFASTER branding in this sub-project.** The webapp is
  built on `ui`'s current, unmodified default shadcn/Base UI "nova"
  theme. Reskinning later only touches `ui`'s theme tokens, not how the
  webapp uses components.
- **`record_review()`'s returned Leaf becomes a new catalog revision**
  on the reviewed `fact_key`. A review decision is a real, browsable
  event in that page's own history, not a side-channel fact only
  visible in `reviews_dir`.
- **Real automated frontend tests** (Vitest + React Testing Library),
  not just manual verification — this project's prior webapp
  sub-projects had none by convention; the "fix everything, Stallman
  bar" instruction for this one's audit phase makes untested React
  views a real gap, not a style choice.
- **`@openfaster-standard/ui` gets extended in place** wherever this
  webapp has a real, justified component need `ui` doesn't cover yet —
  this is exactly what a shared foundation is for.
- **Real client-side routing** (React Router, path-based routes)
  replaces the hand-rolled query-param dispatch — 4 real views with
  real navigation is what a router is for.
- **A candidate-list filter `Input`** is added to the add-citation view
  in this same pass (previously a separately-tracked gap —
  `Personentypen`'s 127 candidates are unusable to scroll through
  today) — the candidate table is already being fully rebuilt here, so
  this is a small, natural addition rather than a separate later pass.

## Non-Goals

- **PDF citation flow.** No PDF discoverer exists yet; `GET
  /api/candidates` still only ever lists XSD families.
- **Optimistic-concurrency (compare-and-swap) protection.** Same
  reasoning as `citation-workflow`'s own spec: one curator, no
  long-lived draft state, the race window is still only a few seconds.
- **Showing existing citation state before re-citing a `fact_key`.**
  Still a real, cheap future refinement, not picked up here.
- **A general "browse and edit any page" flow.** Same scope boundary as
  before — submitting the same `fact_key` again still just appends a
  revision via `add_revision()`'s existing semantics.
- **Any change to `review_surfacing`, `review_recording`, or
  `review_consultation`'s own internals.** They're correct and tested;
  this sub-project only wires them together and gives them a UI.

## Architecture overview

- **Backend**: `webapp/app.py` gains two new endpoints (`GET
  /api/review`, `POST /api/reviews`) and one catch-all route: any
  request path that isn't `/api/*` and doesn't match a real static
  asset returns the SPA's `index.html`, so a hard refresh on e.g.
  `/pages/some-key` still works (React Router owns everything past
  that point, client-side).
- **Frontend**: a new `webapp/frontend/` directory — Vite + React 19 +
  TypeScript. `webapp/frontend/dist/` is what `webapp/app.py`'s
  existing `StaticFiles` mount serves (same mount point, built output
  instead of a hand-written file). `@openfaster-standard/ui` is a real
  npm dependency, not vendored.
- **Routing**: React Router, 4 path-based routes: `/` (index), `/pages/:factKey`
  (page detail), `/add` (candidate browse + cite), `/review` (drift
  review). The old `?page=`/`?add=1` URLs stop working — nothing
  external links to this internal tool.

## `reference_model/deserialize.py` (new)

The missing counterpart to `serialize.py`'s `to_json_dict()`:

```python
"""Deserializes a plain JSON-safe dict (as produced by
reference_model.serialize.to_json_dict()) back into a real Reference.
See docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from __future__ import annotations

from reference_model.model import ContentHash, Leaf, Reference, SubjectDocument, Union
from reference_model.selectors.json_selector import JsonSelector
from reference_model.selectors.svg_selector import SvgSelector
from reference_model.selectors.xpath_selector import XPathSelector

_SELECTOR_TYPES = {
    "XPathSelector": XPathSelector,
    "JsonSelector": JsonSelector,
    "SvgSelector": SvgSelector,
}


class ReferenceDeserializationError(Exception):
    pass


def from_json_dict(data: dict) -> Reference:
    if not isinstance(data, dict):
        raise ReferenceDeserializationError(f"expected a JSON object, got {type(data).__name__}")

    if "parts" in data:
        try:
            parts = [from_json_dict(part) for part in data["parts"]]
        except (KeyError, TypeError) as exc:
            raise ReferenceDeserializationError(f"malformed Union.parts: {exc}") from exc
        return Union(parts=tuple(parts))

    try:
        selector_data = dict(data["selector"])
        selector_type = selector_data["type"]
        if selector_type not in _SELECTOR_TYPES:
            raise ReferenceDeserializationError(f"unknown selector type: {selector_type!r}")
        selector_cls = _SELECTOR_TYPES[selector_type]
        selector = selector_cls(**selector_data)

        subject_document = SubjectDocument(**data["subject_document"])
        content_hash = ContentHash(**data["content_hash"])

        return Leaf(
            reference_id=data["reference_id"],
            subject_document=subject_document,
            selector=selector,
            content_hash=content_hash,
            captured_at=data["captured_at"],
        )
    except KeyError as exc:
        raise ReferenceDeserializationError(f"missing required field: {exc}") from exc
    except TypeError as exc:
        raise ReferenceDeserializationError(f"malformed reference structure: {exc}") from exc
```

`Union`'s `reference_id`/`content_hash` are recomputed in
`__post_init__` from `parts` — never read from `data` for a Union. This
is a real, testable invariant: `from_json_dict(to_json_dict(u)) == u`
for any real `Union`, byte-for-byte, because both directions derive
those two fields the same way from the same parts.

A malformed dict raises `ReferenceDeserializationError` — it never
silently returns a wrong or partial object. The catalog→sweep bridge
below catches this per-`fact_key`, the same way `sweep()` itself already
never lets one bad family take down the whole run.

## `review_workflow/` (new package)

Mirrors `citation_workflow`'s own role: the orchestration layer that
makes the already-built, already-tested pieces (`references_catalog`,
`reference_model.deserialize`, `staleness_sweep`, `review_surfacing`,
`review_recording`, `review_consultation`) work together, so
`webapp/app.py` stays a thin HTTP layer.

```python
"""Orchestrates the review pipeline against the real catalog: load
current citations, sweep them for drift, filter out what's already been
reviewed, and record new review decisions back onto the catalog. See
docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reference_model.deserialize import ReferenceDeserializationError, from_json_dict
from references_catalog.catalog import Revision, add_revision, list_pages
from review_consultation.consult import apply_reviews, load_reviews
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import FlaggedLeaf, ReviewSummary, summarize_for_review
from staleness_sweep.sweep import sweep


@dataclass(frozen=True)
class WebReviewSummary:
    summary: ReviewSummary
    deserialization_failures: tuple[str, ...]  # fact_keys whose current revision isn't a valid Reference


def get_review_summary(catalog_path: str | Path, module_root: str, reviews_dir: str) -> WebReviewSummary:
    pages = list_pages(catalog_path)

    references = {}
    deserialization_failures = []
    for fact_key, page_summary in pages.items():
        try:
            references[fact_key] = from_json_dict(page_summary.current.reference)
        except ReferenceDeserializationError:
            deserialization_failures.append(fact_key)

    report = sweep(references, module_root)
    summary = summarize_for_review(report)
    reviews = load_reviews(reviews_dir)
    summary = apply_reviews(summary, reviews)

    return WebReviewSummary(
        summary=summary,
        deserialization_failures=tuple(sorted(deserialization_failures)),
    )


def submit_review(
    catalog_path: str | Path,
    reviews_dir: str,
    fact_key: str,
    flagged: FlaggedLeaf,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Revision:
    leaf = record_review(reviews_dir, fact_key, flagged, reviewer, verdict, reasoning)
    return add_revision(
        catalog_path, fact_key, leaf, reviewer,
        f"Review ({verdict.value}): {reasoning}", is_correction=False,
    )
```

`submit_review()`'s `is_correction=False`: a review decision isn't
correcting the fact_key's own cited content — it's a new kind of event
in that page's history, distinct from an actual content correction. The
comment field carries the verdict + reasoning so the page-detail view's
existing history table already shows something meaningful without any
further change to that view.

## `webapp/app.py` (extended)

Two new routes, plus the SPA-fallback route:

```python
from review_workflow import get_review_summary, submit_review
from review_recording.record import Verdict


DEFAULT_REVIEWS_DIR = "/work/ontologies/mikadiv-fm/reviews"


def _reviews_dir() -> str:
    return os.environ.get("MIKADIV_REVIEWS_DIR", DEFAULT_REVIEWS_DIR)


@app.get("/api/review")
def get_review_endpoint() -> dict:
    result = get_review_summary(_catalog_path(), _module_root(), _reviews_dir())
    return {
        "flagged": {
            fact_key: [dataclasses.asdict(fl) for fl in entries]
            for fact_key, entries in result.summary.flagged.items()
        },
        "unresolved_families": [dataclasses.asdict(f) for f in result.summary.unresolved_families],
        "excluded_keys": list(result.summary.excluded_keys),
        "deserialization_failures": list(result.deserialization_failures),
    }


class SubmitReviewRequest(BaseModel):
    fact_key: str
    leaf_reference_id: str  # identifies which FlaggedLeaf under fact_key this decision is for
    reviewer: str
    verdict: str  # "approved" | "rejected"
    reasoning: str


@app.post("/api/reviews")
def submit_review_endpoint(request: SubmitReviewRequest) -> dict:
    # Re-fetches the current summary server-side and finds the exact FlaggedLeaf
    # by reference_id, rather than trusting a client-serialized FlaggedLeaf --
    # same "never trust client state for anything server-verifiable" principle
    # citation_workflow's add_citation() already established for `family`.
    result = get_review_summary(_catalog_path(), _module_root(), _reviews_dir())
    entries = result.summary.flagged.get(request.fact_key, ())
    flagged = next((fl for fl in entries if fl.leaf.reference_id == request.leaf_reference_id), None)
    if flagged is None:
        raise HTTPException(
            status_code=404,
            detail=f"no pending flagged leaf {request.leaf_reference_id!r} under {request.fact_key!r}",
        )
    try:
        verdict = Verdict(request.verdict)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid verdict: {request.verdict!r}")

    revision = submit_review(
        _catalog_path(), _reviews_dir(), request.fact_key, flagged, request.reviewer, verdict, request.reasoning,
    )
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


# Must be registered AFTER the StaticFiles mount below, and matches only
# paths StaticFiles itself didn't already resolve (a real asset, e.g.
# /assets/index-abc123.js, is served directly and never reaches this).
@app.exception_handler(404)
async def spa_fallback(request, exc):
    if request.url.path.startswith("/api/"):
        raise exc
    return FileResponse(Path(__file__).parent / "frontend_dist" / "index.html")
```

`404`-as-fallback (via `exception_handler`, not a catch-all route
registered before the mount) is deliberate: FastAPI resolves routes and
the `StaticFiles` mount in registration order, and a real 404 from
`StaticFiles` (no matching built asset) is exactly the signal "this
must be a client-side route" — anything that isn't a real asset falls
through to it.

## `webapp/frontend/` (new)

```
webapp/frontend/
  src/
    main.tsx              # React Router setup, 4 routes
    api.ts                # typed fetch wrappers for every /api/* endpoint
    views/
      IndexView.tsx        # "/"
      PageDetailView.tsx   # "/pages/:factKey"
      AddCitationView.tsx  # "/add"
      ReviewView.tsx       # "/review"
  vite.config.ts
  package.json             # @openfaster-standard/ui as a real npm dependency
```

Per view, built entirely from `@openfaster-standard/ui` components:

- **`IndexView`** — `Table` listing every fact_key (family, selector
  type, reference ID, revision count); a `Badge` (variant
  `destructive`) on any row whose current revision `is_correction`.
- **`PageDetailView`** — heading + summary line, then a `Table` of
  revision history (when/author/comment), same correction `Badge`
  treatment per row. A review-decision revision (comment starting
  `"Review ("...")"`) reads naturally in this same table — no separate
  UI needed for it.
- **`AddCitationView`** — family list (an `Accordion` — see below —
  one item per family, its candidates `Table` inside), a filter
  `Input` above each family's candidate table (client-side substring
  match against tag/name/xpath), a "Cite this" button per candidate
  row opening a `Dialog` with the citation `Form` (`fact_key`,
  `author`, `comment`, `is_correction` via `Input`/`Label`/`Checkbox`).
  Submitting `POST`s `/api/citations` and navigates to
  `/pages/:factKey`.
- **`ReviewView`** — fetches `GET /api/review`. Unresolved families
  and deserialization failures surfaced via `Alert` (two distinct
  messages — "this family's current file couldn't be resolved this
  run" vs. "this page's citation is corrupted and can't be checked" —
  never merged into one generic warning). Flagged items grouped by
  `fact_key` (an `Accordion` again — one item per fact_key, its
  flagged leaves listed inside, each showing `drift_kind` and
  `fingerprint`). Each flagged leaf has a "Review" button opening a
  `Dialog` with a form (`reviewer` `Input`, approve/reject as two
  plain `Button`s — no new component needed for a binary choice — and
  a `reasoning` `Textarea`). Submitting `POST`s `/api/reviews` and
  removes that leaf from the visible summary (re-fetch, or optimistic
  local removal — implementation's call).

## `@openfaster-standard/ui` additions

**`Accordion`** is the one new component clearly justified by the
design above — used identically in two places (family→candidates in
`AddCitationView`, fact_key→flagged-leaves in `ReviewView`), and it's
exactly the shadcn/Base UI component for "click a header to reveal
content," which is precisely the existing (and kept) interaction
pattern. Built the same way as the existing 12: real Vitest tests, a
real Storybook story with genuine variants, added to `ui`'s own
`src/index.ts` exports.

Beyond `Accordion`, no other new component is confidently justified by
this design as written — everything else above maps onto the 12
components that already exist (`Table`, `Badge`, `Alert`, `Dialog`,
`Form`, `Input`, `Label`, `Checkbox`, `Textarea`, `Button`). If
implementation surfaces a real, concrete need for something else (per
the operator's own "extend `ui` as needed" decision), add it the same
way — real tests, real stories, not a placeholder.

## Testing strategy

- **`reference_model/deserialize.py`**: the Leaf round-trip
  (`from_json_dict(to_json_dict(leaf)) == leaf` for a real Leaf built
  via `cite()` against the real corpus); the Union round-trip
  (byte-identical `reference_id`/`content_hash` after a round trip);
  every malformed-input case (missing field, unknown selector type,
  non-dict input) raises `ReferenceDeserializationError`, never a raw
  `KeyError`/`TypeError` leaking out.
- **`review_workflow`**: `get_review_summary()` against a real
  `tmp_path` catalog with a mix of healthy, drifted, and
  deliberately-corrupted (unparseable `reference` dict) revisions —
  proves a corrupted entry lands in `deserialization_failures`, not a
  crash, and every other entry still gets swept normally.
  `submit_review()` against a real flagged leaf: the review JSON file
  is written, and the fact_key's catalog history gains exactly one new
  revision whose `comment` contains the verdict and reasoning.
- **Webapp endpoints**: `TestClient` tests for `GET /api/review` (real
  corpus + real `tmp_path` catalog/reviews_dir fixtures) and `POST
  /api/reviews`, including the 404 (unknown `leaf_reference_id`) and
  400 (invalid `verdict` string) cases, matching this project's
  established endpoint-testing convention.
- **Frontend**: Vitest + React Testing Library for all 4 views and the
  new `Accordion` component, against a mocked `fetch` layer — covering
  the real user flows (submit a citation, approve/reject a review, the
  candidate filter actually filtering) rather than just "it renders."
- **Manual verification**: a real Playwright pass against the running
  webapp (reserved port 8012), covering all 4 views end-to-end with
  real data, including a full drift-review round trip — flag
  something, review it, confirm it disappears from `/review` and shows
  up in the fact_key's own history at `/pages/:factKey` — then revert
  the real committed catalog/reviews directory back to their prior
  state afterward, matching every prior webapp-touching sub-project's
  own verification convention.

## Audit phase

After everything above is built, tested, and merged: a dedicated,
deliberate architectural-fitness pass across `generator` and `ui`
together — not just the final whole-branch review this sub-project's
own plan already gets, but the explicit, separate "Richard Stallman
would say 'damn that's nice'" bar the operator asked for. Every finding
gets fixed regardless of severity, per this box's standing rule (see
`/work/CLAUDE.md`) — no deferred Minors, no exceptions for this being
an "extra" pass on top of the normal review.

## Definition of Done

- `reference_model/deserialize.py` implements `from_json_dict()` and
  `ReferenceDeserializationError` with the semantics above; the Leaf
  and Union round-trip invariants hold against real data.
- `review_workflow/` implements `get_review_summary()` and
  `submit_review()` with the semantics above.
- `webapp/app.py` serves `GET /api/review` and `POST /api/reviews`,
  plus the SPA-fallback route.
- `webapp/frontend/` is a real Vite + React + TypeScript app with all 4
  routes, built entirely from `@openfaster-standard/ui` (plus the new
  `Accordion`), and its built `dist/` is what the webapp actually
  serves.
- `@openfaster-standard/ui` has a new `Accordion` component (and
  anything else implementation genuinely needed), each with real tests
  and Storybook stories, published as a new version.
- All automated tests pass — Python (pytest) and frontend (Vitest).
- A real, full manual Playwright pass covers all 4 views end-to-end,
  including a complete drift-review round trip; the real committed
  catalog and reviews directory are back to their prior state
  afterward.
- The dedicated post-merge architectural-fitness audit across
  `generator` and `ui` is complete, with every finding fixed regardless
  of severity.
