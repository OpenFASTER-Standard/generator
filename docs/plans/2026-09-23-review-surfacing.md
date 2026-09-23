# Review Surfacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `DriftKind`, `FlaggedLeaf`, `ReviewSummary`, and
`summarize_for_review()` from `docs/specs/2026-09-23-review-surfacing-design.md`
— a pure, presentation-agnostic transformation from a `SweepReport` into
a shape organized around what a reviewer needs to know first: what's
flagged, and what kind of problem it is.

**Architecture:** One new, small, standalone module (`review_surfacing/`,
sibling to `reference_model/`/`staleness_sweep/`, depending only on the
latter) with a single pure function and three small dataclasses/enum. No
rendering, no I/O, no new dependencies.

**Tech Stack:** Python 3.11, stdlib only, plus `staleness_sweep` and
`reference_model` (both already merged to `main`).

**Spec:** `docs/specs/2026-09-23-review-surfacing-design.md`

## Global Constraints

- `DriftKind.STRUCTURAL` — the `LeafCheckResult.outcome.status` is
  `NOT_FOUND`, `AMBIGUOUS`, or `UNCITABLE`.
- `DriftKind.CONTENT` — `outcome.status` is `RESOLVED` and `hash_changed`
  is `True`.
- A `LeafCheckResult` with `RESOLVED` and `hash_changed` `False` is
  healthy and never appears in the output at all.
- `ReviewSummary.flagged` only ever contains keys with at least one
  problematic leaf — a key with every leaf healthy is **absent entirely**,
  never present with an empty tuple.
- `unresolved_families` and `excluded_keys` are verbatim pass-throughs
  from the input `SweepReport` — this transformation adds no new
  information about them.
- No per-key mapping from an excluded key to the family that excluded it
  — deliberately deferred, per the spec's own Non-Goals.
- No rendering, no CLI, no web UI, no I/O of any kind.

## Review Focus

- **A `Union` mixing a healthy leaf with both a `CONTENT`-drifted and a
  `STRUCTURAL`-drifted leaf in the same fact.** A reasonable person would
  expect both problems listed, each correctly and independently
  classified, with the healthy leaf silently omitted — not merged,
  collapsed to one classification, or all three retained. Tested directly.
- **A `SweepReport` where every leaf is healthy.** A reasonable person
  would expect `flagged` to be genuinely empty (`{}`), not populated with
  keys mapping to empty tuples that a caller might mistake for "something
  to review." Tested directly.
- **An empty `SweepReport`** (from `sweep({}, ...)`, the most common
  degenerate case). A reasonable person would expect a valid, empty
  `ReviewSummary`, not a crash on an empty pass-through tuple. Tested
  directly.
- **Non-empty `unresolved_families`/`excluded_keys`.** A reasonable
  person would expect these to appear verbatim on the output, not
  silently dropped or transformed by a function whose whole job is
  producing a *more* complete picture, not a smaller one. Tested directly.
- **Data fidelity through the transformation.** A reasonable person would
  expect a `FlaggedLeaf`'s `leaf`/`outcome` to be the exact same objects
  that came from the `SweepReport`, not copies that have silently dropped
  which selector/family/hash they came from. Tested directly (`==`
  identity checks against the original `Leaf`/`ResolutionOutcome`).

---

## Task 1: `DriftKind`, `FlaggedLeaf`, `ReviewSummary`, `summarize_for_review`

**Files:**
- Create: `review_surfacing/__init__.py`
- Create: `review_surfacing/summarize.py`
- Create: `tests/review_surfacing/__init__.py`
- Test: `tests/review_surfacing/test_summarize.py`

**Interfaces:**
- Consumes: `SweepReport`, `FamilyResolutionFailure` (`staleness_sweep.sweep`, already merged); `sweep()` (`staleness_sweep.sweep`, for building real test fixtures); `LeafCheckResult` (`reference_model.cite`); `Leaf`, `Status`, `SubjectDocument` (`reference_model.model`); `cite`, `cite_union` (`reference_model.cite`); `XPathSelector` (`reference_model.selectors.xpath_selector`).
- Produces: `DriftKind` (enum: `CONTENT`, `STRUCTURAL`), `FlaggedLeaf(leaf, outcome, drift_kind)`, `ReviewSummary(flagged, unresolved_families, excluded_keys)`, `summarize_for_review(report: SweepReport) -> ReviewSummary`.

- [ ] **Step 1: Create the package skeleton**

`review_surfacing/__init__.py`:

```python
"""Classifies a SweepReport's entries into what a human reviewer needs to
see first: what's flagged, and what kind of problem it is. Deliberately
presentation-agnostic -- no rendering, no CLI, no web UI. See
docs/specs/2026-09-23-review-surfacing-design.md.
"""
```

`tests/review_surfacing/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/review_surfacing/test_summarize.py`:

```python
import shutil

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from review_surfacing.summarize import DriftKind, summarize_for_review
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
# A real element that is a SIBLING of xs:complexContent (which holds
# AbgefKapitalertragsteuer), not an ancestor or descendant of it -- so
# mutating ABGEF never changes this element's own canonical bytes. Real
# text, verified live: "Meldung nach § 45c Absatz 2 Satz 3 EStG."
MELDEART_DOC_XPATH = "/xs:schema/xs:complexType[@name='Meldeart23']/xs:annotation/xs:documentation"


def _real_meldeart23_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_MELDEART23_XSD)


def _make_content_and_structural_snapshot(module_root):
    """Copies the real corpus into module_root, then creates a synthetic
    1.03 snapshot that content-drifts ABGEF and structurally breaks AOrdNr,
    leaving MELDEART_DOC_XPATH's own target untouched. Points _current at
    1.03. Never touches the real /work/ontologies repo."""
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


def test_healthy_report_produces_an_entirely_empty_summary():
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    summary = summarize_for_review(report)

    assert summary.flagged == {}
    assert summary.unresolved_families == ()
    assert summary.excluded_keys == ()


def test_empty_sweep_report_produces_an_empty_summary():
    report = sweep({}, REAL_MODULE_ROOT)
    summary = summarize_for_review(report)

    assert summary.flagged == {}
    assert summary.unresolved_families == ()
    assert summary.excluded_keys == ()


def test_content_drift_is_classified_as_content(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))

    summary = summarize_for_review(report)

    assert list(summary.flagged.keys()) == ["fact-1"]
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.drift_kind == DriftKind.CONTENT
    assert flagged_leaf.outcome.status == Status.RESOLVED
    assert flagged_leaf.leaf == leaf


def test_structural_drift_is_classified_as_structural(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))

    summary = summarize_for_review(report)

    assert list(summary.flagged.keys()) == ["fact-1"]
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL
    assert flagged_leaf.outcome.status == Status.NOT_FOUND
    assert flagged_leaf.leaf == leaf


def test_union_mixing_healthy_content_and_structural_leaves(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    healthy_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(MELDEART_DOC_XPATH))
    content_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    structural_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([healthy_leaf, content_leaf, structural_leaf])

    report = sweep({"fact-1": union}, str(module_root))
    summary = summarize_for_review(report)

    flagged_by_kind = {fl.drift_kind: fl for fl in summary.flagged["fact-1"]}
    assert len(summary.flagged["fact-1"]) == 2
    assert flagged_by_kind[DriftKind.CONTENT].leaf == content_leaf
    assert flagged_by_kind[DriftKind.STRUCTURAL].leaf == structural_leaf
    assert all(fl.leaf != healthy_leaf for fl in summary.flagged["fact-1"])


def test_unresolved_families_and_excluded_keys_pass_through_verbatim():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    summary = summarize_for_review(report)

    assert summary.unresolved_families == report.family_resolution_failures
    assert summary.excluded_keys == report.excluded_keys
    assert summary.excluded_keys == ("fact-1",)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/review_surfacing/test_summarize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'review_surfacing.summarize'`

- [ ] **Step 4: Implement `review_surfacing/summarize.py`**

```python
"""Classifies a SweepReport's entries into what a human reviewer needs to
see first. See docs/specs/2026-09-23-review-surfacing-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from reference_model.cite import LeafCheckResult
from reference_model.model import Leaf, ResolutionOutcome, Status
from staleness_sweep.sweep import FamilyResolutionFailure, SweepReport


class DriftKind(Enum):
    CONTENT = "CONTENT"
    STRUCTURAL = "STRUCTURAL"


@dataclass(frozen=True)
class FlaggedLeaf:
    leaf: Leaf
    outcome: ResolutionOutcome
    drift_kind: DriftKind


@dataclass(frozen=True)
class ReviewSummary:
    flagged: dict[str, tuple[FlaggedLeaf, ...]]
    unresolved_families: tuple[FamilyResolutionFailure, ...]
    excluded_keys: tuple[str, ...]


def _classify(result: LeafCheckResult) -> FlaggedLeaf | None:
    if result.outcome.status == Status.RESOLVED:
        if result.hash_changed:
            return FlaggedLeaf(result.leaf, result.outcome, DriftKind.CONTENT)
        return None
    return FlaggedLeaf(result.leaf, result.outcome, DriftKind.STRUCTURAL)


def summarize_for_review(report: SweepReport) -> ReviewSummary:
    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for key, results in report.results_by_key.items():
        problematic = [fl for fl in (_classify(result) for result in results) if fl is not None]
        if problematic:
            flagged[key] = tuple(problematic)

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=report.family_resolution_failures,
        excluded_keys=report.excluded_keys,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/review_surfacing/test_summarize.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (76 tests: 46 under `tests/reference_model/`, 24 under
`tests/staleness_sweep/`, 6 under `tests/review_surfacing/test_summarize.py`)

- [ ] **Step 7: Add `review_surfacing*` to `pyproject.toml`'s packages list**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` section:

```toml
[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*"]
```

- [ ] **Step 8: Reinstall and verify the package is importable from outside the repo root**

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
cd /tmp && python3 -c "import review_surfacing; print('importable')"
```

Expected: `importable`

- [ ] **Step 9: Commit**

```bash
cd /work/generator
git add review_surfacing/__init__.py review_surfacing/summarize.py tests/review_surfacing/__init__.py tests/review_surfacing/test_summarize.py pyproject.toml
git commit -m "Add review_surfacing: classify SweepReport entries by drift kind for a reviewer"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `DriftKind`, `FlaggedLeaf`, `ReviewSummary`, and `summarize_for_review()`
  are implemented with the semantics in the spec.
- [ ] All tests pass: `pytest tests/ -v` → 76 passed.
- [ ] A `SweepReport` with a mix of healthy, content-drifted, structurally-broken,
  and excluded entries produces a `ReviewSummary` whose `flagged` dict
  contains exactly the problematic keys, each correctly classified
  (`test_union_mixing_healthy_content_and_structural_leaves`).
