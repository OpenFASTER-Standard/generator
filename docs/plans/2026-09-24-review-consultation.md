# Review Consultation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `review_consultation` (from
`docs/specs/2026-09-24-review-consultation-design.md`) so a previously
`APPROVED` review of a specific drifted state suppresses that exact state
from resurfacing on future sweeps — while further drift past that point,
or a `REJECTED` review, still shows up.

**Architecture:** Extend two already-merged modules with the minimum
needed to identify "the exact state a human reviewed" (`reference_model.cite.LeafCheckResult`
gains `new_content_hash`; `review_surfacing.summarize.FlaggedLeaf` gains
`fingerprint`), simplify `review_recording.record.record_review()` to
capture that fingerprint automatically, then add one new small module
(`review_consultation/consult.py`) that loads review records and filters
a `ReviewSummary` against them. No new third-party dependencies.

**Tech Stack:** Python 3.11, stdlib only, plus `reference_model`,
`staleness_sweep`, `review_surfacing`, `review_recording` (all already
merged to `main`).

**Spec:** `docs/specs/2026-09-24-review-consultation-design.md`

## Global Constraints

- `LeafCheckResult` gains `new_content_hash: str | None` (`None` unless
  `outcome.status` is `RESOLVED`); `check_leaf()` populates it from the
  same `canonicalize_and_hash()` call it already makes to compute
  `hash_changed`, not a second, duplicate one.
- `FlaggedLeaf` gains `fingerprint: str`: for `DriftKind.CONTENT` it's
  `new_content_hash`; for `DriftKind.STRUCTURAL` it's `outcome.status.name`
  (e.g. `"NOT_FOUND"`).
- `record_review()`'s signature becomes `record_review(reviews_dir,
  fact_key, flagged: FlaggedLeaf, reviewer, verdict, reasoning) -> Leaf` —
  `family` and `drift_kind` are derived from `flagged.leaf.subject_document.family`
  and `flagged.drift_kind`, never passed separately. The written document
  gains one field, `reviewed_fingerprint`, copied from `flagged.fingerprint`.
- Suppression rule (`apply_reviews()`): a `FlaggedLeaf` is dropped iff its
  `(fact_key, drift_kind, fingerprint)` matches an `APPROVED` review's
  `(fact_key, drift_kind, reviewed_fingerprint)` **and** does not also
  match a `REJECTED` review for that same triple — a contradictory
  history keeps the entry visible.
- A `fact_key` with zero remaining flagged leaves after filtering is
  omitted from the output `flagged` dict entirely, not left present with
  an empty tuple — mirrors `summarize_for_review()`'s own convention.
  `unresolved_families`/`excluded_keys` pass through unchanged.
- `load_reviews()` on a `reviews_dir` that doesn't exist yet returns `[]`
  (`Path.glob()` on a missing directory is empty, not an error).
- `load_reviews()` raises `ReviewLoadError` — never silently skips — on:
  invalid JSON, a JSON value that isn't an object, a missing required
  field, or an invalid `drift_kind`/`verdict` string.

## Review Focus

- **A fact whose content drifts again, to a genuinely different value,
  after already being approved.** The entire point of scoping suppression
  to a fingerprint rather than fact identity — a reasonable person would
  expect this fresh, unreviewed drift to resurface, not stay hidden
  forever because the `fact_key` was approved once before. Tested
  directly in Task 4 (`test_content_drift_resurfaces_after_further_drift`).
- **Contradictory review history**: an `APPROVED` and a `REJECTED` record
  both exist for the exact same fingerprint. A reasonable person would
  expect the confirmed real problem to stay visible, not be silently
  hidden by an earlier or conflicting approval. Tested directly in Task 4
  (`test_both_approved_and_rejected_for_same_fingerprint_stays_visible`).
- **A `Union` fact where only some of its problematic leaves have been
  reviewed.** A reasonable person would expect the fact to remain visible
  showing only the still-unreviewed leaf, not disappear entirely or keep
  showing the already-approved one. Tested directly in Task 4
  (`test_union_with_one_leaf_approved_key_remains_with_only_unreviewed_leaf`).
- **A hand-edited or corrupted review file** sitting in `reviews_dir`
  (invalid JSON, a JSON array instead of an object, a missing field, an
  invalid `drift_kind`/`verdict` string). A reasonable person would expect
  a loud, specific error naming the bad file, not a silent skip that could
  hide a real reviewed decision, and not an opaque `KeyError`/`ValueError`
  surfacing from deep inside `load_reviews()`. Tested directly in Task 4,
  for each malformed variant.
- **`load_reviews()` called against a `reviews_dir` that has never had
  anything written to it.** A reasonable person consulting reviews before
  any review has ever been recorded would expect a normal empty list, not
  an exception demanding the directory be pre-created. Tested directly in
  Task 4 (`test_load_reviews_on_nonexistent_directory_returns_empty_list`).

---

## Task 1: `LeafCheckResult.new_content_hash`

**Files:**
- Modify: `reference_model/cite.py`
- Modify: `tests/review_surfacing/test_summarize.py` (one hand-constructed `LeafCheckResult` needs the new field)
- Test: `tests/reference_model/test_cite.py`

**Interfaces:**
- Consumes: nothing new — `get_resolver`, `Status`, `ResolutionOutcome` already imported in `reference_model/cite.py`.
- Produces: `LeafCheckResult.new_content_hash: str | None`, populated by `check_leaf()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/reference_model/test_cite.py` (after `test_check_leaf_detects_a_changed_hash_without_a_status_change`):

```python
def test_check_leaf_populates_new_content_hash_when_resolved(tmp_path: Path):
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))

    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = check_leaf(leaf, retrieval_uri=str(mutated_path))
    assert result.outcome.status == Status.RESOLVED
    assert result.new_content_hash is not None
    assert len(result.new_content_hash) == 64
    assert result.new_content_hash != leaf.content_hash.digest


def test_check_leaf_new_content_hash_is_none_when_not_resolved(tmp_path: Path):
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))

    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = check_leaf(leaf, retrieval_uri=str(mutated_path))
    assert result.outcome.status == Status.NOT_FOUND
    assert result.new_content_hash is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_cite.py -v -k new_content_hash`
Expected: FAIL with `AttributeError: 'LeafCheckResult' object has no attribute 'new_content_hash'`

- [ ] **Step 3: Implement**

Modify `reference_model/cite.py`'s `LeafCheckResult`/`check_leaf()`:

```python
@dataclass(frozen=True)
class LeafCheckResult:
    leaf: Leaf
    outcome: ResolutionOutcome
    hash_changed: bool | None  # None unless outcome.status is RESOLVED
    new_content_hash: str | None  # None unless outcome.status is RESOLVED


def check_leaf(leaf: Leaf, retrieval_uri: str | None = None) -> LeafCheckResult:
    resolver = get_resolver(leaf.selector.type)
    uri = retrieval_uri if retrieval_uri is not None else leaf.subject_document.retrieval_uri
    outcome = resolver.resolve(leaf.selector, uri)
    if outcome.status != Status.RESOLVED:
        return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=None, new_content_hash=None)
    new_digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return LeafCheckResult(
        leaf=leaf,
        outcome=outcome,
        hash_changed=new_digest != leaf.content_hash.digest,
        new_content_hash=new_digest,
    )
```

- [ ] **Step 4: Fix the one existing hand-constructed `LeafCheckResult`**

`tests/review_surfacing/test_summarize.py`'s `test_uncitable_drift_is_also_classified_as_structural`
builds a `LeafCheckResult` directly, which now needs the new required
field. Modify that call:

```python
    fake_result = LeafCheckResult(
        leaf=leaf,
        outcome=ResolutionOutcome(status=Status.UNCITABLE),
        hash_changed=None,
        new_content_hash=None,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_cite.py tests/review_surfacing/test_summarize.py -v`
Expected: PASS, no failures

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (109 tests: 107 previously passing, plus 2 new)

- [ ] **Step 7: Commit**

```bash
git add reference_model/cite.py tests/reference_model/test_cite.py tests/review_surfacing/test_summarize.py
git commit -m "Add LeafCheckResult.new_content_hash: expose the digest check_leaf() already computes"
```

---

## Task 2: `FlaggedLeaf.fingerprint`

**Files:**
- Modify: `review_surfacing/summarize.py`
- Test: `tests/review_surfacing/test_summarize.py`

**Interfaces:**
- Consumes: `LeafCheckResult.new_content_hash` (Task 1).
- Produces: `FlaggedLeaf.fingerprint: str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/review_surfacing/test_summarize.py` (after
`test_structural_drift_is_classified_as_structural`):

```python
def test_content_drift_fingerprint_is_the_new_content_hash(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)

    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.fingerprint == report.results_by_key["fact-1"][0].new_content_hash
    assert flagged_leaf.fingerprint != leaf.content_hash.digest
    assert len(flagged_leaf.fingerprint) == 64


def test_structural_drift_fingerprint_is_the_status_name(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)

    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.fingerprint == "NOT_FOUND"
```

Also add one assertion each to two existing tests in the same file.

In `test_ambiguous_drift_is_also_classified_as_structural`, after the
existing `assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL` line,
add:

```python
    assert flagged_leaf.fingerprint == "AMBIGUOUS"
```

In `test_uncitable_drift_is_also_classified_as_structural`, after the
existing `assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL` line,
add:

```python
    assert flagged_leaf.fingerprint == "UNCITABLE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/review_surfacing/test_summarize.py -v`
Expected: FAIL — the two new tests and the two modified tests all fail
with `AttributeError: 'FlaggedLeaf' object has no attribute 'fingerprint'`

- [ ] **Step 3: Implement**

Modify `review_surfacing/summarize.py`:

```python
@dataclass(frozen=True)
class FlaggedLeaf:
    leaf: Leaf
    outcome: ResolutionOutcome
    drift_kind: DriftKind
    fingerprint: str


def _classify(result: LeafCheckResult) -> FlaggedLeaf | None:
    if result.outcome.status == Status.RESOLVED:
        if result.hash_changed:
            return FlaggedLeaf(result.leaf, result.outcome, DriftKind.CONTENT, result.new_content_hash)
        return None
    return FlaggedLeaf(result.leaf, result.outcome, DriftKind.STRUCTURAL, result.outcome.status.name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/review_surfacing/test_summarize.py -v`
Expected: PASS (10 tests: 8 previously passing, plus 2 new)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (111 tests: 109 from Task 1, plus 2 new)

- [ ] **Step 6: Commit**

```bash
git add review_surfacing/summarize.py tests/review_surfacing/test_summarize.py
git commit -m "Add FlaggedLeaf.fingerprint: the exact state a review must match to suppress it"
```

---

## Task 3: `record_review()` takes a `FlaggedLeaf`

**Files:**
- Modify: `review_recording/record.py`
- Test: `tests/review_recording/test_record.py` (full rewrite — every existing test constructs a real `FlaggedLeaf` now instead of passing `family`/`drift_kind` directly)

**Interfaces:**
- Consumes: `FlaggedLeaf` (`review_surfacing.summarize`, Task 2).
- Produces: `record_review(reviews_dir, fact_key, flagged: FlaggedLeaf, reviewer, verdict, reasoning) -> Leaf` (signature change — `family`/`drift_kind` parameters removed). Written document gains `reviewed_fingerprint`.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `tests/review_recording/test_record.py`:

```python
import json
import shutil

from reference_model.cite import check_leaf, cite
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import summarize_for_review
from staleness_sweep.sweep import sweep

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
REAL_MELDEART23_XSD = f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _real_meldeart23_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_MELDEART23_XSD)


def _make_content_and_structural_snapshot(module_root):
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    assert mutated != original

    new_snapshot = module_root / "1.03"
    shutil.copytree(module_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (module_root / "_current").write_text("1.03")


def _content_flagged_leaf(module_root):
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)
    (flagged_leaf,) = summary.flagged["fact-1"]
    return flagged_leaf


def _structural_flagged_leaf(module_root):
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)
    (flagged_leaf,) = summary.flagged["fact-1"]
    return flagged_leaf


def test_record_review_returns_a_resolvable_leaf(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    assert leaf.content_hash.algorithm == "sha256"
    assert len(leaf.content_hash.digest) == 64
    assert leaf.subject_document.family.startswith("review-")
    assert leaf.subject_document.version == "1"

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["verdict"] == "approved"


def test_record_review_writes_the_full_document_shape(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _structural_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="The renamed element needs a real extraction fix.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["fact_key"] == "fact-1"
    assert written["family"] == "MiKaDiv_FM_Meldeart23"
    assert written["drift_kind"] == "STRUCTURAL"
    assert written["reviewed_fingerprint"] == "NOT_FOUND"
    assert written["reviewer"] == "julian.nalenz@divizend.com"
    assert written["verdict"] == "rejected"
    assert written["reasoning"] == "The renamed element needs a real extraction fix."
    assert "reviewed_at" in written and "T" in written["reviewed_at"]  # a real ISO timestamp


def test_record_review_writes_the_content_fingerprint(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed benign.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["reviewed_fingerprint"] == flagged_leaf.fingerprint
    assert len(written["reviewed_fingerprint"]) == 64


def test_record_review_creates_reviews_dir_if_missing(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    reviews_dir = tmp_path / "does-not-exist-yet"
    assert not reviews_dir.exists()

    leaf = record_review(
        reviews_dir=str(reviews_dir),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First review ever written to this directory.",
    )

    assert reviews_dir.exists()
    written_files = list(reviews_dir.iterdir())
    assert len(written_files) == 1
    assert leaf.subject_document.retrieval_uri == str(written_files[0])


def test_unmodified_review_record_is_unchanged_on_recheck(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )

    result = check_leaf(leaf)
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is False


def test_two_calls_with_identical_arguments_produce_independent_records(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    kwargs = dict(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    leaf_1 = record_review(**kwargs)
    leaf_2 = record_review(**kwargs)

    assert leaf_1.subject_document.family != leaf_2.subject_document.family
    assert leaf_1.subject_document.retrieval_uri != leaf_2.subject_document.retrieval_uri
    assert leaf_1.reference_id != leaf_2.reference_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/review_recording/test_record.py -v`
Expected: FAIL with `TypeError: record_review() got an unexpected keyword argument 'flagged'`

- [ ] **Step 3: Implement**

Replace the full contents of `review_recording/record.py`:

```python
"""Turns a reviewer's decision into a plain, real JSON document, cited
through the same Reference/cite() machinery already built for XSDs and
PDFs. See docs/specs/2026-09-23-review-recording-design.md and
docs/specs/2026-09-24-review-consultation-design.md.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from reference_model.cite import cite
from reference_model.model import Leaf, SubjectDocument
from reference_model.selectors.json_selector import JsonSelector
from review_surfacing.summarize import FlaggedLeaf


class Verdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


def record_review(
    reviews_dir: str,
    fact_key: str,
    flagged: FlaggedLeaf,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Leaf:
    Path(reviews_dir).mkdir(parents=True, exist_ok=True)
    review_id = str(uuid.uuid4())
    document = {
        "fact_key": fact_key,
        "family": flagged.leaf.subject_document.family,
        "drift_kind": flagged.drift_kind.value,
        "reviewed_fingerprint": flagged.fingerprint,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict.value,
        "reasoning": reasoning,
    }
    file_path = Path(reviews_dir) / f"{review_id}.json"
    file_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    subject_document = SubjectDocument(
        family=f"review-{review_id}", version="1", retrieval_uri=str(file_path)
    )
    return cite(subject_document, JsonSelector.create(""))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/review_recording/test_record.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (112 tests: 111 from Task 2, plus 1 new)

- [ ] **Step 6: Commit**

```bash
git add review_recording/record.py tests/review_recording/test_record.py
git commit -m "record_review() takes a FlaggedLeaf: family/drift_kind derived, fingerprint captured"
```

---

## Task 4: `review_consultation`

**Files:**
- Create: `review_consultation/__init__.py`
- Create: `review_consultation/consult.py`
- Create: `tests/review_consultation/__init__.py`
- Test: `tests/review_consultation/test_consult.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `DriftKind`, `FlaggedLeaf`, `ReviewSummary` (`review_surfacing.summarize`, Task 2); `Verdict`, `record_review` (`review_recording.record`, Task 3).
- Produces: `ReviewRecord`, `ReviewLoadError`, `load_reviews(reviews_dir: str) -> list[ReviewRecord]`, `apply_reviews(summary: ReviewSummary, reviews: list[ReviewRecord]) -> ReviewSummary`.

- [ ] **Step 1: Create the package skeleton**

`review_consultation/__init__.py`:

```python
"""Consults previously-recorded review decisions to suppress drift a human
has already approved, scoped to the exact fingerprint they reviewed -- so
further drift past that point still resurfaces. See
docs/specs/2026-09-24-review-consultation-design.md.
"""
```

`tests/review_consultation/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/review_consultation/test_consult.py`:

```python
import json
import shutil

import pytest

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from review_consultation.consult import ReviewLoadError, apply_reviews, load_reviews
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import summarize_for_review
from staleness_sweep.sweep import sweep

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _real_meldeart23_subject_document():
    return SubjectDocument(
        family="MiKaDiv_FM_Meldeart23",
        version="1.02",
        retrieval_uri=f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
    )


def _write_snapshot(module_root, version, xsd_text):
    snapshot = module_root / version
    shutil.copytree(module_root / "1.02", snapshot)
    (snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(xsd_text, encoding="utf-8")
    (module_root / "_current").write_text(version)


def test_approved_review_suppresses_matching_content_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed benign.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_content_drift_resurfaces_after_further_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    first_mutation = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", first_mutation)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary_v1 = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf_v1,) = summary_v1.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf_v1,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First change confirmed benign.",
    )

    second_mutation = first_mutation.replace('minOccurs="0"', 'minOccurs="0" maxOccurs="2"')
    assert second_mutation != first_mutation
    (module_root / "1.03" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(
        second_mutation, encoding="utf-8"
    )

    summary_v2 = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary_v2, reviews)

    assert "fact-1" in filtered.flagged
    (still_flagged,) = filtered.flagged["fact-1"]
    assert still_flagged.fingerprint != flagged_leaf_v1.fingerprint


def test_approved_review_suppresses_matching_structural_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.fingerprint == "NOT_FOUND"

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Renamed intentionally, extraction updated separately.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_rejected_review_does_not_suppress(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="This needs a real extraction fix.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged
    assert filtered.flagged["fact-1"] == summary.flagged["fact-1"]


def test_both_approved_and_rejected_for_same_fingerprint_stays_visible(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Initially approved.",
    )
    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="On further thought, this needs a real fix.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged


def test_union_with_one_leaf_approved_key_remains_with_only_unreviewed_leaf(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    content_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    structural_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([content_leaf, structural_leaf])

    summary = summarize_for_review(sweep({"fact-1": union}, str(module_root)))
    assert len(summary.flagged["fact-1"]) == 2
    content_flagged = next(fl for fl in summary.flagged["fact-1"] if fl.leaf == content_leaf)

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=content_flagged,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Content change confirmed benign.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged
    (remaining,) = filtered.flagged["fact-1"]
    assert remaining.leaf == structural_leaf


def test_union_with_all_leaves_approved_key_is_dropped(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    content_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    structural_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([content_leaf, structural_leaf])

    summary = summarize_for_review(sweep({"fact-1": union}, str(module_root)))
    for flagged_leaf in summary.flagged["fact-1"]:
        record_review(
            reviews_dir=str(tmp_path / "reviews"),
            fact_key="fact-1",
            flagged=flagged_leaf,
            reviewer="julian.nalenz@divizend.com",
            verdict=Verdict.APPROVED,
            reasoning="Both changes confirmed benign.",
        )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_unresolved_families_and_excluded_keys_pass_through_unchanged():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver",
        version="1.02",
        retrieval_uri=f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, REAL_MODULE_ROOT))

    filtered = apply_reviews(summary, [])

    assert filtered.unresolved_families == summary.unresolved_families
    assert filtered.excluded_keys == summary.excluded_keys
    assert filtered.excluded_keys == ("fact-1",)


def test_load_reviews_on_nonexistent_directory_returns_empty_list(tmp_path):
    reviews = load_reviews(str(tmp_path / "does-not-exist"))
    assert reviews == []


def test_load_reviews_raises_on_malformed_json(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ReviewLoadError):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_non_object_json(tmp_path):
    (tmp_path / "array.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ReviewLoadError):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_missing_required_field(tmp_path):
    incomplete = {
        "fact_key": "fact-1",
        "family": "MiKaDiv_FM_Meldeart23",
        "drift_kind": "CONTENT",
        "reviewed_fingerprint": "abc123",
        "reviewer": "julian.nalenz@divizend.com",
        "reviewed_at": "2026-09-24T00:00:00+00:00",
        "verdict": "approved",
        # "reasoning" deliberately omitted
    }
    (tmp_path / "incomplete.json").write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(ReviewLoadError):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_invalid_drift_kind_value(tmp_path):
    invalid = {
        "fact_key": "fact-1",
        "family": "MiKaDiv_FM_Meldeart23",
        "drift_kind": "NOT_A_REAL_DRIFT_KIND",
        "reviewed_fingerprint": "abc123",
        "reviewer": "julian.nalenz@divizend.com",
        "reviewed_at": "2026-09-24T00:00:00+00:00",
        "verdict": "approved",
        "reasoning": "n/a",
    }
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_invalid_verdict_value(tmp_path):
    invalid = {
        "fact_key": "fact-1",
        "family": "MiKaDiv_FM_Meldeart23",
        "drift_kind": "CONTENT",
        "reviewed_fingerprint": "abc123",
        "reviewer": "julian.nalenz@divizend.com",
        "reviewed_at": "2026-09-24T00:00:00+00:00",
        "verdict": "maybe",
        "reasoning": "n/a",
    }
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError):
        load_reviews(str(tmp_path))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/review_consultation/test_consult.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'review_consultation.consult'`

- [ ] **Step 4: Implement `review_consultation/consult.py`**

```python
"""Loads previously-recorded review decisions and filters a ReviewSummary
against them, scoped to the exact fingerprint each review was recorded
against. See docs/specs/2026-09-24-review-consultation-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from review_recording.record import Verdict
from review_surfacing.summarize import DriftKind, FlaggedLeaf, ReviewSummary


@dataclass(frozen=True)
class ReviewRecord:
    fact_key: str
    family: str
    drift_kind: DriftKind
    reviewed_fingerprint: str
    reviewer: str
    reviewed_at: str
    verdict: Verdict
    reasoning: str


class ReviewLoadError(Exception):
    pass


_REQUIRED_FIELDS = (
    "fact_key", "family", "drift_kind", "reviewed_fingerprint",
    "reviewer", "reviewed_at", "verdict", "reasoning",
)


def load_reviews(reviews_dir: str) -> list[ReviewRecord]:
    records = []
    for path in sorted(Path(reviews_dir).glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ReviewLoadError(f"{path}: not valid JSON") from e
        if not isinstance(raw, dict):
            raise ReviewLoadError(f"{path}: expected a JSON object")
        missing = [f for f in _REQUIRED_FIELDS if f not in raw]
        if missing:
            raise ReviewLoadError(f"{path}: missing field(s) {missing}")
        try:
            drift_kind = DriftKind(raw["drift_kind"])
            verdict = Verdict(raw["verdict"])
        except ValueError as e:
            raise ReviewLoadError(f"{path}: invalid drift_kind/verdict value") from e
        records.append(ReviewRecord(
            fact_key=raw["fact_key"],
            family=raw["family"],
            drift_kind=drift_kind,
            reviewed_fingerprint=raw["reviewed_fingerprint"],
            reviewer=raw["reviewer"],
            reviewed_at=raw["reviewed_at"],
            verdict=verdict,
            reasoning=raw["reasoning"],
        ))
    return records


def apply_reviews(summary: ReviewSummary, reviews: list[ReviewRecord]) -> ReviewSummary:
    approved = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.APPROVED
    }
    rejected = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.REJECTED
    }

    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for fact_key, entries in summary.flagged.items():
        kept = tuple(
            fl for fl in entries
            if (fact_key, fl.drift_kind, fl.fingerprint) not in approved
            or (fact_key, fl.drift_kind, fl.fingerprint) in rejected
        )
        if kept:
            flagged[fact_key] = kept

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=summary.unresolved_families,
        excluded_keys=summary.excluded_keys,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/review_consultation/test_consult.py -v`
Expected: PASS (14 tests)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (126 tests: 112 from Task 3, plus 14 new)

- [ ] **Step 7: Add `review_consultation*` to `pyproject.toml`'s packages list**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` section:

```toml
[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*", "review_consultation*"]
```

- [ ] **Step 8: Reinstall and verify the package is importable from outside the repo root**

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
cd /tmp && python3 -c "import review_consultation; print('importable')"
```

Expected: `importable`

- [ ] **Step 9: Commit**

```bash
cd /work/generator
git add review_consultation/__init__.py review_consultation/consult.py tests/review_consultation/__init__.py tests/review_consultation/test_consult.py pyproject.toml
git commit -m "Add review_consultation: suppress previously-approved drift by fingerprint"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `LeafCheckResult` gains `new_content_hash`; `FlaggedLeaf` gains
  `fingerprint`; `record_review()` takes a `FlaggedLeaf` instead of
  separate `family`/`drift_kind` arguments — all with the semantics in
  the spec.
- [ ] `ReviewRecord`, `ReviewLoadError`, `load_reviews()`, and
  `apply_reviews()` are implemented with the semantics in the spec in a
  new `review_consultation` package.
- [ ] All tests pass: `pytest tests/ -v` → 126 passed.
- [ ] A fact approved once, then drifted again to a different value,
  resurfaces (`test_content_drift_resurfaces_after_further_drift`); a
  `REJECTED` review never suppresses
  (`test_rejected_review_does_not_suppress`); a contradictory
  approve+reject pair for the same fingerprint stays visible
  (`test_both_approved_and_rejected_for_same_fingerprint_stays_visible`).
