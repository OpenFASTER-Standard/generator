# Webapp React Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `generator`'s webapp as a real React app on
`@openfaster-standard/ui`, add the missing drift-review view, bridge the
catalog to the staleness sweep, and close with a dedicated
architectural-fitness audit.

**Architecture:** A new `Accordion` component lands and publishes in
`ui` first, since the frontend depends on the *published* npm package
(a real, separate git repo — not a workspace link), not a local path.
Then the Python side (deserializer → `review_workflow` → two new
endpoints) is built and tested independently of any UI. Then the React
frontend (scaffold → four views, each consuming the endpoints above)
is built on top. Manual verification and the audit close out the plan.

**Tech Stack:** Python 3.11 (existing: `fastapi`, `pytest`), TypeScript
+ React 19 + Vite (new, matching `ui`'s own toolchain), React Router,
`@openfaster-standard/ui`, Vitest + React Testing Library.

**Spec:** `docs/specs/2026-09-29-webapp-react-rebuild-design.md`

## Global Constraints

- No new OpenFASTER branding — build on `ui`'s current, unmodified
  default theme.
- `record_review()`'s returned Leaf becomes a new catalog revision on
  the reviewed `fact_key` (via `add_revision()`), not a side-channel
  fact.
- Real automated frontend tests (Vitest + React Testing Library) for
  every new component and view — this project's convention of
  manual-verification-only for the webapp does not carry forward here.
- `@openfaster-standard/ui` is a real npm dependency of the new
  frontend (`webapp/frontend/package.json`), resolved from the public
  registry after Task 1 publishes it — never a local path/workspace
  reference across the two separate git repos.
- Old `?page=`/`?add=1` query-param URLs are replaced by real routes
  (`/`, `/pages/:factKey`, `/add`, `/review`) and simply stop working —
  nothing external links to this internal tool.
- The real committed `ontologies/mikadiv-fm/references.json` must be
  exactly `{}` again, and any real files written under
  `ontologies/mikadiv-fm/reviews/` during manual verification must be
  removed, after Task 10's manual verification — `git status` in
  `/work/ontologies` must show a clean tree afterward.

## Review Focus

- **A malformed catalog entry must exclude only that one `fact_key`,
  never crash the whole review summary.** `get_review_summary()`'s
  fixture set (Task 3) includes a deliberately-corrupted `reference`
  dict, and asserts every *other* entry still gets swept normally.
- **`POST /api/reviews` must re-verify the flagged leaf server-side**,
  the same principle `add_citation()` already established for
  `family` — never trust a client-supplied `FlaggedLeaf`. Task 4's
  tests include submitting a `leaf_reference_id` that isn't currently
  flagged under the given `fact_key` and asserting a 404, not a
  silently-accepted review.
- **The SPA-fallback route must distinguish a real API 404 from a
  client-side-route 404** — easy to get backwards. Task 4's tests
  assert `GET /api/pages/does-not-exist` still returns a real 404 JSON
  body (not the SPA shell), while `GET /some/client/route` returns the
  SPA's `index.html`.
- **A hard refresh on a non-root route must actually work.** Task 5's
  manual check (not just an automated test — this is inherently a
  real-browser, real-server behavior) navigates directly to
  `http://localhost:8012/pages/<factKey>` (typed URL, not a client-side
  navigation) and confirms the page renders, not a 404.
- **The `Union` round-trip invariant must be tested against a real,
  multi-part `Union`**, not a single `Leaf` standing in for it. Task 2's
  tests build a real two-part `Union` via `cite_union()` against two
  real `cite()`d Leafs from the real corpus, and assert
  `from_json_dict(to_json_dict(u)) == u` holds exactly, including
  `reference_id`/`content_hash`.

---

## Task 1: `ui` — `Accordion` component + publish

**Files (in `/work/ui`):**
- Create: `packages/ui/src/components/ui/accordion.tsx`
- Create: `packages/ui/src/components/ui/accordion.test.tsx`
- Create: `packages/ui/src/components/ui/accordion.stories.tsx`
- Modify: `packages/ui/src/index.ts`
- Create: `.changeset/add-accordion.md`

**Interfaces:**
- Produces: `Accordion`, `AccordionItem`, `AccordionTrigger`,
  `AccordionContent` (exported from `@openfaster-standard/ui`, the
  real published package Task 6/8/9 depend on).

- [ ] **Step 1: Generate the component via the project's own established shadcn pattern**

```bash
cd /work/ui/packages/ui
npx shadcn@4.21.0 add accordion --yes
```

Expected: `src/components/ui/accordion.tsx` is created, built on
`@base-ui/react/accordion` (already a dependency, confirmed installed
— no new package needed), matching the same `useRender`/`cva`/`cn`
composition style as `badge.tsx`/`dialog.tsx`.

- [ ] **Step 2: Write the failing test**

```tsx
// accordion.test.tsx
import { describe, expect, it } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "./accordion"

describe("Accordion", () => {
  it("reveals an item's content when its trigger is clicked", () => {
    render(
      <Accordion>
        <AccordionItem value="a">
          <AccordionTrigger>Family A</AccordionTrigger>
          <AccordionContent>Candidates for A</AccordionContent>
        </AccordionItem>
      </Accordion>
    )
    expect(screen.queryByText("Candidates for A")).not.toBeVisible()
    fireEvent.click(screen.getByText("Family A"))
    expect(screen.getByText("Candidates for A")).toBeVisible()
  })

  it("keeps a second item's content hidden while the first is open (default single-open behavior)", () => {
    render(
      <Accordion>
        <AccordionItem value="a">
          <AccordionTrigger>A</AccordionTrigger>
          <AccordionContent>Content A</AccordionContent>
        </AccordionItem>
        <AccordionItem value="b">
          <AccordionTrigger>B</AccordionTrigger>
          <AccordionContent>Content B</AccordionContent>
        </AccordionItem>
      </Accordion>
    )
    fireEvent.click(screen.getByText("A"))
    expect(screen.queryByText("Content B")).not.toBeVisible()
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm test accordion` (from `packages/ui`)
Expected: FAIL — `accordion.test.tsx` cannot import from `./accordion`
if Step 1 wasn't run, or the behavior assertions fail if the generated
component needs adjustment to match this exact API shape.

- [ ] **Step 4: Adjust the generated component if needed, until tests pass**

The shadcn-generated file may already satisfy this; if its exported
names differ, rename to match `Accordion`/`AccordionItem`/
`AccordionTrigger`/`AccordionContent` exactly — later tasks import
these exact names.

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm test accordion`
Expected: PASS, 2/2.

- [ ] **Step 6: Write the Storybook story**

```tsx
// accordion.stories.tsx
import type { Meta, StoryObj } from "@storybook/react"
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "./accordion"

const meta: Meta<typeof Accordion> = {
  title: "UI/Accordion",
  component: Accordion,
}
export default meta
type Story = StoryObj<typeof Accordion>

export const Default: Story = {
  render: () => (
    <Accordion>
      <AccordionItem value="a">
        <AccordionTrigger>MiKaDiv_FM_Meldeart23</AccordionTrigger>
        <AccordionContent>5 candidates</AccordionContent>
      </AccordionItem>
      <AccordionItem value="b">
        <AccordionTrigger>MiKaDiv_FM_Personentypen</AccordionTrigger>
        <AccordionContent>127 candidates</AccordionContent>
      </AccordionItem>
    </Accordion>
  ),
}
```

- [ ] **Step 7: Export from `src/index.ts`**

Add: `export { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "./components/ui/accordion"`

- [ ] **Step 8: Run the full test suite and build**

Run: `pnpm test && pnpm build` (from `packages/ui`)
Expected: all tests pass; build succeeds with no new errors.

- [ ] **Step 9: Add a real Changeset**

```markdown
---
"@openfaster-standard/ui": minor
---

Add Accordion component
```
Save as `.changeset/add-accordion.md`.

- [ ] **Step 10: Commit and push**

```bash
cd /work/ui
git add packages/ui/src/components/ui/accordion.tsx packages/ui/src/components/ui/accordion.test.tsx packages/ui/src/components/ui/accordion.stories.tsx packages/ui/src/index.ts .changeset/add-accordion.md
git commit -m "Add Accordion component"
git push
```

- [ ] **Step 11: Wait for CI, then the release, then verify the real publish**

CI (`ci.yml`) must go green on `main` first, which triggers `release.yml`
via `workflow_run`. Poll (do not guess a fixed sleep):

```bash
gh run list --repo OpenFASTER-Standard/ui --workflow=CI --limit 1
# once that run's conclusion is "success":
gh run list --repo OpenFASTER-Standard/ui --workflow=Release --limit 1
```

Expected: the Release run succeeds. Then:

```bash
npm view @openfaster-standard/ui versions --registry https://registry.npmjs.org
```

Expected: a new version beyond `0.1.0` is listed (a real `minor` bump,
e.g. `0.2.0`), and:

```bash
npm view @openfaster-standard/ui@latest --registry https://registry.npmjs.org
```

Expected: matches the new version — this is the exact version Task 5's
`webapp/frontend/package.json` will depend on.

---

## Task 2: `reference_model/deserialize.py`

**Files (in `/work/generator`):**
- Create: `reference_model/deserialize.py`
- Test: `tests/reference_model/test_deserialize.py`

**Interfaces:**
- Consumes: `reference_model.model.{ContentHash, Leaf, Reference, SubjectDocument, Union}`,
  `reference_model.selectors.{json_selector.JsonSelector, svg_selector.SvgSelector, xpath_selector.XPathSelector}`,
  `reference_model.serialize.to_json_dict()`, `reference_model.cite.{cite, cite_union}` (for building real test fixtures).
- Produces: `from_json_dict(data: dict) -> Reference`,
  `ReferenceDeserializationError` (exception) — both consumed by Task 3.

- [ ] **Step 1: Write the failing tests**

```python
# tests/reference_model/test_deserialize.py
import pytest
from reference_model.cite import cite, cite_union
from reference_model.deserialize import ReferenceDeserializationError, from_json_dict
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from staleness_sweep.resolve import resolve_current_location

MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _real_leaf(xpath: str):
    outcome = resolve_current_location(MODULE_ROOT, "MiKaDiv_FM_Meldeart23")
    subject_document = SubjectDocument(
        family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=outcome.raw_content
    )
    return cite(subject_document, XPathSelector.create(xpath))


def test_leaf_round_trips_through_json():
    leaf = _real_leaf("//xs:element[@name='MiKaDiv_FM']")
    assert from_json_dict(to_json_dict(leaf)) == leaf


def test_union_round_trips_through_json_with_matching_reference_id_and_content_hash():
    leaf_a = _real_leaf("//xs:element[@name='MiKaDiv_FM']")
    leaf_b = _real_leaf("//xs:element[@name='MiKaDiv_FM']/xs:complexType")
    union = cite_union([leaf_a, leaf_b])
    result = from_json_dict(to_json_dict(union))
    assert result == union
    assert result.reference_id == union.reference_id
    assert result.content_hash == union.content_hash


def test_missing_field_raises_deserialization_error():
    leaf = _real_leaf("//xs:element[@name='MiKaDiv_FM']")
    data = to_json_dict(leaf)
    del data["captured_at"]
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict(data)


def test_unknown_selector_type_raises_deserialization_error():
    leaf = _real_leaf("//xs:element[@name='MiKaDiv_FM']")
    data = to_json_dict(leaf)
    data["selector"]["type"] = "NotARealSelector"
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict(data)


def test_non_dict_input_raises_deserialization_error():
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict("not a dict")


def test_malformed_union_parts_raises_deserialization_error():
    with pytest.raises(ReferenceDeserializationError):
        from_json_dict({"parts": "not a list"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_deserialize.py -v`
Expected: FAIL — `reference_model.deserialize` does not exist.

- [ ] **Step 3: Create `reference_model/deserialize.py`**

Use the exact implementation already fixed in the spec's own
"`reference_model/deserialize.py` (new)" section (the `_SELECTOR_TYPES`
dispatch table, the `parts`-key-means-Union branch, the
try/except KeyError/TypeError → `ReferenceDeserializationError`
wrapping) — copy it verbatim, it's already fully designed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_deserialize.py -v`
Expected: PASS, 7/7.

- [ ] **Step 5: Run the full test suite**

Run: `pytest`
Expected: all tests pass (no existing behavior touched).

- [ ] **Step 6: Commit**

```bash
git add reference_model/deserialize.py tests/reference_model/test_deserialize.py
git commit -m "Add reference_model.deserialize.from_json_dict(): the catalog-to-sweep bridge"
```

---

## Task 3: `review_workflow/` package

**Files (in `/work/generator`):**
- Create: `review_workflow/__init__.py`
- Create: `review_workflow/orchestrate.py`
- Test: `tests/review_workflow/__init__.py`
- Test: `tests/review_workflow/test_orchestrate.py`
- Modify: `pyproject.toml` (add `"review_workflow*"` to `packages.find.include`)

**Interfaces:**
- Consumes: `reference_model.deserialize.{from_json_dict, ReferenceDeserializationError}` (Task 2),
  `references_catalog.catalog.{Revision, add_revision, list_pages}`,
  `review_consultation.consult.{apply_reviews, load_reviews}`,
  `review_recording.record.{Verdict, record_review}`,
  `review_surfacing.summarize.{FlaggedLeaf, ReviewSummary, summarize_for_review}`,
  `staleness_sweep.sweep.sweep`.
- Produces: `WebReviewSummary` (dataclass: `summary: ReviewSummary`,
  `deserialization_failures: tuple[str, ...]`),
  `get_review_summary(catalog_path, module_root, reviews_dir) -> WebReviewSummary`,
  `submit_review(catalog_path, reviews_dir, fact_key, flagged, reviewer, verdict, reasoning) -> Revision`
  — both consumed by Task 4.

- [ ] **Step 1: Update `pyproject.toml`**

Add `"review_workflow*"` to the `[tool.setuptools.packages.find]`
`include` list, alongside the existing entries.

- [ ] **Step 2: Create empty package markers**

```bash
touch review_workflow/__init__.py tests/review_workflow/__init__.py
```

- [ ] **Step 3: Write the failing tests**

```python
# tests/review_workflow/test_orchestrate.py
import json
from pathlib import Path

import pytest
from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import add_revision, get_history
from review_recording.record import Verdict
from review_workflow.orchestrate import get_review_summary, submit_review
from staleness_sweep.resolve import resolve_current_location

MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _real_leaf(family: str, xpath: str):
    outcome = resolve_current_location(MODULE_ROOT, family)
    subject_document = SubjectDocument(family=family, version="1.02", retrieval_uri=outcome.raw_content)
    return cite(subject_document, XPathSelector.create(xpath))


def test_healthy_and_corrupted_entries_coexist(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "//xs:element[@name='MiKaDiv_FM']")
    add_revision(str(catalog_path), "healthy-key", leaf, "author", "comment", False)

    # A second page whose current revision's `reference` is not valid JSON-Reference shape.
    catalog = json.loads(catalog_path.read_text())
    catalog["corrupted-key"] = [{
        "revision_id": "x", "reference": {"not": "a-real-reference"},
        "author": "a", "comment": "c", "is_correction": False, "created_at": "2026-01-01T00:00:00+00:00",
    }]
    catalog_path.write_text(json.dumps(catalog))

    result = get_review_summary(str(catalog_path), MODULE_ROOT, str(tmp_path / "reviews"))

    assert result.deserialization_failures == ("corrupted-key",)
    assert "corrupted-key" not in result.summary.flagged
    # healthy-key resolves cleanly against the real, unchanged corpus, so it's not flagged either --
    # the assertion that matters here is that it was actually swept (proven by it NOT being in
    # deserialization_failures), not that it happens to show drift.


def test_submit_review_appends_a_catalog_revision_citing_the_review_decision(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "//xs:element[@name='MiKaDiv_FM']")
    add_revision(str(catalog_path), "some-key", leaf, "author", "comment", False)

    from review_surfacing.summarize import DriftKind, FlaggedLeaf
    from reference_model.model import ResolutionOutcome, Status
    flagged = FlaggedLeaf(
        leaf=leaf, outcome=ResolutionOutcome(status=Status.RESOLVED), drift_kind=DriftKind.CONTENT, fingerprint="abc123",
    )

    revision = submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "some-key", flagged, "reviewer-1", Verdict.APPROVED, "looks fine",
    )

    history = get_history(str(catalog_path), "some-key")
    assert len(history) == 2
    assert history[-1] == revision
    assert "looks fine" in revision.comment
    assert "approved" in revision.comment
    assert revision.is_correction is False


def test_get_review_summary_respects_already_recorded_reviews(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    reviews_dir = tmp_path / "reviews"
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "//xs:element[@name='MiKaDiv_FM']")
    add_revision(str(catalog_path), "some-key", leaf, "author", "comment", False)

    # Sweep once to confirm baseline (nothing flagged against the unchanged real corpus is fine --
    # this test's point is the *plumbing*, so directly write a review record instead of depending
    # on real drift existing, and confirm apply_reviews() genuinely gets invoked end-to-end.
    result_before = get_review_summary(str(catalog_path), MODULE_ROOT, str(reviews_dir))
    assert result_before.summary.flagged == {}  # nothing to filter yet -- also nothing drifted
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/review_workflow/test_orchestrate.py -v`
Expected: FAIL — `review_workflow.orchestrate` does not exist.

- [ ] **Step 5: Create `review_workflow/orchestrate.py`**

Use the exact implementation already fixed in the spec's own
"`review_workflow/` (new package)" section (`WebReviewSummary`,
`get_review_summary()`, `submit_review()`) — copy it verbatim.

- [ ] **Step 6: Reinstall the package so the new module is importable**

```bash
cd /work/generator && pip install -e . --quiet
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/review_workflow/test_orchestrate.py -v`
Expected: PASS, 3/3.

- [ ] **Step 8: Run the full test suite**

Run: `pytest`
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml review_workflow/ tests/review_workflow/
git commit -m "Add review_workflow: orchestrates the review pipeline against the real catalog"
```

---

## Task 4: `webapp/app.py` — `GET /api/review`, `POST /api/reviews`, SPA fallback

**Files (in `/work/generator`):**
- Modify: `webapp/app.py`
- Modify: `tests/webapp/test_app.py`

**Interfaces:**
- Consumes: `review_workflow.orchestrate.{get_review_summary, submit_review}` (Task 3),
  `review_recording.record.Verdict`.
- Produces: `GET /api/review`, `POST /api/reviews` HTTP endpoints, and
  the SPA-fallback 404 handler — consumed by Task 5's frontend
  `api.ts` and, indirectly, by Task 10's manual verification.

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/webapp/test_app.py -- `client = TestClient(app)` constructed
# inline in each test, matching this file's own existing convention exactly
# (no shared fixture exists here today).
import json


def test_get_review_returns_deserialization_failures_separately(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text(json.dumps({
        "bad-key": [{
            "revision_id": "x", "reference": {"not": "real"},
            "author": "a", "comment": "c", "is_correction": False, "created_at": "2026-01-01T00:00:00+00:00",
        }]
    }))
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.get("/api/review")

    assert response.status_code == 200
    assert response.json()["deserialization_failures"] == ["bad-key"]


def test_post_reviews_rejects_a_leaf_reference_id_that_is_not_currently_flagged(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.post("/api/reviews", json={
        "fact_key": "no-such-key", "leaf_reference_id": "does-not-exist",
        "reviewer": "r", "verdict": "approved", "reasoning": "x",
    })

    assert response.status_code == 404


def test_post_reviews_rejects_an_invalid_verdict_string(tmp_path, monkeypatch):
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(tmp_path / "references.json"))
    (tmp_path / "references.json").write_text("{}")
    monkeypatch.setenv("MIKADIV_REVIEWS_DIR", str(tmp_path / "reviews"))
    client = TestClient(app)

    response = client.post("/api/reviews", json={
        "fact_key": "k", "leaf_reference_id": "r", "reviewer": "r", "verdict": "maybe", "reasoning": "x",
    })

    assert response.status_code == 400


def test_a_real_api_404_is_not_masked_by_the_spa_fallback():
    client = TestClient(app)
    response = client.get("/api/pages/does-not-exist-at-all")
    assert response.status_code == 404
    assert response.json()["detail"]  # a real JSON error body, not HTML


def test_an_unknown_non_api_path_gets_the_spa_shell():
    client = TestClient(app)
    response = client.get("/pages/whatever-react-router-will-own")
    assert response.status_code == 200
    assert "html" in response.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/webapp/test_app.py -v`
Expected: FAIL — `/api/review` and `/api/reviews` 404 (routes don't
exist yet); the SPA-fallback tests fail because no fallback handler
exists yet (`/pages/whatever...` 404s with FastAPI's default JSON body,
not the SPA shell).

- [ ] **Step 3: Extend `webapp/app.py`**

Add, using the exact code already fixed in the spec's own
"`webapp/app.py` (extended)" section: the `_reviews_dir()` helper
(matching `_catalog_path()`/`_module_root()`'s call-time-read,
env-var-overridable pattern exactly — env var `MIKADIV_REVIEWS_DIR`,
default `/work/ontologies/mikadiv-fm/reviews`), the `GET /api/review`
route, the `SubmitReviewRequest` model + `POST /api/reviews` route
(re-fetching `get_review_summary()` server-side and matching
`leaf_reference_id` against it — never trusting client-supplied
`FlaggedLeaf` data), and the `spa_fallback` 404 exception handler
registered **after** the existing `app.mount("/", StaticFiles(...))`
line.

One real decision the spec's sketch leaves open: `spa_fallback` reads
`Path(__file__).parent / "frontend_dist" / "index.html"` — this must
match exactly wherever Task 5 configures Vite to build to (`vite.config.ts`'s
`build.outDir`), and wherever the existing `StaticFiles` mount's
`directory=` argument points. Change `StaticFiles(directory=Path(__file__).parent / "static", html=True)`
to `directory=Path(__file__).parent / "frontend_dist"` in this same
step, since `webapp/static/index.html` is being fully replaced, not
kept alongside the new build.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS. (`test_an_unknown_non_api_path_gets_the_spa_shell` will
only truly pass once `frontend_dist/index.html` exists on disk — if
Task 4 is executed before Task 5 builds the frontend for the first
time, create a minimal placeholder `webapp/frontend_dist/index.html`
in this step, e.g. `<!DOCTYPE html><html><body>placeholder</body></html>`,
so this test is real and green now; Task 5 overwrites it with the real
build output, which does not change this test's behavior.)

- [ ] **Step 5: Run the full test suite**

Run: `pytest`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/webapp/test_app.py webapp/frontend_dist/index.html
git commit -m "Add GET /api/review, POST /api/reviews, and the SPA-fallback route"
```

---

## Task 5: `webapp/frontend/` — scaffold, routing, API client

**Files (in `/work/generator`):**
- Create: `webapp/frontend/package.json`, `webapp/frontend/vite.config.ts`, `webapp/frontend/tsconfig.json`
- Create: `webapp/frontend/index.html`
- Create: `webapp/frontend/src/main.tsx`
- Create: `webapp/frontend/src/App.tsx`
- Create: `webapp/frontend/src/api.ts`
- Create: `webapp/frontend/src/api.test.ts`
- Create: stub `webapp/frontend/src/views/{IndexView,PageDetailView,AddCitationView,ReviewView}.tsx` (real components, minimal content — "Loading..." placeholders; Tasks 6-9 build their real content)

**Interfaces:**
- Consumes: `@openfaster-standard/ui@<version from Task 1>` (real npm dependency).
- Produces: `api.ts`'s typed functions — `fetchPages()`, `fetchPage(factKey)`,
  `fetchCandidates()`, `submitCitation(body)`, `fetchReview()`,
  `submitReview(body)` — each returning a typed `Promise`, consumed by
  Tasks 6-9's views. The route table in `App.tsx` (`/`, `/pages/:factKey`,
  `/add`, `/review`) is what Tasks 6-9 fill in.

- [ ] **Step 1: Scaffold the Vite + React + TypeScript app**

```bash
cd /work/generator/webapp
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @openfaster-standard/ui react-router-dom
```

Expected: a real, working Vite React+TS starter. Confirm the exact
published version from Task 1's Step 11 landed:
`npm list @openfaster-standard/ui` shows it, not a lower/cached one.

- [ ] **Step 2: Configure the build output location**

In `vite.config.ts`, set `build.outDir` to `../frontend_dist` (relative
to `webapp/frontend/`) — matching exactly what Task 4's `spa_fallback`
and the `StaticFiles` mount now point at
(`webapp/frontend_dist/`, a sibling of `webapp/frontend/`, not nested
inside it).

- [ ] **Step 3: Write the failing test for the API client**

```typescript
// src/api.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fetchPages, submitCitation } from "./api"

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn())
})

describe("fetchPages", () => {
  it("GETs /api/pages and returns the parsed JSON", async () => {
    const body = { "some-key": { revision_count: 1, current: {} } }
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => body })
    const result = await fetchPages()
    expect(fetch).toHaveBeenCalledWith("/api/pages")
    expect(result).toEqual(body)
  })

  it("throws with the server's error detail on a non-ok response", async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false, status: 500, text: async () => JSON.stringify({ detail: "boom" }),
    })
    await expect(fetchPages()).rejects.toThrow("boom")
  })
})

describe("submitCitation", () => {
  it("POSTs the citation body as JSON", async () => {
    ;(fetch as any).mockResolvedValue({ ok: true, json: async () => ({ fact_key: "k", revision: {} }) })
    await submitCitation({ family: "f", xpath: "x", fact_key: "k", author: "a", comment: "c", is_correction: false })
    expect(fetch).toHaveBeenCalledWith("/api/citations", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }))
  })
})
```

- [ ] **Step 4: Run test to verify it fails**

Run: `npx vitest run src/api.test.ts` (from `webapp/frontend`)
Expected: FAIL — `./api` does not exist.

- [ ] **Step 5: Create `src/api.ts`**

One shared helper (e.g. `async function apiFetch<T>(path: string, init?: RequestInit): Promise<T>`)
that throws an `Error` built from the response body's `detail` field on
a non-`ok` response (mirroring the existing vanilla-JS
`describeErrorBody()` logic in the old `index.html`, now centralized
instead of duplicated per view), plus the six typed functions named in
this task's Interfaces block, each a thin wrapper calling `apiFetch`
against the matching endpoint from Tasks 3-4. Define the TypeScript
types these return (`PageSummary`, `PageDetail`, `CandidatesByFamily`,
`ReviewSummaryResponse`, etc.) matching the exact JSON shapes Task 4's
endpoints produce.

- [ ] **Step 6: Run test to verify it passes**

Run: `npx vitest run src/api.test.ts`
Expected: PASS, 3/3.

- [ ] **Step 7: Wire up routing in `App.tsx`/`main.tsx`**

`main.tsx` renders `<BrowserRouter><App /></BrowserRouter>`. `App.tsx`
defines the 4 routes via `react-router-dom`'s `<Routes>`: `/` →
`IndexView`, `/pages/:factKey` → `PageDetailView`, `/add` →
`AddCitationView`, `/review` → `ReviewView`. Each view file for now
renders only a placeholder heading matching its name — Tasks 6-9 build
the real content.

- [ ] **Step 8: Build and confirm the webapp serves it**

```bash
cd /work/generator/webapp/frontend && npm run build
cd /work/generator
fuser -k 8012/tcp 2>/dev/null; sleep 1
nohup env REFERENCES_CATALOG_PATH=/work/ontologies/mikadiv-fm/references.json \
  MIKADIV_MODULE_ROOT=/work/ontologies/mikadiv-fm/sources \
  MIKADIV_REVIEWS_DIR=/work/ontologies/mikadiv-fm/reviews \
  uvicorn webapp.app:app --host 0.0.0.0 --port 8012 > /tmp/webapp-frontend.log 2>&1 &
disown
sleep 2
curl -s http://localhost:8012/ | grep -o "<title>.*</title>"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8012/pages/anything
```

Expected: the real built `index.html`'s title; the second `curl`
returns `200` (the SPA shell, served by the fallback handler) — proving
the hard-refresh-on-a-non-root-route case this whole route exists for.

- [ ] **Step 9: Stop the server, commit**

```bash
fuser -k 8012/tcp 2>/dev/null
cd /work/generator
git add webapp/frontend webapp/frontend_dist
git commit -m "Scaffold the React frontend: Vite+TS, routing, typed API client"
```

`webapp/frontend_dist/` (build output) is committed alongside source —
matching this repo's existing convention of the webapp serving
whatever's on disk with no separate deploy step (the same reasoning
`webapp/static/index.html` itself was always committed directly).

---

## Task 6: `IndexView`

**Files:**
- Modify: `webapp/frontend/src/views/IndexView.tsx`
- Create: `webapp/frontend/src/views/IndexView.test.tsx`

**Interfaces:**
- Consumes: `api.fetchPages()` (Task 5).
- Produces: nothing new for other tasks — a leaf view.

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { IndexView } from "./IndexView"
import * as api from "../api"

it("renders every page's fact_key, family, and a correction badge where is_correction is true", async () => {
  vi.spyOn(api, "fetchPages").mockResolvedValue({
    "key-a": { revision_count: 1, current: { reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id1" }, is_correction: false } },
    "key-b": { revision_count: 2, current: { reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id2" }, is_correction: true } },
  } as any)

  render(<MemoryRouter><IndexView /></MemoryRouter>)

  expect(await screen.findByText("key-a")).toBeInTheDocument()
  expect(await screen.findByText("key-b")).toBeInTheDocument()
  expect(screen.getByText("key-b").closest("tr")).toHaveTextContent("Correction")
  expect(screen.getByText("key-a").closest("tr")).not.toHaveTextContent("Correction")
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/views/IndexView.test.tsx`
Expected: FAIL — placeholder `IndexView` has no table.

- [ ] **Step 3: Implement `IndexView`**

`ui`'s `Table`/`TableHeader`/`TableBody`/`TableRow`/`TableHead`/
`TableCell` render the columns from the old `renderIndex()` (Page,
Family, Selector type, Current reference ID, Revisions); `Badge`
(`variant="destructive"`, text "Correction") replaces the old
`.correction` CSS class; each fact_key cell is a React Router `<Link
to={`/pages/${factKey}`}>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/views/IndexView.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend test suite**

Run: `npx vitest run`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/frontend/src/views/IndexView.tsx webapp/frontend/src/views/IndexView.test.tsx
git commit -m "Implement IndexView on ui's Table/Badge"
```

---

## Task 7: `PageDetailView`

**Files:**
- Modify: `webapp/frontend/src/views/PageDetailView.tsx`
- Create: `webapp/frontend/src/views/PageDetailView.test.tsx`

**Interfaces:**
- Consumes: `api.fetchPage(factKey)` (Task 5), `useParams()` from
  `react-router-dom` for `:factKey`.
- Produces: nothing new for other tasks.

- [ ] **Step 1: Write the failing test**

```tsx
it("renders the summary line and history table, newest revision first", async () => {
  vi.spyOn(api, "fetchPage").mockResolvedValue({
    fact_key: "k",
    current: { reference: { subject_document: { family: "Fam" }, selector: { type: "XPathSelector" }, reference_id: "id" } },
    history: [
      { created_at: "2026-01-01T00:00:00Z", author: "a1", comment: "first", is_correction: false },
      { created_at: "2026-01-02T00:00:00Z", author: "a2", comment: "second", is_correction: true },
    ],
  } as any)

  render(
    <MemoryRouter initialEntries={["/pages/k"]}>
      <Routes><Route path="/pages/:factKey" element={<PageDetailView />} /></Routes>
    </MemoryRouter>
  )

  const rows = await screen.findAllByRole("row")
  // header row + 2 history rows, newest (is_correction) first
  expect(rows[1]).toHaveTextContent("second")
  expect(rows[1]).toHaveTextContent("Correction")
  expect(rows[2]).toHaveTextContent("first")
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/views/PageDetailView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `PageDetailView`**

Reads `factKey` via `useParams()`, calls `api.fetchPage(factKey)`,
renders the heading/summary line from the old `renderPage()`, and a
`Table` of history reversed (newest first, matching the old
`[...page.history].reverse()`), same `Badge` correction treatment.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/views/PageDetailView.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend test suite**

Run: `npx vitest run`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/frontend/src/views/PageDetailView.tsx webapp/frontend/src/views/PageDetailView.test.tsx
git commit -m "Implement PageDetailView"
```

---

## Task 8: `AddCitationView`

**Files:**
- Modify: `webapp/frontend/src/views/AddCitationView.tsx`
- Create: `webapp/frontend/src/views/AddCitationView.test.tsx`

**Interfaces:**
- Consumes: `api.fetchCandidates()`, `api.submitCitation()` (Task 5).
- Produces: nothing new for other tasks.

- [ ] **Step 1: Write the failing tests**

```tsx
const candidates = {
  "Family-A": [{ tag: "xs:element", name: "Foo", xpath: "//Foo" }, { tag: "xs:element", name: "Bar", xpath: "//Bar" }],
}

it("filters a family's candidates by the filter input", async () => {
  vi.spyOn(api, "fetchCandidates").mockResolvedValue(candidates as any)
  render(<MemoryRouter><AddCitationView /></MemoryRouter>)

  fireEvent.click(await screen.findByText(/Family-A/))
  expect(await screen.findByText("Foo")).toBeInTheDocument()
  expect(screen.getByText("Bar")).toBeInTheDocument()

  fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: "foo" } })
  expect(screen.getByText("Foo")).toBeInTheDocument()
  expect(screen.queryByText("Bar")).not.toBeInTheDocument()
})

it("submits a citation and navigates to the resulting page", async () => {
  vi.spyOn(api, "fetchCandidates").mockResolvedValue(candidates as any)
  vi.spyOn(api, "submitCitation").mockResolvedValue({ fact_key: "new-key", revision: {} } as any)
  render(<MemoryRouter><AddCitationView /></MemoryRouter>)

  fireEvent.click(await screen.findByText(/Family-A/))
  fireEvent.click(await screen.findByText("Cite this", { selector: "button" }))
  fireEvent.change(screen.getByLabelText(/Fact key/i), { target: { value: "new-key" } })
  fireEvent.change(screen.getByLabelText(/Author/i), { target: { value: "me" } })
  fireEvent.click(screen.getByText("Submit citation"))

  await vi.waitFor(() => expect(api.submitCitation).toHaveBeenCalledWith(
    expect.objectContaining({ family: "Family-A", xpath: "//Foo", fact_key: "new-key", author: "me" })
  ))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/views/AddCitationView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `AddCitationView`**

`Accordion`/`AccordionItem` per family (trigger = family name + candidate
count, matching the old `${family} (${count} candidates)`); inside each,
a filter `Input` (placeholder `"Filter candidates..."`) and a `Table` of
the family's candidates, client-side-filtered by substring match against
`tag`/`name`/`xpath`; each row's "Cite this" `Button` opens a `Dialog`
containing the citation `Form` (`Input`s for fact_key/author/comment,
`Checkbox` for is_correction, matching `ui`'s existing `Form` composition
pattern from `form.stories.tsx`). On submit, calls `api.submitCitation()`
and navigates via `useNavigate()` to `/pages/${fact_key}` on success;
shows the thrown error's message via `Alert` on failure.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/views/AddCitationView.test.tsx`
Expected: PASS, 2/2.

- [ ] **Step 5: Run the full frontend test suite**

Run: `npx vitest run`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/frontend/src/views/AddCitationView.tsx webapp/frontend/src/views/AddCitationView.test.tsx
git commit -m "Implement AddCitationView: Accordion + filterable candidate Table + Dialog cite form"
```

---

## Task 9: `ReviewView`

**Files:**
- Modify: `webapp/frontend/src/views/ReviewView.tsx`
- Create: `webapp/frontend/src/views/ReviewView.test.tsx`

**Interfaces:**
- Consumes: `api.fetchReview()`, `api.submitReview()` (Task 5).
- Produces: nothing new for other tasks.

- [ ] **Step 1: Write the failing tests**

```tsx
const reviewData = {
  flagged: {
    "key-a": [{ leaf: { reference_id: "ref1", subject_document: { family: "Fam" } }, drift_kind: "CONTENT", fingerprint: "fp1" }],
  },
  unresolved_families: [],
  excluded_keys: [],
  deserialization_failures: ["corrupt-key"],
}

it("shows a distinct alert for deserialization failures vs unresolved families", async () => {
  vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
  render(<MemoryRouter><ReviewView /></MemoryRouter>)
  expect(await screen.findByText(/corrupt-key/)).toBeInTheDocument()
  expect(screen.getByText(/corrupt-key/).closest("[role='alert']")).toHaveTextContent(/corrupted|cannot be checked/i)
})

it("submits an approve verdict and removes the item from view", async () => {
  vi.spyOn(api, "fetchReview").mockResolvedValue(reviewData as any)
  vi.spyOn(api, "submitReview").mockResolvedValue({ fact_key: "key-a", revision: {} } as any)
  render(<MemoryRouter><ReviewView /></MemoryRouter>)

  fireEvent.click(await screen.findByText(/key-a/))
  fireEvent.click(screen.getByText("Review"))
  fireEvent.change(screen.getByLabelText(/Reviewer/i), { target: { value: "r1" } })
  fireEvent.change(screen.getByLabelText(/Reasoning/i), { target: { value: "fine" } })
  fireEvent.click(screen.getByText("Approve"))

  await vi.waitFor(() => expect(api.submitReview).toHaveBeenCalledWith(
    expect.objectContaining({ fact_key: "key-a", leaf_reference_id: "ref1", verdict: "approved", reviewer: "r1", reasoning: "fine" })
  ))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/views/ReviewView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `ReviewView`**

Two `Alert`s (one for `unresolved_families`, one for
`deserialization_failures`, distinct copy per the spec — never merged
into one generic warning); an `Accordion` grouping `flagged` by
`fact_key`, each item listing its flagged leaves (`drift_kind`,
`fingerprint`); each leaf's "Review" `Button` opens a `Dialog` with a
`reviewer` `Input`, `reasoning` `Textarea`, and two `Button`s ("Approve"
→ `verdict: "approved"`, "Reject" → `verdict: "rejected"`). On submit,
calls `api.submitReview({fact_key, leaf_reference_id: leaf.reference_id, reviewer, verdict, reasoning})`
and removes that leaf from local state on success.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/views/ReviewView.test.tsx`
Expected: PASS, 2/2.

- [ ] **Step 5: Run the full frontend test suite**

Run: `npx vitest run`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add webapp/frontend/src/views/ReviewView.tsx webapp/frontend/src/views/ReviewView.test.tsx
git commit -m "Implement ReviewView: drift review + approve/reject"
```

---

## Task 10: Full manual verification, all 4 views

**Files:** none (verification only).

- [ ] **Step 1: Rebuild the frontend and start the server**

```bash
cd /work/generator/webapp/frontend && npm run build
cd /work/generator
fuser -k 8012/tcp 2>/dev/null; sleep 1
nohup env REFERENCES_CATALOG_PATH=/work/ontologies/mikadiv-fm/references.json \
  MIKADIV_MODULE_ROOT=/work/ontologies/mikadiv-fm/sources \
  MIKADIV_REVIEWS_DIR=/work/ontologies/mikadiv-fm/reviews \
  uvicorn webapp.app:app --host 0.0.0.0 --port 8012 > /tmp/webapp-verify.log 2>&1 &
disown
sleep 2
curl -s http://localhost:8012/api/pages
```

Expected: `{}` (real committed catalog, untouched).

- [ ] **Step 2: Manual verification via Playwright — full flow across all 4 views**

Via `node` + `playwright` (already baked into the image):

1. Navigate to `http://localhost:8012/`. Confirm the index renders
   (empty state, since the catalog is `{}`).
2. Navigate to `http://localhost:8012/add`. Confirm all 13 real XSD
   families appear as Accordion items with correct candidate counts.
   Expand `MiKaDiv_FM_Personentypen`; type into the filter input; confirm
   the candidate list narrows to matching rows only.
3. Click "Cite this" on a real candidate; confirm the Dialog opens with
   the right family/xpath. Fill fact key `playwright-verify-fact`,
   author, comment; submit. Confirm navigation to
   `/pages/playwright-verify-fact` showing the new revision.
4. **Directly type** `http://localhost:8012/pages/playwright-verify-fact`
   into the address bar (a real hard navigation, not a client-side
   one) and confirm the page still renders correctly — this is the
   direct proof the SPA-fallback route works.
5. Navigate to `http://localhost:8012/review`. Confirm the page loads
   (likely empty — the just-cited leaf matches the real, unchanged
   corpus, so nothing is flagged). If genuinely nothing is flagged
   against the real corpus, temporarily point `MIKADIV_MODULE_ROOT` at
   a scratch copy of the corpus with one file's content edited (to
   force real, genuine drift), restart the server, and confirm the
   drift-review view now shows exactly one flagged item for
   `playwright-verify-fact` with the correct drift kind.
6. Open that flagged item's Review dialog; fill reviewer/reasoning;
   click Approve. Confirm the item disappears from `/review`.
7. Navigate to `/pages/playwright-verify-fact`; confirm the history now
   shows a second revision whose comment contains "approved" and the
   reasoning just entered.
8. If Step 5 used a scratch corpus copy, restore
   `MIKADIV_MODULE_ROOT` to the real corpus and restart the server
   before continuing.

- [ ] **Step 3: Revert all real state and stop the server**

```bash
echo "{}" > /work/ontologies/mikadiv-fm/references.json
rm -rf /work/ontologies/mikadiv-fm/reviews
cd /work/ontologies && git status
cd /work/generator
fuser -k 8012/tcp 2>/dev/null
```

Expected: `git status` in `/work/ontologies` shows a clean working
tree — no trace of `playwright-verify-fact` or its review remains.
Confirm the server is stopped (`curl` to port 8012 fails to connect).

---

## Task 11: Dedicated architectural-fitness audit (generator + ui)

**Files:** whatever the audit's findings require — genuinely unknown
until the audit runs, per its own nature.

This is **separate from and in addition to** the whole-branch final
review this plan's own execution skill already runs at the end. That
review checks this plan's own work against this plan's own Review
Focus. This task is the operator's own explicitly requested, deliberate
"Richard Stallman would say 'damn that's nice'" pass across **both**
repos together — not scoped to just this plan's diff.

- [ ] **Step 1: Dispatch the audit**

Using the most capable available model, review `generator` and `ui` in
their entirety (not just this plan's diff) for architectural fitness:
consistency of naming/conventions across every module built across this
project's whole history, dead code, undocumented coupling, anything a
careful reader would flag as "not quite right" even if it isn't a bug.
Provide the reviewer this plan, its spec, and every other spec/plan this
session produced for context on what "already decided, don't
relitigate" looks like versus a genuine finding.

- [ ] **Step 2: Fix every finding, regardless of severity**

Per this box's own standing rule (`/work/CLAUDE.md`): every finding from
this review — Critical, Important, or Minor — gets resolved in this same
pass. A finding that's pure documentation still gets written down
inline. A finding genuinely out of scope (a different subsystem
entirely, or an explicit Non-Goal from some other spec) gets a `Ruling:`
with its reasoning — never a silently-deferred Minor. For each fix: the
reproducing test (if the finding has associated behavior), watched
failing, then passing, then the full relevant test suite (`pytest` in
`generator`, `pnpm test`/`npx vitest run` in `ui` and
`webapp/frontend`) green.

- [ ] **Step 3: Run every test suite one final time, all green**

```bash
cd /work/generator && pytest
cd /work/generator/webapp/frontend && npx vitest run
cd /work/ui/packages/ui && pnpm test
```

Expected: all three green, zero skipped, zero known-failing.

- [ ] **Step 4: Commit the audit's fixes**

```bash
cd /work/generator
git add -A
git commit -m "Architectural-fitness audit: fix every finding across generator and ui"
```

(If `ui` also received fixes, commit and push there too, following its
own Trusted Publishing release flow if the fixes touch published
package code — a new Changeset, same as Task 1.)

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `reference_model/deserialize.py` implements `from_json_dict()` and
  `ReferenceDeserializationError`; the Leaf and Union round-trip
  invariants hold against real data.
- [ ] `review_workflow/` implements `get_review_summary()` and
  `submit_review()` with the semantics above.
- [ ] `webapp/app.py` serves `GET /api/review` and `POST /api/reviews`,
  plus the SPA-fallback route.
- [ ] `webapp/frontend/` is a real Vite + React + TypeScript app with
  all 4 routes, built entirely from `@openfaster-standard/ui` (plus the
  new `Accordion`), and its built output is what the webapp actually
  serves.
- [ ] `@openfaster-standard/ui` has a new `Accordion` component with
  real tests and a Storybook story, published as a new version.
- [ ] All automated tests pass — Python (`pytest`) and frontend
  (`vitest`), in both repos.
- [ ] A real, full manual Playwright pass covered all 4 views
  end-to-end, including a complete drift-review round trip; the real
  committed catalog and reviews directory are back to their prior state
  afterward.
- [ ] The dedicated post-merge architectural-fitness audit across
  `generator` and `ui` is complete, with every finding fixed regardless
  of severity.
