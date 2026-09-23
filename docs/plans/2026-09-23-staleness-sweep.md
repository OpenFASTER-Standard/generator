# Staleness Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `resolve_current_location()` and `sweep()`/`SweepReport`
from `docs/specs/2026-09-23-staleness-sweep-design.md`, batching
`reference_model`'s already-built `check_reference()` across many
`Reference`s at once against the real, snapshot-versioned `ontologies`
corpus — and, as a prerequisite, delete the old pre-reset codebase this
repo still carries (it isn't being extended, and its tests would
otherwise break once the real corpus is restructured) and restructure
that real corpus into the snapshot layout the design depends on.

**Architecture:** A new, standalone `staleness_sweep/` package (sibling to
`reference_model/`, depending on it, nothing else) with two small
modules: `resolve.py` (family → current file, reading a plain-text
`_current` pointer and a per-snapshot `_manifest.json`, zero filename
parsing) and `sweep.py` (batches `check_reference()` across a caller-keyed
dict of `Reference`s). Two prerequisite, non-code tasks come first: remove
the old codebase, and restructure the real `mikadiv-fm/sources/` corpus.

**Tech Stack:** Python 3.11, stdlib only for the new code (`json`,
`pathlib`) plus `reference_model` itself. No new dependencies.

**Spec:** `docs/specs/2026-09-23-staleness-sweep-design.md`

## Global Constraints

- Snapshot layout: `{module_root}/_current` (plain text, one line, the
  version string) + `{module_root}/{version}/_manifest.json` (JSON,
  `{family: path-relative-to-snapshot-dir}`, covering every family in
  that snapshot). Written once at fetch time; only `_current` is ever
  edited across a re-fetch. Old snapshot directories are kept permanently.
- The real MiKaDiv-FM snapshot version is `1.02` — confirmed uniform
  across every `MiKaDiv_FM_*.xsd` file's own filename. Named by the real
  schema release version, not a fetch date.
- `resolve_current_location` reuses `reference_model.model.Status`/
  `ResolutionOutcome` directly — no new outcome vocabulary.
- A missing/unreadable `_current`, or a family absent from the manifest →
  `Status.NOT_FOUND` (expected, not a bug). A manifest naming a snapshot
  with no `_manifest.json`, a path that doesn't exist, or a path that
  resolves outside its own snapshot directory → raise
  `CorpusIntegrityError`, never a `Status` value — the corpus's own
  metadata is inconsistent with reality, which is a different kind of
  problem than "content drifted."
- `sweep()` takes exactly one `module_root` per call.
- Any `Reference` touching an unresolved family is excluded from
  `SweepReport.results_by_key` entirely — `sweep()` never relies on
  `check_reference()`'s own default (falling back to a `Leaf`'s originally
  stored `retrieval_uri` when no override is given), since that default
  exists for a different calling pattern and would risk a misleading
  "unchanged" here.
- No fake version bump is ever committed to the real `mikadiv-fm/sources/`
  corpus — every multi-snapshot test scenario uses a `tmp_path` copy.

## Review Focus

- **A hand-edited (or malicious) manifest entry using `../` to escape its
  own snapshot directory.** A reasonable person maintaining this file by
  hand could make this mistake without meaning any harm; either way, a
  resolved path silently pointing outside the snapshot it claims to
  belong to is not something to trust. Task 3 rejects it explicitly.
- **A `_current` file with trailing whitespace/a newline** — the kind of
  artifact almost any text editor adds by default when hand-writing a
  one-line file. A reasonable person would expect this to still resolve
  correctly, not silently look up the wrong (or no) snapshot. Task 3
  tests this directly.
- **Two `Reference`s in the same `sweep()` batch sharing a family but
  each with a different (and possibly stale) originally-stored
  `retrieval_uri`.** A reasonable person would expect `sweep()` to check
  both against the one, freshly-resolved current file — not silently let
  either one's own stale stored path leak through. Task 4 tests this with
  a citation whose stored path is a deliberately mutated copy, confirming
  the sweep still checks the real current file instead.
- **An empty `references` dict.** A reasonable person calling `sweep()`
  with nothing to check would expect an empty, valid report back — not a
  crash from an empty-collection edge case in family collection. Task 4
  tests this directly.
- **A `Union` where only some of its leaves belong to an unresolvable
  family.** Per the spec, the whole `Reference` is excluded from
  `results_by_key`, not partially reported — a reasonable person reading
  a sweep report would otherwise wrongly conclude the resolvable leaf was
  actually checked. Task 4 tests this directly.

---

## Task 1: Delete the old, pre-reset codebase

**Files:**
- Delete: `citations/`, `equivalence/`, `extraction/`, `generation/`, `ingestion/`, `provenance/`, `reporting/`, `review/`, `store/`, `webapp/`, `frontend/`, `report.html`
- Delete: `tests/citations/`, `tests/equivalence/`, `tests/extraction/`, `tests/provenance/`, `tests/reporting/`, `tests/review/`, `tests/store/`, `tests/webapp/`, `tests/test_package_structure.py`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:** None — this task only removes code and tests; it produces
nothing later tasks consume beyond a clean, minimal `pyproject.toml`.

This code was never being extended (per this project's own explicit
"build from scratch" reset earlier this session) and is about to actively
get in the way: restructuring the real `mikadiv-fm/sources/` corpus (Task
2) will break the literal file paths 29 of its test files reference,
since they were all written against the old flat layout.

- [ ] **Step 1: Delete the old top-level packages, their tests, and the generated report artifact**

```bash
git rm -r citations equivalence extraction generation ingestion provenance reporting review store webapp frontend
git rm report.html
git rm -r tests/citations tests/equivalence tests/extraction tests/provenance tests/reporting tests/review tests/store tests/webapp
git rm tests/test_package_structure.py
find . -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null
```

Note: `tests/reference_model/test_package_structure.py` is a **different,
new** file — do not touch it.

- [ ] **Step 2: Rewrite `pyproject.toml` to only what `reference_model`/`staleness_sweep` actually need**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "openfaster-generator"
version = "0.1.0"
description = "Source reference model and staleness-sweep tooling for OpenFASTER's MiKaDiv-FM regulatory schema"
requires-python = ">=3.11"
dependencies = [
    "lxml>=5.0",
    "pdfplumber>=0.11",
    "shapely>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "reportlab>=4.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*"]
```

- [ ] **Step 3: Rewrite `README.md`**

```markdown
# OpenFASTER Generator

Part of [OpenFASTER](https://openfaster.org). Built from scratch against
real [`ontologies`](https://github.com/OpenFASTER-Standard/ontologies)
source material (Germany's MiKaDiv-FM regulatory schema: XSDs + BZSt
guidance PDFs) and externally researched prior art -- not built on or
migrating from any prior code in this repo's own history. See
`docs/specs/` for the full design record, one sub-project at a time.

## Layout

- `reference_model/` -- a format-agnostic `Reference` (citation) model:
  records exactly what real source span (an XSD element, a PDF page
  region) backs a fact, precise enough to re-locate later and soundly
  flag when it may have changed. See
  `docs/specs/2026-09-23-source-reference-model-design.md`.
- `staleness_sweep/` -- batches `reference_model`'s own `check_reference()`
  across many `Reference`s at once against the real, snapshot-versioned
  `ontologies` corpus. See `docs/specs/2026-09-23-staleness-sweep-design.md`.

Licensed MIT.
```

- [ ] **Step 4: Reinstall and verify only `reference_model` remains**

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
python3 -m pytest tests/ -v
```

Expected: `46 passed` (all under `tests/reference_model/`), zero
collection errors, zero references to the deleted packages anywhere in
the output.

- [ ] **Step 5: Confirm no dangling imports of the deleted packages remain**

```bash
grep -rlE "^(import|from) (citations|equivalence|extraction|generation|ingestion|provenance|reporting|review|store|webapp)\b" --include=*.py .
```

Expected: no output (empty result).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md
git commit -m "Remove the old pre-reset codebase (never extended, would break once mikadiv-fm/sources/ is restructured)"
```

---

## Task 2: Restructure the real `mikadiv-fm/sources/` corpus into the snapshot layout

**Files (in the separate `/work/ontologies` repository, not `generator`):**
- Modify: `mikadiv-fm/sources/` (directory restructuring)
- Create: `mikadiv-fm/sources/_current`
- Create: `mikadiv-fm/sources/1.02/_manifest.json`
- Modify: `mikadiv-fm/sources/README.md`

**Interfaces:** None new for later tasks — Task 3 reads these real files
directly by path, not through any code produced here.

This is a real, git-tracked rename in a separate repo
(`github.com/OpenFASTER-Standard/ontologies`) — confirmed no test suite
or script in that repo references the old flat paths, so this is safe
there. It's fully reversible via `git revert` if anything looks wrong.

- [ ] **Step 1: Move both real source directories under a new `1.02/` snapshot directory**

```bash
cd /work/ontologies/mikadiv-fm/sources
mkdir -p 1.02
git mv xsd 1.02/xsd
git mv khb 1.02/khb
```

- [ ] **Step 2: Verify the move**

```bash
find /work/ontologies/mikadiv-fm/sources -maxdepth 3 -type f | sort
```

Expected: 13 files under `1.02/xsd/`, 8 files under `1.02/khb/`, plus
`README.md` still at the top level — 22 lines total.

- [ ] **Step 3: Write `_current`**

```bash
printf '1.02' > /work/ontologies/mikadiv-fm/sources/_current
```

- [ ] **Step 4: Write `1.02/_manifest.json`**

```bash
cat > /work/ontologies/mikadiv-fm/sources/1.02/_manifest.json <<'EOF'
{
  "MiKaDiv_FM": "xsd/MiKaDiv_FM_1.02.xsd",
  "MiKaDiv_FM_Fachtypen": "xsd/MiKaDiv_FM_Fachtypen_1.02.xsd",
  "MiKaDiv_FM_Meldeart11": "xsd/MiKaDiv_FM_Meldeart11_1.02.xsd",
  "MiKaDiv_FM_Meldeart13": "xsd/MiKaDiv_FM_Meldeart13_1.02.xsd",
  "MiKaDiv_FM_Meldeart21": "xsd/MiKaDiv_FM_Meldeart21_1.02.xsd",
  "MiKaDiv_FM_Meldeart22": "xsd/MiKaDiv_FM_Meldeart22_1.02.xsd",
  "MiKaDiv_FM_Meldeart23": "xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
  "MiKaDiv_FM_MeldeartErg": "xsd/MiKaDiv_FM_MeldeartErg_1.02.xsd",
  "MiKaDiv_FM_MeldeartenBasis": "xsd/MiKaDiv_FM_MeldeartenBasis_1.02.xsd",
  "MiKaDiv_FM_MeldeartenSonder": "xsd/MiKaDiv_FM_MeldeartenSonder_1.02.xsd",
  "MiKaDiv_FM_Personentypen": "xsd/MiKaDiv_FM_Personentypen_1.02.xsd",
  "MiKaDiv_FM_Standardtypen": "xsd/MiKaDiv_FM_Standardtypen_1.02.xsd",
  "din-norm-91379-datatypes": "xsd/din-norm-91379-datatypes.xsd",
  "ausstellung_steuerbescheinigung": "khb/ausstellung_steuerbescheinigung_v7.pdf",
  "einzelfragen_datenuebermittlung_de": "khb/einzelfragen_datenuebermittlung_de_v8.pdf",
  "individual_questions_en": "khb/individual_questions_en_v1.pdf",
  "khb_mikadiv_fm_anlage_de": "khb/khb_mikadiv_fm_anlage_de_v8.pdf",
  "khb_mikadiv_fm_anlage_en": "khb/khb_mikadiv_fm_anlage_en_v3.pdf",
  "khb_mikadiv_fm_de": "khb/khb_mikadiv_fm_de_v9.pdf",
  "khb_mikadiv_fm_en": "khb/khb_mikadiv_fm_en_v3.pdf",
  "verfahrensleitende_hinweise": "khb/verfahrensleitende_hinweise_v8.pdf"
}
EOF
```

- [ ] **Step 5: Verify every manifest entry resolves to a real file**

```bash
python3 -c "
import json
from pathlib import Path

root = Path('/work/ontologies/mikadiv-fm/sources/1.02')
manifest = json.loads((root / '_manifest.json').read_text())
assert len(manifest) == 21, len(manifest)
for family, rel_path in manifest.items():
    full_path = root / rel_path
    assert full_path.exists(), f'{family}: {full_path} missing'
print('all 21 families resolve to real files')
"
```

Expected: `all 21 families resolve to real files`

- [ ] **Step 6: Update `mikadiv-fm/sources/README.md`'s status line and add a short layout note**

Change the top `**Status: ...**` line to:

```markdown
**Status: committed, current as of the `xsd_mikadiv_fm.zip` v8 /
`khb_mikadiv_fm.pdf` v9 release fetched 2026-09-14. Structured as one
subdirectory per whole-module snapshot, versioned by the real MiKaDiv-FM
schema release (currently `1.02`) -- see `_current` and each snapshot's
own `_manifest.json`. Re-fetching adds a new snapshot directory rather
than overwriting this one; nothing here is ever deleted.**
```

- [ ] **Step 7: Commit and push in the `ontologies` repo**

```bash
cd /work/ontologies
git add mikadiv-fm/sources
git commit -m "Restructure mikadiv-fm/sources into one subdirectory per snapshot (1.02), with a _current pointer and per-snapshot _manifest.json"
git push origin main
```

---

## Task 3: `resolve_current_location`

**Files:**
- Create: `staleness_sweep/__init__.py`
- Create: `staleness_sweep/resolve.py`
- Create: `tests/staleness_sweep/__init__.py`
- Test: `tests/staleness_sweep/test_resolve.py`

**Interfaces:**
- Consumes: `ResolutionOutcome`, `Status` (`reference_model.model`, already merged).
- Produces: `CorpusIntegrityError`, `resolve_current_location(module_root: str, family: str) -> ResolutionOutcome`.

- [ ] **Step 1: Create the package skeleton**

`staleness_sweep/__init__.py`:

```python
"""Batches reference_model's check_reference() across many References at
once against a git-tracked, snapshot-versioned corpus. See
docs/specs/2026-09-23-staleness-sweep-design.md.
"""
```

`tests/staleness_sweep/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/staleness_sweep/test_resolve.py`:

```python
import json
from pathlib import Path

import pytest

from reference_model.model import Status
from staleness_sweep.resolve import CorpusIntegrityError, resolve_current_location

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"


def test_resolves_a_real_family_to_its_real_current_path():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "MiKaDiv_FM_Meldeart23")
    assert outcome.status == Status.RESOLVED
    expected = str(Path(REAL_MODULE_ROOT) / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd")
    assert outcome.raw_content == expected
    assert Path(outcome.raw_content).exists()


def test_resolves_the_unversioned_din_family_too():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "din-norm-91379-datatypes")
    assert outcome.status == Status.RESOLVED
    assert Path(outcome.raw_content).exists()


def test_unknown_family_is_not_found():
    outcome = resolve_current_location(REAL_MODULE_ROOT, "NoSuchFamilyEver")
    assert outcome.status == Status.NOT_FOUND


def test_missing_current_pointer_is_not_found(tmp_path):
    outcome = resolve_current_location(str(tmp_path), "AnyFamily")
    assert outcome.status == Status.NOT_FOUND


def test_current_pointer_with_trailing_whitespace_is_handled(tmp_path):
    snapshot_dir = tmp_path / "1.0"
    snapshot_dir.mkdir()
    (tmp_path / "_current").write_text("1.0\n")
    (snapshot_dir / "file.xsd").write_text("<real/>")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"Family": "file.xsd"}))

    outcome = resolve_current_location(str(tmp_path), "Family")
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == str(snapshot_dir / "file.xsd")


def test_missing_manifest_for_the_pointed_at_snapshot_raises(tmp_path):
    (tmp_path / "_current").write_text("9.99")
    (tmp_path / "9.99").mkdir()
    with pytest.raises(CorpusIntegrityError, match="9.99"):
        resolve_current_location(str(tmp_path), "AnyFamily")


def test_manifest_naming_a_nonexistent_file_raises(tmp_path):
    snapshot_dir = tmp_path / "1.0"
    snapshot_dir.mkdir()
    (tmp_path / "_current").write_text("1.0")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"GhostFamily": "xsd/does-not-exist.xsd"}))

    with pytest.raises(CorpusIntegrityError, match="does-not-exist"):
        resolve_current_location(str(tmp_path), "GhostFamily")


def test_manifest_entry_escaping_the_snapshot_directory_is_rejected(tmp_path):
    module_root = tmp_path / "module"
    module_root.mkdir()
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir()
    (module_root / "_current").write_text("1.0")

    outside_file = tmp_path / "outside.xsd"  # sibling of module_root, not under it
    outside_file.write_text("<outside/>")
    (snapshot_dir / "_manifest.json").write_text(json.dumps({"EscapingFamily": "../../outside.xsd"}))

    with pytest.raises(CorpusIntegrityError, match="escapes"):
        resolve_current_location(str(module_root), "EscapingFamily")


def test_a_second_synthetic_snapshot_resolves_independently(tmp_path):
    snap1 = tmp_path / "1.0"
    snap1.mkdir()
    (snap1 / "file-v1.xsd").write_text("<old/>")
    (snap1 / "_manifest.json").write_text(json.dumps({"Family": "file-v1.xsd"}))

    snap2 = tmp_path / "2.0"
    snap2.mkdir()
    (snap2 / "file-v2.xsd").write_text("<new/>")
    (snap2 / "_manifest.json").write_text(json.dumps({"Family": "file-v2.xsd"}))

    (tmp_path / "_current").write_text("2.0")

    outcome = resolve_current_location(str(tmp_path), "Family")
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == str(snap2 / "file-v2.xsd")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/staleness_sweep/test_resolve.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'staleness_sweep.resolve'`

- [ ] **Step 4: Implement `staleness_sweep/resolve.py`**

```python
"""Resolves a family name to its current real file, using the real
ontologies-repo convention: a plain-text _current pointer naming the
current snapshot version, and a per-snapshot _manifest.json mapping every
family to its real filename (relative to that snapshot's own directory).
No filename parsing anywhere. See
docs/specs/2026-09-23-staleness-sweep-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from reference_model.model import ResolutionOutcome, Status


class CorpusIntegrityError(Exception):
    pass


def resolve_current_location(module_root: str, family: str) -> ResolutionOutcome:
    current_path = Path(module_root) / "_current"
    if not current_path.exists():
        return ResolutionOutcome(status=Status.NOT_FOUND)

    snapshot = current_path.read_text().strip()
    snapshot_dir = Path(module_root) / snapshot
    manifest_path = snapshot_dir / "_manifest.json"
    if not manifest_path.exists():
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r} but {manifest_path} does not exist"
        )

    manifest = json.loads(manifest_path.read_text())
    if family not in manifest:
        return ResolutionOutcome(status=Status.NOT_FOUND)

    resolved_snapshot_dir = snapshot_dir.resolve()
    resolved_path = (snapshot_dir / manifest[family]).resolve()
    if not resolved_path.is_relative_to(resolved_snapshot_dir):
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, which escapes the snapshot directory {snapshot_dir}"
        )
    if not resolved_path.exists():
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, but {resolved_path} does not exist"
        )

    return ResolutionOutcome(status=Status.RESOLVED, raw_content=str(resolved_path))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/staleness_sweep/test_resolve.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add staleness_sweep/__init__.py staleness_sweep/resolve.py tests/staleness_sweep/__init__.py tests/staleness_sweep/test_resolve.py
git commit -m "Add resolve_current_location(): family -> current real file, no filename parsing"
```

---

## Task 4: `sweep()` and `SweepReport`

**Files:**
- Create: `staleness_sweep/sweep.py`
- Test: `tests/staleness_sweep/test_sweep.py`

**Interfaces:**
- Consumes: `Leaf`, `Reference`, `Status` (Task 1 of the reference-model plan, already merged); `LeafCheckResult`, `check_reference`, `cite`, `cite_union` (`reference_model.cite`, already merged); `SubjectDocument` (`reference_model.model`); `XPathSelector` (`reference_model.selectors.xpath_selector`); `resolve_current_location` (Task 3 above).
- Produces: `FamilyResolutionFailure(family, status)`, `SweepReport(results_by_key, family_resolution_failures)`, `sweep(references: dict[str, Reference], module_root: str) -> SweepReport`.

- [ ] **Step 1: Write the failing tests**

`tests/staleness_sweep/test_sweep.py`:

```python
import shutil
from pathlib import Path

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from staleness_sweep.sweep import FamilyResolutionFailure, sweep

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


def test_sweep_reports_a_real_reference_as_unchanged():
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    assert report.family_resolution_failures == ()
    assert report.results_by_key["fact-1"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["fact-1"][0].hash_changed is False


def test_sweep_reports_an_unresolvable_family_as_a_failure_not_a_leaf_result():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )
    assert "fact-1" not in report.results_by_key


def test_sweep_with_no_references_returns_an_empty_report():
    report = sweep({}, REAL_MODULE_ROOT)
    assert report.results_by_key == {}
    assert report.family_resolution_failures == ()


def test_sweep_uses_the_resolved_current_path_not_a_leaf_own_stale_stored_uri(tmp_path):
    stale_copy = tmp_path / "stale-copy.xsd"
    original = Path(REAL_MELDEART23_XSD).read_text(encoding="utf-8")
    # Mutate the very element this leaf cites, in the stale copy only --
    # citing against the stale copy captures the MUTATED content as the
    # leaf's stored hash.
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    assert mutated != original  # confirms the replace actually matched something real
    stale_copy.write_text(mutated, encoding="utf-8")

    stale_subject_document = SubjectDocument(
        family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=str(stale_copy)
    )
    leaf = cite(stale_subject_document, XPathSelector.create(ABGEF_XPATH))

    report = sweep({"fact": leaf}, REAL_MODULE_ROOT)

    # The leaf's own stored retrieval_uri (stale_copy) still has the
    # mutation baked into its stored hash, so falling back to checking
    # THAT path again would report unchanged. The real current file was
    # never mutated, so if sweep() correctly used the resolved current
    # path instead, the content reverts relative to what was stored and
    # this must report a real change -- the only way to tell which path
    # sweep() actually used.
    assert report.results_by_key["fact"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["fact"][0].hash_changed is True


def test_union_with_one_unresolvable_family_is_fully_excluded_from_results():
    good_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    bad_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    bad_leaf = cite(bad_subject_document, XPathSelector.create(ABGEF_XPATH))
    union = cite_union([good_leaf, bad_leaf])

    report = sweep({"fact": union}, REAL_MODULE_ROOT)

    assert "fact" not in report.results_by_key
    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )


def test_sweep_over_a_deliberately_changed_synthetic_snapshot(tmp_path):
    # The spec's own Definition of Done scenario: cite a real fact, then
    # sweep against a tmp_path copy of the corpus with one deliberate
    # change on a second, synthetic snapshot -- never the real repo.
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)

    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')

    new_snapshot = module_root / "1.03"
    shutil.copytree(module_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (module_root / "_current").write_text("1.03")

    changed_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    unchanged_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))

    report = sweep({"changed-fact": changed_leaf, "unchanged-fact": unchanged_leaf}, str(module_root))

    assert report.family_resolution_failures == ()
    assert report.results_by_key["changed-fact"][0].outcome.status == Status.NOT_FOUND
    assert report.results_by_key["unchanged-fact"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["unchanged-fact"][0].hash_changed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/staleness_sweep/test_sweep.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'staleness_sweep.sweep'`

- [ ] **Step 3: Implement `staleness_sweep/sweep.py`**

```python
"""Batches reference_model's check_reference() across many References at
once. See docs/specs/2026-09-23-staleness-sweep-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from reference_model.cite import LeafCheckResult, check_reference
from reference_model.model import Leaf, Reference, Status
from staleness_sweep.resolve import resolve_current_location


@dataclass(frozen=True)
class FamilyResolutionFailure:
    family: str
    status: Status  # always NOT_FOUND -- see resolve_current_location


@dataclass(frozen=True)
class SweepReport:
    results_by_key: dict[str, list[LeafCheckResult]]
    family_resolution_failures: tuple[FamilyResolutionFailure, ...]


def _collect_families(reference: Reference) -> set[str]:
    if isinstance(reference, Leaf):
        return {reference.subject_document.family}
    families: set[str] = set()
    for part in reference.parts:
        families |= _collect_families(part)
    return families


def sweep(references: dict[str, Reference], module_root: str) -> SweepReport:
    all_families: set[str] = set()
    for reference in references.values():
        all_families |= _collect_families(reference)

    overrides: dict[str, str] = {}
    failures: list[FamilyResolutionFailure] = []
    for family in all_families:
        outcome = resolve_current_location(module_root, family)
        if outcome.status == Status.RESOLVED:
            overrides[family] = outcome.raw_content
        else:
            failures.append(FamilyResolutionFailure(family=family, status=outcome.status))

    failed_families = {failure.family for failure in failures}
    results_by_key = {
        key: check_reference(reference, retrieval_overrides=overrides)
        for key, reference in references.items()
        if not (_collect_families(reference) & failed_families)
    }
    return SweepReport(results_by_key=results_by_key, family_resolution_failures=tuple(failures))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/staleness_sweep/test_sweep.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (61 tests: 46 under `tests/reference_model/`, 9 under
`tests/staleness_sweep/test_resolve.py`, 6 under
`tests/staleness_sweep/test_sweep.py`)

- [ ] **Step 6: Commit**

```bash
git add staleness_sweep/sweep.py tests/staleness_sweep/test_sweep.py
git commit -m "Add sweep()/SweepReport: batch check_reference() across many References"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `mikadiv-fm/sources/` is restructured into the snapshot layout,
  with a real `_current` and `_manifest.json` for the real `1.02`
  snapshot, covering all 21 real families.
- [ ] `resolve_current_location` and `sweep()`/`SweepReport` are
  implemented with the semantics in the spec.
- [ ] All tests pass: `pytest tests/ -v` → 61 passed.
- [ ] Citing a real fact from the restructured corpus, then running
  `sweep()` against a `tmp_path` copy with one deliberate change on a
  second, synthetic snapshot, correctly reports that one change and
  nothing else as flagged (`test_sweep_over_a_deliberately_changed_synthetic_snapshot`).
