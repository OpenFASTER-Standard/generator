# Review Recording Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `JsonSelector` (from
`docs/specs/2026-09-23-review-recording-design.md`) and `record_review()`/
`Verdict` — turning a reviewer's decision into a plain, real JSON document
cited through the exact same `Reference`/`cite()` machinery already built
for XSDs and PDFs, with no new Fact/Revision data model.

**Architecture:** One new selector (`reference_model/selectors/json_selector.py`,
sibling to the existing two) addressing a JSON document via RFC 6901 JSON
Pointer, plus one new small module (`review_recording/record.py`) that
writes a review-result file and cites it. No new third-party dependencies
— JSON Pointer resolution is simple enough to implement directly against
the stdlib `json` module.

**Tech Stack:** Python 3.11, stdlib only, plus `reference_model` (already
merged to `main`).

**Spec:** `docs/specs/2026-09-23-review-recording-design.md`

## Global Constraints

- `JsonSelector` addresses a document via an RFC 6901 JSON Pointer string
  (e.g. `/verdict`, or `""` for the whole document). Only `Status.RESOLVED`
  and `Status.NOT_FOUND` are reachable for this selector type —
  `AMBIGUOUS`/`UNCITABLE` never occur, since a JSON Pointer always
  addresses exactly zero or one location.
- `canonicalize_and_hash` is JCS-inspired (`json.dumps(value,
  sort_keys=True, separators=(",", ":"))`), not byte-exact RFC 8785 — no
  ECMAScript number formatting. Fine since review-result documents are
  all strings.
- Review-result documents live in a caller-supplied `reviews_dir`
  (production use: `ontologies/mikadiv-fm/reviews/`), one file per review,
  named `{uuid4}.json`. Each file is immutable and permanent once written.
- `record_review()`'s `family` is `f"review-{review_id}"` (prefixed so it
  never collides with a real schema family); `version` is the constant
  `"1"`.
- `record_review()` cites the **whole** document (`JsonSelector.create("")`),
  never a specific field.
- `record_review()` is **not idempotent** — unlike `cite()`'s own
  idempotent citation of an unchanging span, each call represents a
  distinct human review event and produces a distinct `review_id`/
  `family`/`Leaf`, even if called twice with identical arguments.

## Review Focus

- **A JSON value that is `null`, `false`, or `0`** — a reasonable person
  would expect these "falsy-but-present" values to resolve as `RESOLVED`
  with that real value, not be misclassified as `NOT_FOUND` by a
  truthiness check in the resolver (`if value:` instead of "does this key
  exist"). Tested directly, for all three values.
- **A JSON Pointer using RFC 6901's own escape sequences** (`~0` for a
  literal `~`, `~1` for a literal `/` in a key name) — a reasonable
  person authoring a pointer against a key that happens to contain one of
  these characters would expect it to resolve correctly, not be silently
  misinterpreted as a path separator. Tested directly.
- **Calling `record_review()` twice with identical arguments.** A
  reasonable person would expect two independent review records (two
  files, two distinct `Leaf`s) — each call is a real, separate human
  decision, even if its content happens to match a previous one — not a
  silently deduplicated single record. Tested directly.
- **A JSON Pointer that continues past a scalar** (e.g. indexing into a
  string or number as if it were an object/array). A reasonable person
  authoring a slightly-wrong pointer would expect a clean `NOT_FOUND`, not
  an unhandled exception crashing the whole `resolve()` call. Tested
  directly.
- **`reviews_dir` not existing yet** (the very first review ever
  recorded). A reasonable person calling `record_review()` for the first
  time would expect it to just work, not require the directory to be
  pre-created. Tested directly.

---

## Task 1: `JsonSelector`

**Files:**
- Create: `reference_model/selectors/json_selector.py`
- Modify: `reference_model/selectors/__init__.py`
- Test: `tests/reference_model/test_json_selector.py`

**Interfaces:**
- Consumes: `ResolutionOutcome`, `Status` (`reference_model.model`); `Resolver`, `register` (`reference_model.registry`).
- Produces: `JsonSelector(type, pointer)` with `JsonSelector.create(pointer: str) -> JsonSelector`; registers `"JsonSelector"` in the registry as an import side effect.

- [ ] **Step 1: Write the failing tests**

`tests/reference_model/test_json_selector.py`:

```python
import json

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.json_selector import JsonSelector

FIXTURE = {
    "verdict": "approved",
    "nested": {"reasoning": "looks fine"},
    "items": ["a", "b", "c"],
    "flags": {"is_null": None, "is_false": False, "is_zero": 0},
    "weird/key": "slash-in-key",
    "tilde~key": "tilde-in-key",
}


def _write_fixture(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(FIXTURE), encoding="utf-8")
    return str(path)


def _resolver():
    return get_resolver("JsonSelector")


def test_resolves_a_nested_object_field(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/nested/reasoning"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "looks fine"


def test_resolves_an_array_index(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/items/1"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "b"


def test_resolves_null_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_null"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content is None


def test_resolves_false_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_false"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content is False


def test_resolves_zero_value_as_resolved_not_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/flags/is_zero"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == 0


def test_resolves_escaped_slash_in_key(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/weird~1key"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "slash-in-key"


def test_resolves_escaped_tilde_in_key(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/tilde~0key"), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "tilde-in-key"


def test_empty_pointer_resolves_whole_document(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create(""), fixture_path)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == FIXTURE


def test_missing_key_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/nonexistent"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_out_of_range_index_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/items/99"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_indexing_into_a_scalar_is_not_found(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    outcome = _resolver().resolve(JsonSelector.create("/verdict/oops"), fixture_path)
    assert outcome.status == Status.NOT_FOUND


def test_missing_file_is_not_found():
    outcome = _resolver().resolve(JsonSelector.create("/verdict"), "/nonexistent/does-not-exist.json")
    assert outcome.status == Status.NOT_FOUND


def test_malformed_json_is_not_found(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text("{not valid json", encoding="utf-8")
    outcome = _resolver().resolve(JsonSelector.create("/verdict"), str(path))
    assert outcome.status == Status.NOT_FOUND


def test_hash_is_reproducible_and_sensitive_to_different_values(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    resolver = _resolver()

    outcome_1 = resolver.resolve(JsonSelector.create("/verdict"), fixture_path)
    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)
    outcome_2 = resolver.resolve(JsonSelector.create("/verdict"), fixture_path)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)
    assert digest_1 == digest_2
    assert len(digest_1) == 64

    other_outcome = resolver.resolve(JsonSelector.create("/nested/reasoning"), fixture_path)
    other_digest = resolver.canonicalize_and_hash(other_outcome.raw_content)
    assert other_digest != digest_1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/reference_model/test_json_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reference_model.selectors.json_selector'`

- [ ] **Step 3: Implement `reference_model/selectors/json_selector.py`**

```python
"""JsonSelector: addresses a value inside a JSON document via a real
standard, RFC 6901 JSON Pointer -- the JSON analogue of XPath. Unlike
XPath, a JSON Pointer always addresses exactly zero or one location, so
this selector's resolve() only ever returns RESOLVED or NOT_FOUND;
AMBIGUOUS/UNCITABLE never occur.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register


@dataclass(frozen=True)
class JsonSelector:
    type: str
    pointer: str  # RFC 6901 JSON Pointer, e.g. "/verdict" or "" for the whole document

    @staticmethod
    def create(pointer: str) -> "JsonSelector":
        return JsonSelector(type="JsonSelector", pointer=pointer)


def _resolve_pointer(document, pointer: str):
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON Pointer (must start with '/'): {pointer!r}")

    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")  # RFC 6901 escaping
        if isinstance(current, dict):
            current = current[token]  # raises KeyError if missing
        elif isinstance(current, list):
            current = current[int(token)]  # raises ValueError (non-numeric) or IndexError
        else:
            raise KeyError(token)  # can't descend further into a scalar
    return current


def resolve(selector: JsonSelector, retrieval_uri: str) -> ResolutionOutcome:
    try:
        with open(retrieval_uri, encoding="utf-8") as f:
            document = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ResolutionOutcome(status=Status.NOT_FOUND)

    try:
        value = _resolve_pointer(document, selector.pointer)
    except (KeyError, IndexError, ValueError):
        return ResolutionOutcome(status=Status.NOT_FOUND)

    return ResolutionOutcome(status=Status.RESOLVED, raw_content=value)


def canonicalize_and_hash(raw_content) -> str:
    # JCS-inspired (sorted keys, no incidental whitespace), not byte-exact
    # RFC 8785 -- no ECMAScript number formatting. Review-result documents
    # are all strings, so this doesn't matter in practice.
    canonical = json.dumps(raw_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


register("JsonSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
```

- [ ] **Step 4: Register the new selector module**

Modify `reference_model/selectors/__init__.py`:

```python
"""Importing this package registers every built-in selector type.
Adding a new format means adding a module here and importing it below --
nothing else changes."""
from reference_model.selectors import json_selector, svg_selector, xpath_selector  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/reference_model/test_json_selector.py -v`
Expected: PASS (14 tests)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (92 tests: 78 previously passing, plus 14 new)

- [ ] **Step 7: Commit**

```bash
git add reference_model/selectors/json_selector.py reference_model/selectors/__init__.py tests/reference_model/test_json_selector.py
git commit -m "Add JsonSelector: address a JSON document via RFC 6901 JSON Pointer"
```

---

## Task 2: `record_review()` and `Verdict`

**Files:**
- Create: `review_recording/__init__.py`
- Create: `review_recording/record.py`
- Create: `tests/review_recording/__init__.py`
- Test: `tests/review_recording/test_record.py`

**Interfaces:**
- Consumes: `Leaf`, `SubjectDocument` (`reference_model.model`); `cite`, `check_leaf` (`reference_model.cite`); `JsonSelector` (`reference_model.selectors.json_selector`, Task 1); `DriftKind` (`review_surfacing.summarize`, already merged).
- Produces: `Verdict` (enum: `APPROVED`, `REJECTED`), `record_review(reviews_dir, fact_key, family, drift_kind, reviewer, verdict, reasoning) -> Leaf`.

- [ ] **Step 1: Create the package skeleton**

`review_recording/__init__.py`:

```python
"""Turns a reviewer's decision into a plain, real JSON document, cited
through the same Reference/cite() machinery already built for XSDs and
PDFs -- no new Fact/Revision data model. See
docs/specs/2026-09-23-review-recording-design.md.
"""
```

`tests/review_recording/__init__.py`: empty file.

- [ ] **Step 2: Write the failing tests**

`tests/review_recording/test_record.py`:

```python
import json

from reference_model.cite import check_leaf
from reference_model.model import Status
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import DriftKind


def test_record_review_returns_a_resolvable_leaf(tmp_path):
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    assert leaf.content_hash.algorithm == "sha256"
    assert len(leaf.content_hash.digest) == 64
    assert leaf.subject_document.family.startswith("review-")
    assert leaf.subject_document.version == "1"


def test_record_review_writes_the_full_document_shape(tmp_path):
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.STRUCTURAL,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="The renamed element needs a real extraction fix.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["fact_key"] == "fact-1"
    assert written["family"] == "MiKaDiv_FM_Meldeart23"
    assert written["drift_kind"] == "STRUCTURAL"
    assert written["reviewer"] == "julian.nalenz@divizend.com"
    assert written["verdict"] == "rejected"
    assert written["reasoning"] == "The renamed element needs a real extraction fix."
    assert "reviewed_at" in written and "T" in written["reviewed_at"]  # a real ISO timestamp


def test_record_review_creates_reviews_dir_if_missing(tmp_path):
    reviews_dir = tmp_path / "does-not-exist-yet"
    assert not reviews_dir.exists()

    leaf = record_review(
        reviews_dir=str(reviews_dir),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First review ever written to this directory.",
    )

    assert reviews_dir.exists()
    written_files = list(reviews_dir.iterdir())
    assert len(written_files) == 1
    assert leaf.subject_document.retrieval_uri == str(written_files[0])


def test_unmodified_review_record_is_unchanged_on_recheck(tmp_path):
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )

    result = check_leaf(leaf)
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is False


def test_two_calls_with_identical_arguments_produce_independent_records(tmp_path):
    kwargs = dict(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
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

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/review_recording/test_record.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'review_recording.record'`

- [ ] **Step 4: Implement `review_recording/record.py`**

```python
"""Turns a reviewer's decision into a plain, real JSON document, cited
through the same Reference/cite() machinery already built for XSDs and
PDFs. See docs/specs/2026-09-23-review-recording-design.md.
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
from review_surfacing.summarize import DriftKind


class Verdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


def record_review(
    reviews_dir: str,
    fact_key: str,
    family: str,
    drift_kind: DriftKind,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Leaf:
    Path(reviews_dir).mkdir(parents=True, exist_ok=True)
    review_id = str(uuid.uuid4())
    document = {
        "fact_key": fact_key,
        "family": family,
        "drift_kind": drift_kind.value,
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

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/review_recording/test_record.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (97 tests: 92 from Task 1, plus 5 new)

- [ ] **Step 7: Add `review_recording*` to `pyproject.toml`'s packages list**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` section:

```toml
[tool.setuptools.packages.find]
include = ["reference_model*", "staleness_sweep*", "review_surfacing*", "review_recording*"]
```

- [ ] **Step 8: Reinstall and verify the package is importable from outside the repo root**

```bash
python3 -m pip install --break-system-packages -e ".[dev]"
cd /tmp && python3 -c "import review_recording; print('importable')"
```

Expected: `importable`

- [ ] **Step 9: Commit**

```bash
cd /work/generator
git add review_recording/__init__.py review_recording/record.py tests/review_recording/__init__.py tests/review_recording/test_record.py pyproject.toml
git commit -m "Add record_review()/Verdict: a reviewer's decision as a citable JSON document"
```

---

## Definition of Done (from the spec, restated as a final check)

- [ ] `JsonSelector` is implemented and registered in the selector-type
  registry, with the semantics in the spec.
- [ ] `record_review()` and `Verdict` are implemented with the semantics
  in the spec.
- [ ] All tests pass: `pytest tests/ -v` → 97 passed.
- [ ] Calling `record_review()` for a real flagged entry produces a real
  JSON file, and the returned `Leaf` successfully re-resolves via
  `check_leaf()` with `hash_changed=False`
  (`test_unmodified_review_record_is_unchanged_on_recheck`).
