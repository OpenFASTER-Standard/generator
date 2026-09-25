# Citation Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the interaction layer from
`docs/specs/2026-09-25-citation-workflow-design.md`: connect
`discover_candidates()`, a corpus-wide candidate browser, and
`add_revision()`'s create/edit unification into a real "browse real
candidates → submit a real citation" flow, reachable from a browser.

**Architecture:** Five tasks, bottom-up. Task 1 extends an existing,
already-merged file (`staleness_sweep/resolve.py`) with a pure refactor
plus one new function. Task 2 builds a new discovery-layer module on top
of it. Task 3 builds a new orchestration module on top of that. Task 4
exposes Task 3 over HTTP. Task 5 is the browser-facing UI consuming
Task 4's endpoints. Every later task consumes the previous one's real
interface, never a stub.

**Tech Stack:** Python 3.11, `lxml`/`fastapi`/`uvicorn`/`pydantic`
(already dependencies — `pydantic` ships transitively via `fastapi`, no
new dependency needed), plus the real MiKaDiv-FM corpus.

**Spec:** `docs/specs/2026-09-25-citation-workflow-design.md`

## Global Constraints

- Task 1 is a **refactor, not a rewrite** of
  `staleness_sweep/resolve.py`: `resolve_current_location()`'s own
  observable behavior must not change at all. Its existing test file,
  `tests/staleness_sweep/test_resolve.py` (14 tests), is **not modified**
  by this plan — it must keep passing completely unchanged, proving the
  refactor is behavior-preserving. New tests for the new
  `list_current_locations()` function go in a **separate** new test file.
- `CorpusCandidate` (Task 2) deliberately has **no** `family`/`version`/
  `retrieval_uri` fields — the citation step (Task 3) always re-resolves
  `family` server-side via `list_current_locations()`, never trusting a
  client-supplied path. This is a security/correctness property, not a
  style choice: it is the only thing standing between an `/api/citations`
  caller and citing an arbitrary file on disk.
- `add_citation()` (Task 3) re-raises `reference_model.cite.CitationError`
  unchanged when a candidate's `xpath` no longer resolves (e.g. because
  the underlying XSD changed between candidate-listing and submission) —
  it does not swallow or wrap it. The webapp layer (Task 4) is what maps
  it to HTTP 400.
- `pyproject.toml`'s `[tool.setuptools.packages.find]` include list gets
  `"citation_workflow*"` added in Task 3 — the new package is not
  importable without it.
- The static page still has **no automated test** — this project's own
  established convention (no frontend test runner). A manual, required
  Playwright verification step replaces it, exactly as it has for every
  prior `webapp`-touching plan.
- The real committed `ontologies/mikadiv-fm/references.json` must remain
  exactly `{}` after the manual verification step in Task 5 — any real
  citation submitted during that verification must be reverted.
- No full optimistic-concurrency/CAS protection — already reconsidered
  and explicitly deferred in the spec's Non-Goals (the race window here
  is one HTTP `POST`, not a long-lived editing session). Not revisited in
  this plan.

## Review Focus

- **The `resolve.py` refactor must genuinely change zero observable
  behavior.** A reasonable person relying on `resolve_current_location()`
  elsewhere in the codebase should see no difference at all after this
  plan merges. Tested directly in Task 1 by running the existing,
  untouched `tests/staleness_sweep/test_resolve.py` (14 tests) against
  the refactored file.
- **`add_citation()` must re-resolve `family` server-side, never trust a
  client-supplied `retrieval_uri`.** A reasonable person would expect the
  citation endpoint to always cite the real, current corpus file for a
  family — not whatever path a request happened to include — since
  `CorpusCandidate` never carries one in the first place. Tested directly
  in Task 3 (an unknown family raises without creating any page) and
  Task 4 (the same, over HTTP).
- **A candidate that was valid when listed but has since gone stale must
  map to HTTP 400, not a 500.** A reasonable person clicking "Cite this"
  on a candidate a moment after the underlying file changed underneath it
  should see a clear rejection, not an opaque server error. Tested
  directly in Task 4 with a real, synthetic snapshot that is mutated
  between candidate discovery and citation submission.
- **Citing the same `fact_key` twice through this new layer must append a
  second revision, not fail or silently overwrite.** This is the whole
  point of routing through `add_revision()`'s create/edit unification
  rather than a separate create-only path. Tested directly in Task 3.
- **`list_corpus_candidates()` must include only XSD families, never any
  of the 8 real PDF families**, since `discover_candidates()` only
  understands XML Schema. A reasonable person calling this function
  should not get a silent `KeyError`/crash, or a bogus empty list, for a
  PDF family — it should simply not appear. Tested directly in Task 2
  against the real corpus's exact family split (13 XSD, 8 PDF).

---

## Task 1: `staleness_sweep/resolve.py` (refactor + new function)

**Files:**
- Modify: `staleness_sweep/resolve.py` (refactor `resolve_current_location()`'s
  internals into two private helpers; add `FamilyLocation` +
  `list_current_locations()`)
- Do **not** modify: `tests/staleness_sweep/test_resolve.py` — it must
  keep passing completely unchanged
- Create: `tests/staleness_sweep/test_list_current_locations.py`

**Interfaces:**
- Consumes: `ResolutionOutcome`, `Status` (`reference_model.model`) —
  already merged, unchanged.
- Produces: `FamilyLocation(family, version, retrieval_uri)`,
  `list_current_locations(module_root: str) -> list[FamilyLocation]`.
  `resolve_current_location(module_root: str, family: str) ->
  ResolutionOutcome` and `CorpusIntegrityError` are unchanged in name,
  signature, and behavior.

- [ ] **Step 1: Confirm the existing test file's current baseline**

Run: `pytest tests/staleness_sweep/test_resolve.py -v`
Expected: PASS (14 tests). This is the baseline this task must not
disturb — re-run it again after Step 3 and it must show the identical
14 tests, unmodified, still passing.

- [ ] **Step 2: Write the failing tests for `list_current_locations()`**

Create `tests/staleness_sweep/test_list_current_locations.py`:

```python
from pathlib import Path

from staleness_sweep.resolve import FamilyLocation, list_current_locations

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

REAL_FAMILIES = {
    "MiKaDiv_FM",
    "MiKaDiv_FM_Fachtypen",
    "MiKaDiv_FM_Meldeart11",
    "MiKaDiv_FM_Meldeart13",
    "MiKaDiv_FM_Meldeart21",
    "MiKaDiv_FM_Meldeart22",
    "MiKaDiv_FM_Meldeart23",
    "MiKaDiv_FM_MeldeartErg",
    "MiKaDiv_FM_MeldeartenBasis",
    "MiKaDiv_FM_MeldeartenSonder",
    "MiKaDiv_FM_Personentypen",
    "MiKaDiv_FM_Standardtypen",
    "din-norm-91379-datatypes",
    "ausstellung_steuerbescheinigung",
    "einzelfragen_datenuebermittlung_de",
    "individual_questions_en",
    "khb_mikadiv_fm_anlage_de",
    "khb_mikadiv_fm_anlage_en",
    "khb_mikadiv_fm_de",
    "khb_mikadiv_fm_en",
    "verfahrensleitende_hinweise",
}


def test_lists_all_21_real_families_with_correct_version_and_existing_paths():
    locations = list_current_locations(REAL_MODULE_ROOT)

    assert len(locations) == 21
    assert {loc.family for loc in locations} == REAL_FAMILIES
    for loc in locations:
        assert loc.version == "1.02"
        assert Path(loc.retrieval_uri).exists()


def test_a_real_xsd_family_resolves_to_the_same_path_resolve_current_location_would():
    locations = {loc.family: loc for loc in list_current_locations(REAL_MODULE_ROOT)}

    expected = str(Path(REAL_MODULE_ROOT) / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd")
    assert locations["MiKaDiv_FM_Meldeart23"].retrieval_uri == expected


def test_results_are_sorted_by_family_name():
    locations = list_current_locations(REAL_MODULE_ROOT)
    families = [loc.family for loc in locations]
    assert families == sorted(families)


def test_missing_current_pointer_returns_empty_list(tmp_path):
    assert list_current_locations(str(tmp_path)) == []


def test_returns_family_location_instances():
    locations = list_current_locations(REAL_MODULE_ROOT)
    assert all(isinstance(loc, FamilyLocation) for loc in locations)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/staleness_sweep/test_list_current_locations.py -v`
Expected: FAIL — `ImportError: cannot import name 'list_current_locations'
from 'staleness_sweep.resolve'` (and `FamilyLocation` doesn't exist
either), since neither exists yet.

- [ ] **Step 4: Replace the full contents of `staleness_sweep/resolve.py`**

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

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `pytest tests/staleness_sweep/test_list_current_locations.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Confirm the existing test file is still completely
  unaffected**

Run: `pytest tests/staleness_sweep/test_resolve.py -v`
Expected: PASS (14 tests) — the identical 14 test names as Step 1, file
untouched, all still green. This is the proof the refactor is
behavior-preserving.

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (180 tests: 175 previously passing, plus 5 new)

- [ ] **Step 8: Commit**

```bash
git add staleness_sweep/resolve.py tests/staleness_sweep/test_list_current_locations.py
git commit -m "Add list_current_locations() to staleness_sweep.resolve"
```

---

## Task 2: `discovery/corpus_candidates.py` (new)

**Files:**
- Create: `discovery/corpus_candidates.py`
- Create: `tests/discovery/test_corpus_candidates.py`

**Interfaces:**
- Consumes: `list_current_locations` (`staleness_sweep.resolve`, Task 1);
  `discover_candidates` (`discovery.xsd_discoverer`, already merged).
- Produces: `CorpusCandidate(tag, name, xpath)`,
  `list_corpus_candidates(module_root: str) -> dict[str,
  list[CorpusCandidate]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/discovery/test_corpus_candidates.py`:

```python
from discovery.corpus_candidates import CorpusCandidate, list_corpus_candidates

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

REAL_XSD_FAMILIES = {
    "MiKaDiv_FM",
    "MiKaDiv_FM_Fachtypen",
    "MiKaDiv_FM_Meldeart11",
    "MiKaDiv_FM_Meldeart13",
    "MiKaDiv_FM_Meldeart21",
    "MiKaDiv_FM_Meldeart22",
    "MiKaDiv_FM_Meldeart23",
    "MiKaDiv_FM_MeldeartErg",
    "MiKaDiv_FM_MeldeartenBasis",
    "MiKaDiv_FM_MeldeartenSonder",
    "MiKaDiv_FM_Personentypen",
    "MiKaDiv_FM_Standardtypen",
    "din-norm-91379-datatypes",
}

REAL_PER_FAMILY_COUNTS = {
    "MiKaDiv_FM": 47,
    "MiKaDiv_FM_Fachtypen": 85,
    "MiKaDiv_FM_Meldeart11": 1,
    "MiKaDiv_FM_Meldeart13": 18,
    "MiKaDiv_FM_Meldeart21": 14,
    "MiKaDiv_FM_Meldeart22": 19,
    "MiKaDiv_FM_Meldeart23": 5,
    "MiKaDiv_FM_MeldeartErg": 2,
    "MiKaDiv_FM_MeldeartenBasis": 22,
    "MiKaDiv_FM_MeldeartenSonder": 8,
    "MiKaDiv_FM_Personentypen": 127,
    "MiKaDiv_FM_Standardtypen": 73,
    "din-norm-91379-datatypes": 1,
}


def test_returns_exactly_the_13_real_xsd_families_never_any_pdf_family():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    assert set(result.keys()) == REAL_XSD_FAMILIES


def test_real_per_family_candidate_counts_match_live_verification():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    for family, expected_count in REAL_PER_FAMILY_COUNTS.items():
        assert len(result[family]) == expected_count, family


def test_total_real_candidate_count_across_the_whole_corpus_is_422():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    assert sum(len(candidates) for candidates in result.values()) == 422


def test_a_known_real_candidate_appears_with_the_correct_xpath():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    aordnr_xpath = (
        "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
        "/xs:sequence/xs:element[@name='AOrdNr']"
    )
    matches = [c for c in result["MiKaDiv_FM_Meldeart23"] if c.xpath == aordnr_xpath]
    assert len(matches) == 1
    assert matches[0].name == "AOrdNr"
    assert matches[0].tag == "element"


def test_returns_corpus_candidate_instances_with_no_family_or_location_fields():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    sample = result["MiKaDiv_FM_Meldeart23"][0]
    assert isinstance(sample, CorpusCandidate)
    assert not hasattr(sample, "family")
    assert not hasattr(sample, "retrieval_uri")


def test_on_corpus_with_no_current_pointer_returns_empty_dict(tmp_path):
    assert list_corpus_candidates(str(tmp_path)) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/discovery/test_corpus_candidates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'discovery.corpus_candidates'`.

- [ ] **Step 3: Create `discovery/corpus_candidates.py`**

```python
"""Lists every citable candidate across the whole real corpus, grouped by
family, by combining staleness_sweep's current-snapshot listing with
discover_candidates() per XSD family. See
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
    result: dict[str, list[CorpusCandidate]] = {}
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/discovery/test_corpus_candidates.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (186 tests: 180 from Task 1, plus 6 new)

- [ ] **Step 6: Commit**

```bash
git add discovery/corpus_candidates.py tests/discovery/test_corpus_candidates.py
git commit -m "Add list_corpus_candidates() grouping real candidates by family"
```

---

## Task 3: `citation_workflow/add_citation.py` (new package)

**Files:**
- Create: `citation_workflow/__init__.py` (empty)
- Create: `citation_workflow/add_citation.py`
- Modify: `pyproject.toml` (add `"citation_workflow*"` to
  `[tool.setuptools.packages.find]`'s `include` list)
- Create: `tests/citation_workflow/__init__.py` (empty, matching this
  repo's existing `tests/<package>/` layout)
- Create: `tests/citation_workflow/test_add_citation.py`

**Interfaces:**
- Consumes: `list_current_locations` (`staleness_sweep.resolve`, Task 1);
  `cite`, `CitationError` (`reference_model.cite`, already merged);
  `SubjectDocument` (`reference_model.model`, already merged);
  `XPathSelector` (`reference_model.selectors.xpath_selector`, already
  merged); `Revision`, `add_revision` (`references_catalog.catalog`,
  already merged).
- Produces: `FamilyNotFoundError`, `add_citation(module_root: str,
  catalog_path: str | Path, family: str, xpath: str, fact_key: str,
  author: str, comment: str, is_correction: bool) -> Revision`.

- [ ] **Step 1: Update `pyproject.toml`**

In `[tool.setuptools.packages.find]`, change:

```toml
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*", "webapp*", "references_catalog*", "discovery*"]
```

to:

```toml
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*", "webapp*", "references_catalog*", "discovery*", "citation_workflow*"]
```

- [ ] **Step 2: Create empty package markers**

```bash
mkdir -p citation_workflow tests/citation_workflow
touch citation_workflow/__init__.py tests/citation_workflow/__init__.py
```

- [ ] **Step 3: Write the failing tests**

Create `tests/citation_workflow/test_add_citation.py`:

```python
import pytest

from citation_workflow.add_citation import FamilyNotFoundError, add_citation
from reference_model.cite import CitationError, cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import get_history

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _empty_catalog(tmp_path) -> str:
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    return str(catalog_path)


def test_add_citation_creates_a_page_matching_a_direct_cite_call(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    revision = add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=AORDNR_XPATH,
        fact_key="fact-1", author="julian", comment="initial citation", is_correction=False,
    )

    expected_leaf = cite(
        SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD),
        XPathSelector.create(AORDNR_XPATH),
    )
    history = get_history(catalog_path, "fact-1")
    assert len(history) == 1
    assert history[0].revision_id == revision.revision_id
    assert history[0].reference["reference_id"] == to_json_dict(expected_leaf)["reference_id"]
    assert history[0].author == "julian"
    assert history[0].is_correction is False


def test_add_citation_raises_family_not_found_without_creating_a_page(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    with pytest.raises(FamilyNotFoundError):
        add_citation(
            REAL_MODULE_ROOT, catalog_path,
            family="NoSuchFamilyEver", xpath="/x",
            fact_key="fact-2", author="julian", comment="x", is_correction=False,
        )

    assert get_history(catalog_path, "fact-2") == []


def test_add_citation_twice_for_same_fact_key_appends_a_second_revision(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=AORDNR_XPATH,
        fact_key="fact-3", author="julian", comment="first version", is_correction=False,
    )
    revision_2 = add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=ABGEF_XPATH,
        fact_key="fact-3", author="julian", comment="corrected", is_correction=True,
    )

    history = get_history(catalog_path, "fact-3")
    assert len(history) == 2
    assert history[1].revision_id == revision_2.revision_id
    assert history[1].is_correction is True


def test_add_citation_with_an_xpath_that_does_not_resolve_raises_citation_error(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    with pytest.raises(CitationError):
        add_citation(
            REAL_MODULE_ROOT, catalog_path,
            family="MiKaDiv_FM_Meldeart23", xpath="/xs:schema/xs:complexType[@name='NoSuchThing']",
            fact_key="fact-4", author="julian", comment="x", is_correction=False,
        )

    assert get_history(catalog_path, "fact-4") == []
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/citation_workflow/test_add_citation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named
'citation_workflow.add_citation'`.

- [ ] **Step 5: Create `citation_workflow/add_citation.py`**

```python
"""Connects candidate discovery to the catalog: given a family + xpath a
human picked from list_corpus_candidates(), re-resolves the family's real
current location server-side, builds and verifies a fresh citation, and
records it as a new revision. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from pathlib import Path

from reference_model.cite import cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import Revision, add_revision
from staleness_sweep.resolve import list_current_locations


class FamilyNotFoundError(Exception):
    pass


def add_citation(
    module_root: str,
    catalog_path: str | Path,
    family: str,
    xpath: str,
    fact_key: str,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    locations = {loc.family: loc for loc in list_current_locations(module_root)}
    if family not in locations:
        raise FamilyNotFoundError(f"no such family in the current corpus snapshot: {family!r}")
    location = locations[family]
    subject_document = SubjectDocument(
        family=location.family,
        version=location.version,
        retrieval_uri=location.retrieval_uri,
    )
    leaf = cite(subject_document, XPathSelector.create(xpath))
    return add_revision(catalog_path, fact_key, leaf, author, comment, is_correction)
```

- [ ] **Step 6: Reinstall the package so the new module is importable**

Run: `pip install -e ".[dev]" -q`
Expected: completes with no error (registers `citation_workflow` under
the editable-install path hook, per `pyproject.toml`'s updated include
list).

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/citation_workflow/test_add_citation.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (190 tests: 186 from Task 2, plus 4 new)

- [ ] **Step 9: Commit**

```bash
git add citation_workflow tests/citation_workflow pyproject.toml
git commit -m "Add citation_workflow.add_citation orchestrating discovery + catalog"
```

---

## Task 4: `webapp/app.py` (extend with candidates + citation endpoints)

**Files:**
- Modify: `webapp/app.py`
- Modify: `tests/webapp/test_app.py` (add new tests; existing tests are
  unaffected and stay as-is)

**Interfaces:**
- Consumes: `list_corpus_candidates` (`discovery.corpus_candidates`, Task
  2); `add_citation`, `FamilyNotFoundError` (`citation_workflow.add_citation`,
  Task 3); `CitationError` (`reference_model.cite`, already merged).
- Produces: `GET /api/candidates`, `POST /api/citations` on
  `webapp.app.app`. `GET /api/pages`, `GET /api/pages/{fact_key}` are
  unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/webapp/test_app.py` (keep all existing content and
imports above; add these new imports and tests at the end of the file):

```python
import json
from pathlib import Path

REAL_XSD_FAMILIES = {
    "MiKaDiv_FM",
    "MiKaDiv_FM_Fachtypen",
    "MiKaDiv_FM_Meldeart11",
    "MiKaDiv_FM_Meldeart13",
    "MiKaDiv_FM_Meldeart21",
    "MiKaDiv_FM_Meldeart22",
    "MiKaDiv_FM_Meldeart23",
    "MiKaDiv_FM_MeldeartErg",
    "MiKaDiv_FM_MeldeartenBasis",
    "MiKaDiv_FM_MeldeartenSonder",
    "MiKaDiv_FM_Personentypen",
    "MiKaDiv_FM_Standardtypen",
    "din-norm-91379-datatypes",
}


def _synthetic_corpus(tmp_path, xsd_content: str) -> str:
    module_root = tmp_path / "corpus"
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "test.xsd").write_text(xsd_content, encoding="utf-8")
    (snapshot_dir / "_manifest.json").write_text(
        json.dumps({"TestFamily": "test.xsd"}), encoding="utf-8"
    )
    (module_root / "_current").write_text("1.0", encoding="utf-8")
    return str(module_root)


_VALID_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Foo" type="xs:string"/>
</xs:schema>
"""

_XSD_WITHOUT_FOO = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
</xs:schema>
"""


def test_list_candidates_endpoint_returns_the_real_13_xsd_families():
    client = TestClient(app)
    response = client.get("/api/candidates")

    assert response.status_code == 200
    assert set(response.json().keys()) == REAL_XSD_FAMILIES


def test_add_citation_endpoint_creates_a_page_retrievable_via_get_pages(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-1",
        "author": "julian",
        "comment": "initial",
        "is_correction": False,
    })

    assert response.status_code == 200
    assert response.json()["fact_key"] == "fact-1"

    page_response = client.get("/api/pages/fact-1")
    assert page_response.status_code == 200
    assert page_response.json()["current"]["author"] == "julian"


def test_add_citation_endpoint_returns_400_for_unknown_family(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)

    client = TestClient(app)
    response = client.post("/api/citations", json={
        "family": "NoSuchFamily",
        "xpath": "/x",
        "fact_key": "fact-2",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 400
    assert client.get("/api/pages/fact-2").status_code == 404


def test_add_citation_endpoint_returns_400_for_a_candidate_that_went_stale(tmp_path, monkeypatch):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    module_root = _synthetic_corpus(tmp_path, _VALID_XSD)
    monkeypatch.setenv("REFERENCES_CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("MIKADIV_MODULE_ROOT", module_root)
    client = TestClient(app)

    # The xpath is valid right now -- confirm the candidate genuinely
    # exists before making it stale underneath the same family.
    candidates = client.get("/api/candidates").json()
    assert any(c["xpath"] == "/xs:schema/xs:element[@name='Foo']" for c in candidates["TestFamily"])

    # Mutate the real underlying file so the same xpath no longer resolves
    # -- simulates a candidate going stale between listing and submission.
    (Path(module_root) / "1.0" / "test.xsd").write_text(_XSD_WITHOUT_FOO, encoding="utf-8")

    response = client.post("/api/citations", json={
        "family": "TestFamily",
        "xpath": "/xs:schema/xs:element[@name='Foo']",
        "fact_key": "fact-3",
        "author": "julian",
        "comment": "x",
        "is_correction": False,
    })

    assert response.status_code == 400
    assert client.get("/api/pages/fact-3").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/webapp/test_app.py -v`
Expected: FAIL — the four new tests fail with 404s (`/api/candidates`
and `/api/citations` don't exist yet in the current `webapp/app.py`);
existing tests still pass.

- [ ] **Step 3: Replace the full contents of `webapp/app.py`**

```python
"""Serves the references catalog as browsable pages with revision
history, plus a candidate-browsing + citation-submission interaction
layer. See docs/specs/2026-09-25-catalog-revision-history-design.md and
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from citation_workflow.add_citation import FamilyNotFoundError, add_citation
from discovery.corpus_candidates import list_corpus_candidates
from reference_model.cite import CitationError
from references_catalog.catalog import get_history, list_pages

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"
DEFAULT_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


def _module_root() -> str:
    # Same call-time-read pattern as _catalog_path(), for the same reason.
    return os.environ.get("MIKADIV_MODULE_ROOT", DEFAULT_MODULE_ROOT)


class AddCitationRequest(BaseModel):
    family: str
    xpath: str
    fact_key: str
    author: str
    comment: str
    is_correction: bool


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


@app.get("/api/candidates")
def list_candidates_endpoint() -> dict:
    candidates = list_corpus_candidates(_module_root())
    return {
        family: [dataclasses.asdict(c) for c in family_candidates]
        for family, family_candidates in candidates.items()
    }


@app.post("/api/citations")
def add_citation_endpoint(request: AddCitationRequest) -> dict:
    try:
        revision = add_citation(
            _module_root(),
            _catalog_path(),
            request.family,
            request.xpath,
            request.fact_key,
            request.author,
            request.comment,
            request.is_correction,
        )
    except (FamilyNotFoundError, CitationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"fact_key": request.fact_key, "revision": dataclasses.asdict(revision)}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/webapp/test_app.py -v`
Expected: PASS (11 tests: 7 existing + 4 new)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (194 tests: 190 from Task 3, plus 4 new)

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py tests/webapp/test_app.py
git commit -m "Add GET /api/candidates and POST /api/citations to webapp"
```

---

## Task 5: `webapp/static/index.html` (add the `?add=1` view) + manual verification

**Files:**
- Modify: `webapp/static/index.html`

**Interfaces:**
- Consumes: `GET /api/candidates`, `POST /api/citations` (Task 4), via
  the browser's own `fetch()`.
- Produces: nothing new for other code — this is the leaf of the stack.

No automated test for this file, per this project's own established
convention (no frontend test runner). The completion gate is the manual
verification in Steps 3-5 below, which is required, not optional.

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
    nav { margin-bottom: 1rem; }
    nav a { margin-right: 1rem; }
    .cite-form { border: 1px solid #ccc; padding: 1rem; margin-top: 1rem; max-width: 30rem; }
    .cite-form label { display: block; margin-top: 0.5rem; }
    .cite-form input[type="text"] { width: 100%; box-sizing: border-box; }
    button { cursor: pointer; }
  </style>
</head>
<body>
  <h1><a href="/">MiKaDiv-FM References</a></h1>
  <nav>
    <a href="/">Index</a>
    <a href="?add=1">Add citation</a>
  </nav>
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
      table.innerHTML = "<thead><tr><th>Page</th><th>Family</th><th>Selector type</th><th>Current reference ID</th><th>Revisions</th></tr></thead>";
      const tbody = document.createElement("tbody");
      factKeys.forEach((factKey) => {
        const page = pages[factKey];
        const reference = page.current.reference;
        const family = reference.subject_document ? reference.subject_document.family : "";
        const selectorType = reference.selector ? reference.selector.type : "";
        const referenceId = reference.reference_id || "";
        const row = document.createElement("tr");
        const linkCell = document.createElement("td");
        const link = document.createElement("a");
        link.href = `?page=${encodeURIComponent(factKey)}`;
        link.textContent = factKey;
        linkCell.appendChild(link);
        row.appendChild(linkCell);
        const referenceIdCell = cell(referenceId);
        if (page.current.is_correction) {
          referenceIdCell.classList.add("correction");
        }
        [family, selectorType].forEach((value) => row.appendChild(cell(value)));
        row.appendChild(referenceIdCell);
        row.appendChild(cell(String(page.revision_count)));
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

    function renderCiteForm(container, family, candidate) {
      const existingForm = container.querySelector(".cite-form");
      if (existingForm) {
        existingForm.remove();
      }

      const form = document.createElement("form");
      form.className = "cite-form";

      const summary = document.createElement("p");
      summary.textContent = `${family}: ${candidate.tag} ${candidate.name} (${candidate.xpath})`;
      form.appendChild(summary);

      function makeField(labelText, inputType) {
        const label = document.createElement("label");
        label.textContent = labelText;
        const input = document.createElement("input");
        input.type = inputType;
        label.appendChild(input);
        form.appendChild(label);
        return input;
      }

      const factKeyInput = makeField("Fact key", "text");
      const authorInput = makeField("Author", "text");
      const commentInput = makeField("Comment", "text");
      const isCorrectionInput = makeField("Is correction", "checkbox");

      const submitButton = document.createElement("button");
      submitButton.type = "submit";
      submitButton.textContent = "Submit citation";
      form.appendChild(submitButton);

      const formError = document.createElement("p");
      formError.id = "error";
      form.appendChild(formError);

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        formError.textContent = "";
        const factKey = factKeyInput.value;
        fetch("/api/citations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            family: family,
            xpath: candidate.xpath,
            fact_key: factKey,
            author: authorInput.value,
            comment: commentInput.value,
            is_correction: isCorrectionInput.checked,
          }),
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((body) => {
                throw new Error(body.detail || `Server returned ${response.status}`);
              });
            }
            window.location.href = `?page=${encodeURIComponent(factKey)}`;
          })
          .catch((error) => {
            formError.textContent = `Failed to submit citation: ${error.message}`;
          });
      });

      container.appendChild(form);
    }

    function renderCandidateTable(container, family, candidates) {
      const existingTable = container.querySelector(".candidate-table");
      if (existingTable) {
        existingTable.remove();
      }
      const existingForm = container.querySelector(".cite-form");
      if (existingForm) {
        existingForm.remove();
      }

      const table = document.createElement("table");
      table.className = "candidate-table";
      table.innerHTML = "<thead><tr><th>Tag</th><th>Name</th><th>XPath</th><th></th></tr></thead>";
      const tbody = document.createElement("tbody");
      candidates.forEach((candidate) => {
        const row = document.createElement("tr");
        row.appendChild(cell(candidate.tag));
        row.appendChild(cell(candidate.name));
        row.appendChild(cell(candidate.xpath));
        const actionCell = document.createElement("td");
        const citeButton = document.createElement("button");
        citeButton.type = "button";
        citeButton.textContent = "Cite this";
        citeButton.addEventListener("click", () => renderCiteForm(container, family, candidate));
        actionCell.appendChild(citeButton);
        row.appendChild(actionCell);
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      container.appendChild(table);
    }

    function renderAdd(candidatesByFamily) {
      const content = document.getElementById("content");
      content.innerHTML = "";

      const heading = document.createElement("h2");
      heading.textContent = "Add citation";
      content.appendChild(heading);

      const familyList = document.createElement("ul");
      const detail = document.createElement("div");
      detail.id = "add-detail";

      Object.keys(candidatesByFamily).sort().forEach((family) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = "#";
        link.textContent = `${family} (${candidatesByFamily[family].length} candidates)`;
        link.addEventListener("click", (event) => {
          event.preventDefault();
          renderCandidateTable(detail, family, candidatesByFamily[family]);
        });
        item.appendChild(link);
        familyList.appendChild(item);
      });

      content.appendChild(familyList);
      content.appendChild(detail);
    }

    const params = new URLSearchParams(window.location.search);
    const factKey = params.get("page");
    const isAdd = params.get("add");

    if (isAdd) {
      fetch("/api/candidates")
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
          }
          return response.json();
        })
        .then(renderAdd)
        .catch((error) => renderError(`Failed to load candidates: ${error.message}`));
    } else if (factKey) {
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
Expected: PASS (194 tests — unchanged from Task 4; this task adds no
automated tests)

- [ ] **Step 3: Commit**

```bash
git add webapp/static/index.html
git commit -m "Add ?add=1 view: browse real candidates and submit a citation"
```

- [ ] **Step 4: Manual verification — full browse-and-cite flow**

```bash
cd /work/generator
fuser -k 8012/tcp 2>/dev/null; sleep 1
nohup env REFERENCES_CATALOG_PATH=/work/ontologies/mikadiv-fm/references.json \
  MIKADIV_MODULE_ROOT=/work/ontologies/mikadiv-fm/sources \
  uvicorn webapp.app:app --host 0.0.0.0 --port 8012 > /tmp/webapp-citation.log 2>&1 &
disown
sleep 2
curl -s http://localhost:8012/api/pages
```

Expected: `{}` (the real committed catalog, untouched so far). Then via
Playwright (`node` + the `playwright` package, already baked into the
image — see this repo's own established pattern from prior plans, not a
new MCP server):

1. Navigate to `http://localhost:8012/?add=1`. Confirm the page shows a
   heading "Add citation" and a list of exactly 13 family links (never a
   PDF family), each showing its real candidate count (e.g.
   `MiKaDiv_FM_Meldeart23 (5 candidates)`).
2. Click a family link. Confirm a candidate table appears client-side
   with no page reload, showing that family's real tag/name/xpath rows.
3. Click "Cite this" on one row. Confirm a form appears showing that
   exact family/tag/name/xpath, with Fact key / Author / Comment /
   Is correction fields.
4. Fill in a fresh, clearly-marked fact key (e.g.
   `playwright-verify-fact`), an author, and a comment; submit.
5. Confirm the browser navigates to
   `http://localhost:8012/?page=playwright-verify-fact` and that page
   shows exactly one History row with the author/comment just entered.
6. Confirm `curl -s http://localhost:8012/api/pages` now shows the one
   new page.

- [ ] **Step 5: Revert the real catalog and stop the server**

```bash
echo "{}" > /work/ontologies/mikadiv-fm/references.json
cd /work/ontologies && git status
cd /work/generator
fuser -k 8012/tcp 2>/dev/null
```

Expected: `git status` in `/work/ontologies` shows a clean working tree —
the demo citation is fully reverted, matching the committed `{}` exactly.
Confirm the `uvicorn` process is stopped (`curl` to port 8012 fails to
connect).

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `staleness_sweep/resolve.py` provides `FamilyLocation` and
  `list_current_locations()`, with `resolve_current_location()`'s own
  behavior fully unchanged (its existing 14-test file untouched and
  green).
- [ ] `discovery/corpus_candidates.py` provides `CorpusCandidate` and
  `list_corpus_candidates()`, returning exactly the 13 real XSD families
  (never any PDF family) with the real, live-verified per-family counts
  totaling 422.
- [ ] `citation_workflow/add_citation.py` provides `FamilyNotFoundError`
  and `add_citation()`, re-resolving `family` server-side and unifying
  create/edit via `add_revision()`.
- [ ] `webapp/app.py` serves `GET /api/candidates` and
  `POST /api/citations`, mapping `FamilyNotFoundError`/`CitationError` to
  HTTP 400.
- [ ] `webapp/static/index.html` provides a working `?add=1` view,
  manually verified in a real browser via Playwright: browse real
  candidates, submit a real citation, land on the resulting page.
- [ ] All automated tests pass: `pytest tests/ -v` → 194 passed.
- [ ] The real committed `ontologies/mikadiv-fm/references.json` remains
  exactly `{}`.
