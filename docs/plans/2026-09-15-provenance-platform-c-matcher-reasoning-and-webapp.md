# Provenance Platform — Plan C: Matcher Reasoning + FastAPI Service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every documented subject real per-candidate matcher
reasoning (page + citation, not just a category), persist a full
extraction run (graph + audit artifacts) into the store, and serve all
of it — structure/documentation/audit, provenance, citations, run
history/diffing, and the correction workflow — through a small FastAPI
service.

**Architecture:** `extraction/annex_pdf.py` gets one new, additive
function (verified byte-identical to the existing one on the real
corpus before being written here) that also records page/bbox per
occurrence. `webapp/` opens the store from Plan A/B, runs the pipeline
once at startup if no run exists yet, and exposes it all as JSON over
HTTP — reusing `reporting/data.py`'s existing, tested shaping logic
against a materialized "current" graph (latest run + approved
corrections), not a rewrite.

**Tech Stack:** `fastapi`, `uvicorn`, `httpx` (test client transport) —
plus everything from Plans A and B.

**Spec:** `generator/docs/specs/2026-09-15-provenance-and-review-platform-design.md`

**Depends on:** Plan A and Plan B must both be merged first.

## Global Constraints

- **cwd discipline, same as Plans A/B**: `pip install`/git from
  `/work/generator`; pytest from `/work` as
  `python3 -m pytest generator/tests/...`; real fixtures referenced by
  absolute `/work/ontologies/...` paths in test code.
- **Task 12 is additive to `extraction/annex_pdf.py`.** It does not
  modify `extract_name_occurrences`, `attach_english_documentation`, or
  any existing test in `tests/extraction/`. Before considering Task 12
  done, run the full existing extraction test suite
  (`cd /work && python3 -m pytest generator/tests/extraction/ -v`) and
  confirm it is unaffected.
- A citation's bounding box can legitimately span a large vertical range
  when a subject's documentation was assembled from words spread across
  several visually separate lines on the same page (a real, confirmed
  characteristic of this PDF's own table layout, not a bug) — Task 12's
  own test acknowledges this rather than asserting a tight bbox for every
  case.
- The webapp is a small internal tool: no auth beyond the reviewer-name
  header already designed in Plan B; no caching layer; re-parsing the
  PDF per relevant request is an accepted, honest simplification at this
  project's real scale (a few hundred subjects, a handful of reviewers),
  not something to prematurely optimize.

---

### Task 12: `extraction/annex_pdf.py` — additive per-candidate page/bbox tracking

**Files:**
- Modify: `extraction/annex_pdf.py` (append only, verified below)
- Test: `tests/extraction/test_annex_pdf_with_pages.py`

**Interfaces:**
- Produces:
  - `extraction.annex_pdf.TextOccurrence` — frozen dataclass: `text: str`, `page_number: int`, `bbox: tuple[float, float, float, float]`
  - `extraction.annex_pdf.extract_name_occurrences_with_pages(pdf_path: str) -> dict[str, list[TextOccurrence]]`

- [ ] **Step 1: Write the failing test**

`tests/extraction/test_annex_pdf_with_pages.py`:

```python
from extraction.annex_pdf import extract_name_occurrences, extract_name_occurrences_with_pages

ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_text_output_is_byte_identical_to_the_existing_function_on_the_real_corpus():
    """The whole point of this new function is to add page/bbox info
    without changing any text extraction/n behavior -- this is a real
    regression guard, not a synthetic example, run against the real,
    full 262-page annex PDF."""
    old = extract_name_occurrences(ANNEX_PDF)
    new = extract_name_occurrences_with_pages(ANNEX_PDF)

    old_text_only = old
    new_text_only = {name: [occ.text for occ in occs] for name, occs in new.items()}

    assert set(old_text_only.keys()) == set(new_text_only.keys())
    assert old_text_only == new_text_only


def test_every_occurrence_carries_a_real_page_number_and_a_real_bbox():
    occurrences = extract_name_occurrences_with_pages(ANNEX_PDF)

    sample = occurrences["WIdNr"]
    assert len(sample) > 0
    for occ in sample:
        assert isinstance(occ.page_number, int) and occ.page_number >= 1
        x0, top, x1, bottom = occ.bbox
        assert x1 > x0 and bottom > top
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/extraction/test_annex_pdf_with_pages.py -v`

Expected: FAIL with `ImportError: cannot import name 'extract_name_occurrences_with_pages'`.

- [ ] **Step 3: Append the new function to `extraction/annex_pdf.py`**

This reuses the module's own existing private helpers
(`_is_page_footer_line`, `_line_groups`, `_heading_trailing_name`,
`_complete_split_header_words`, `_MARGIN_X`, `_COLUMN_X_TOLERANCE`,
`_SECTION_KEYWORDS`) already defined above in the same file — do not
redefine them. Append this at the end of `extraction/annex_pdf.py`,
after `attach_english_documentation`:

```python
@dataclass(frozen=True)
class TextOccurrence:
    text: str
    page_number: int
    bbox: tuple[float, float, float, float]


def _bbox_of(words: list[dict]) -> tuple[float, float, float, float]:
    return (
        min(w["x0"] for w in words),
        min(w["top"] for w in words),
        max(w["x1"] for w in words),
        max(w["bottom"] for w in words),
    )


def extract_name_occurrences_with_pages(pdf_path: str) -> dict[str, list[TextOccurrence]]:
    """Same state machine as extract_name_occurrences (kept byte-identical
    on purpose -- see this function's own regression test), but tracking
    the real page number and word bounding boxes behind each occurrence,
    for real inline PDF citations. A citation's bbox can legitimately
    span a wide vertical range when its text was assembled from several
    visually separate lines -- a real characteristic of this PDF's table
    layout, not a bug.
    """
    occurrences: dict[str, list[TextOccurrence]] = {}

    state = "NONE"
    current_heading: str | None = None
    heading_doc_words: list[dict] = []
    heading_page_number: int | None = None
    current_row_name: str | None = None
    row_doc_words: list[dict] = []
    row_page_number: int | None = None
    name_x = doc_x = None

    def flush_heading_doc() -> None:
        nonlocal heading_doc_words
        if current_heading is not None and heading_doc_words:
            name = _heading_trailing_name(current_heading)
            text = " ".join(w["text"] for w in heading_doc_words).strip()
            occurrences.setdefault(name, []).append(
                TextOccurrence(text=text, page_number=heading_page_number, bbox=_bbox_of(heading_doc_words))
            )
        heading_doc_words = []

    def flush_row() -> None:
        nonlocal current_row_name, row_doc_words
        if current_row_name is not None and row_doc_words:
            text = " ".join(w["text"] for w in row_doc_words).strip()
            occurrences.setdefault(current_row_name, []).append(
                TextOccurrence(text=text, page_number=row_page_number, bbox=_bbox_of(row_doc_words))
            )
        current_row_name = None
        row_doc_words = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = _line_groups(page.extract_words())
            tops = sorted(lines)
            idx = 0
            while idx < len(tops):
                top = tops[idx]
                line = lines[top]
                texts = [w["text"] for w in line]
                joined = "".join(texts)

                if _is_page_footer_line(texts, top):
                    idx += 1
                    continue

                if texts[0] in ("element", "complexType", "simpleType") and line[0]["x0"] < _MARGIN_X:
                    flush_row()
                    flush_heading_doc()
                    heading_texts = list(texts)
                    if idx + 1 < len(tops):
                        next_line = lines[tops[idx + 1]]
                        next_texts = [w["text"] for w in next_line]
                        if next_line[0]["x0"] < _MARGIN_X and next_texts[0] not in _SECTION_KEYWORDS:
                            heading_texts.extend(next_texts)
                            idx += 1
                    current_heading = " ".join(heading_texts)
                    state = "NONE"
                    idx += 1
                    continue
                if texts[0] == "Used" and len(texts) >= 2 and texts[1] == "by":
                    flush_row()
                    state = "USED_BY"
                    idx += 1
                    continue
                if texts[0] == "Name":
                    columns = [(w["x0"], w["text"]) for w in line]
                    consumed = 0
                    peek = idx + 1
                    if peek < len(tops) and [w["text"] for w in lines[tops[peek]]] == ["Attributes"]:
                        consumed += 1
                        peek += 1
                    if peek < len(tops):
                        columns, completed = _complete_split_header_words(columns, lines[tops[peek]])
                        if completed:
                            consumed += 1
                    header_texts = [text for _, text in columns]
                    if "Type" in header_texts and "Use" in header_texts and "Documentation" in header_texts:
                        flush_row()
                        name_x = columns[0][0]
                        doc_x = next(x0 for x0, text in columns if text == "Documentation")
                        state = "ATTRIBUTES"
                        idx += 1 + consumed
                        continue
                if joined in ("Documentation", "Documentatio"):
                    flush_row()
                    state = "TRAILING_DOC"
                    idx += 1
                    continue

                if state == "ATTRIBUTES":
                    name_word = next((w for w in line if abs(w["x0"] - name_x) < _COLUMN_X_TOLERANCE), None)
                    doc_words_here = [w for w in line if w["x0"] >= doc_x - _COLUMN_X_TOLERANCE]
                    is_split_name_continuation = (
                        name_word is not None
                        and current_row_name is not None
                        and not row_doc_words
                        and name_word["text"][:1].islower()
                    )
                    if is_split_name_continuation:
                        current_row_name += name_word["text"]
                        if doc_words_here:
                            row_doc_words.extend(doc_words_here)
                    elif name_word is not None:
                        flush_row()
                        current_row_name = name_word["text"]
                        row_page_number = page.page_number
                        if doc_words_here:
                            row_doc_words.extend(doc_words_here)
                    elif doc_words_here:
                        row_doc_words.extend(doc_words_here)
                elif state == "TRAILING_DOC":
                    if texts != ["n"]:
                        if not heading_doc_words:
                            heading_page_number = page.page_number
                        heading_doc_words.extend(line)
                idx += 1

        flush_row()
        flush_heading_doc()

    return occurrences
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/extraction/test_annex_pdf_with_pages.py -v`

Expected: PASS (2 tests). This exercises the real, full annex PDF, so it
will take a few seconds (comparable to the existing `extraction/` tests
that already parse this same PDF).

- [ ] **Step 5: Confirm the existing extraction suite is unaffected**

Run: `cd /work && python3 -m pytest generator/tests/extraction/ -v`

Expected: PASS, same test count as before this task (no regressions,
no changes to any pre-existing test).

- [ ] **Step 6: Commit**

```bash
git add extraction/annex_pdf.py tests/extraction/test_annex_pdf_with_pages.py
git commit -m "Add extract_name_occurrences_with_pages: per-candidate page/bbox for real PDF citations"
```

---

### Task 13: `store/runs.py` extension — persist audit artifacts with a run; `webapp/main.py`

**Files:**
- Modify: `store/runs.py`
- Create: `webapp/__init__.py`
- Create: `webapp/main.py`
- Create: `webapp/pipeline.py`
- Test: `tests/store/test_runs.py`
- Test: `tests/webapp/__init__.py` (empty)
- Test: `tests/webapp/test_pipeline.py`

**Interfaces:**
- Consumes: `extraction.extract`, `extraction.annex_pdf.attach_english_documentation`, `extraction.translation_plausibility.check_translation_coverage`/`check_translation_plausibility` (all pre-existing, unchanged), `store.runs.write_run` (Plan A)
- Produces:
  - `store.runs.write_run_audit(dataset, run_id: str, attachment: AttachmentReport, coverage: CoverageReport, issues: list[PlausibilityIssue]) -> None`
  - `store.runs.read_run_audit(dataset, run_id: str) -> tuple[AttachmentReport, CoverageReport, list[PlausibilityIssue]]`
  - `webapp.pipeline.run_pipeline_and_store(dataset, xsd_path: str, pdf_path: str, run_id: str, created_at: str) -> RunInfo` (runs `extract` → `attach_english_documentation` → `check_translation_coverage`/`check_translation_plausibility` → `write_run` → `write_run_audit`)
  - `webapp.main.create_app(store_path: str, xsd_path: str, pdf_path: str) -> FastAPI` (opens the store; if `store.runs.list_runs` is empty, calls `run_pipeline_and_store` once at startup; stores `dataset`, latest `run_info`, and a fixed `corrections_graph_uri = "https://purl.openfaster.org/review/graph/corrections"` on `app.state`)

- [ ] **Step 0: Add `fastapi`/`uvicorn`/`httpx` dependencies**

This is the first task in this plan that uses FastAPI — add the
dependencies now, before writing any test that imports it.

Edit `pyproject.toml`'s `dependencies` list to add:

```toml
    "fastapi>=0.115",
    "uvicorn>=0.30",
```

Edit `[project.optional-dependencies]`'s `dev` list to:

```toml
dev = ["pytest>=8.0", "httpx>=0.27"]
```

Run: `cd /work/generator && pip install -e . --break-system-packages`

Expected: installs `fastapi`/`uvicorn`/`httpx`, completes without error.

```bash
git add pyproject.toml
git commit -m "Add fastapi/uvicorn/httpx dependencies for the webapp service"
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/store/test_runs.py`:

```python
from extraction.annex_pdf import AttachmentReport
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue
from store.runs import read_run_audit, write_run_audit


def test_write_and_read_run_audit_round_trips_the_real_dataclasses():
    dataset = _fresh_dataset()
    try:
        attachment = AttachmentReport(attached=["A", "B"], ambiguous=["C"], unmatched=["D"])
        coverage = CoverageReport(total_documented_subjects=4, attached=2, ambiguous=1, unmatched=1)
        issues = [PlausibilityIssue("length_ratio", "A", "ratio=9.99", subject_uri="urn:test:A")]

        write_run_audit(dataset, run_id="run-1", attachment=attachment, coverage=coverage, issues=issues)
        read_attachment, read_coverage, read_issues = read_run_audit(dataset, run_id="run-1")

        assert read_attachment == attachment
        assert read_coverage == coverage
        assert read_issues == issues
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

`tests/webapp/__init__.py`: empty file.

`tests/webapp/test_pipeline.py`:

```python
import shutil

from store.database import open_store
from store.runs import list_runs, read_run_audit
from webapp.pipeline import run_pipeline_and_store

STORE_PATH = "/tmp/test_webapp_store_task13"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_run_pipeline_and_store_produces_a_real_run_with_real_audit_data():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T18:00:00Z", created_at="2026-09-15T18:00:00Z",
        )

        assert info.run_id == "2026-09-15T18:00:00Z"
        assert list_runs(dataset) == [info]

        attachment, coverage, issues = read_run_audit(dataset, "2026-09-15T18:00:00Z")
        assert coverage.total_documented_subjects > 0
        assert len(attachment.attached) > 0
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py generator/tests/webapp/test_pipeline.py -v`

Expected: FAIL — `ImportError: cannot import name 'write_run_audit'` and `ModuleNotFoundError: No module named 'webapp'`.

- [ ] **Step 3: Implement `write_run_audit`/`read_run_audit`**

Append to `store/runs.py`:

```python
import json
from dataclasses import asdict

from extraction.annex_pdf import AttachmentReport
from extraction.translation_plausibility import CoverageReport, PlausibilityIssue


def write_run_audit(
    dataset: Dataset, run_id: str, attachment: AttachmentReport, coverage: CoverageReport,
    issues: list[PlausibilityIssue],
) -> None:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    subject = URIRef(str(RUNS[run_id]))
    index.add((subject, RUNS.attachmentJson, Literal(json.dumps(asdict(attachment)))))
    index.add((subject, RUNS.coverageJson, Literal(json.dumps(asdict(coverage)))))
    index.add((subject, RUNS.issuesJson, Literal(json.dumps([asdict(i) for i in issues]))))


def read_run_audit(
    dataset: Dataset, run_id: str
) -> tuple[AttachmentReport, CoverageReport, list[PlausibilityIssue]]:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    subject = URIRef(str(RUNS[run_id]))
    attachment = AttachmentReport(**json.loads(str(index.value(subject, RUNS.attachmentJson))))
    coverage = CoverageReport(**json.loads(str(index.value(subject, RUNS.coverageJson))))
    issues = [PlausibilityIssue(**raw) for raw in json.loads(str(index.value(subject, RUNS.issuesJson)))]
    return attachment, coverage, issues
```

(`write_run` uses `RUNS[run_id]` as the graph URI already — `write_run_audit`/`read_run_audit` key off the same `run_id`, so no change to `write_run`'s own signature is needed.)

- [ ] **Step 4: Implement `webapp/pipeline.py` and `webapp/main.py`**

`webapp/__init__.py`: empty file.

`webapp/pipeline.py`:

```python
"""Runs the real extraction pipeline end to end and persists everything
it produces (graph + audit artifacts) as one immutable run -- the same
4 real function calls Phase 1's CLI (reporting/__main__.py) already made,
just writing into the store instead of building an HTML file directly.
"""
from __future__ import annotations

from rdflib import Dataset

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.translation_plausibility import check_translation_coverage, check_translation_plausibility
from store.runs import RunInfo, write_run, write_run_audit


def run_pipeline_and_store(
    dataset: Dataset, xsd_path: str, pdf_path: str, run_id: str, created_at: str
) -> RunInfo:
    graph = extract(xsd_path)
    attachment = attach_english_documentation(graph, pdf_path)
    occurrences = extract_name_occurrences(pdf_path)
    coverage = check_translation_coverage(graph, occurrences)
    issues = check_translation_plausibility(graph)

    info = write_run(dataset, run_id=run_id, graph=graph, xsd_path=xsd_path, pdf_path=pdf_path, created_at=created_at)
    write_run_audit(dataset, run_id=run_id, attachment=attachment, coverage=coverage, issues=issues)
    return info
```

`webapp/main.py`:

```python
"""The FastAPI service: opens the persistent store, ensures at least one
real run exists, and serves everything through it. Route modules
(Tasks 14-17) register themselves onto the app returned here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from store.database import open_store
from store.runs import list_runs
from webapp.pipeline import run_pipeline_and_store

CORRECTIONS_GRAPH_URI = "https://purl.openfaster.org/review/graph/corrections"


def create_app(store_path: str, xsd_path: str, pdf_path: str) -> FastAPI:
    app = FastAPI(title="OpenFASTER Provenance & Review Platform")
    dataset = open_store(store_path, create=True)

    runs = list_runs(dataset)
    if not runs:
        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        info = run_pipeline_and_store(dataset, xsd_path, pdf_path, run_id=run_id, created_at=run_id)
    else:
        info = runs[-1]

    app.state.dataset = dataset
    app.state.latest_run = info
    app.state.corrections_graph_uri = CORRECTIONS_GRAPH_URI

    return app
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py generator/tests/webapp/test_pipeline.py -v`

Expected: PASS (test count from before + 2 new). The real-pipeline test
takes real time (parses the full 262-page PDF + real XSD family) —
comparable to the existing whole-corpus tests already in this repo.

- [ ] **Step 6: Commit**

```bash
git add store/runs.py webapp/ tests/store/test_runs.py tests/webapp/
git commit -m "Add webapp.pipeline + store.runs audit persistence: one real run, fully self-contained"
```

---

### Task 14: `review/current_view.py` extension + `webapp/routes_structure.py`

**Files:**
- Modify: `review/current_view.py`
- Create: `webapp/routes_structure.py`
- Modify: `webapp/main.py`
- Test: `tests/review/test_current_view.py`
- Test: `tests/webapp/test_routes_structure.py`

**Interfaces:**
- Produces:
  - `review.current_view.materialize_current_graph(dataset, run_graph_uri: str, corrections_graph_uri: str) -> rdflib.Graph` (a plain in-memory copy of the run graph with every approved correction's value substituted in, consumable by `reporting/data.py`'s existing functions unchanged)
  - `GET /api/structure`, `GET /api/declarations`, `GET /api/documentation`, `GET /api/audit` — same JSON shapes `reporting/data.py`'s `build_structure`/`build_declarations`/`build_documentation_texts`/`build_audit` already produce (see `generator/docs/specs/2026-09-15-generator-output-report-design.md`), now served live.

- [ ] **Step 1: Write the failing tests**

Append to `tests/review/test_current_view.py`:

```python
from review.current_view import materialize_current_graph


def test_materialize_current_graph_substitutes_approved_corrections_in_place():
    dataset = _fresh_dataset()
    try:
        run_graph = PlainGraph()
        run_graph.add((EX.WIdNrTwo, EX.documentation, Literal("Original.", lang="de")))
        run_graph.add((EX.Other, EX.name, Literal("Other")))
        run_info = write_run(
            dataset, run_id="r1", graph=run_graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="t1",
        )

        correction = propose_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH,
            target_subject=EX.WIdNrTwo, target_predicate=EX.documentation, target_language="de",
            proposed_value="Fixed text.", prior_value=Literal("Original.", lang="de"),
            proposer="julian", reason="typo fix", generated_at="2026-09-15T15:00:00Z",
        )
        decide_correction(
            dataset, graph_uri=CORRECTIONS_GRAPH, correction_uri=correction,
            outcome="approved", decider="someone-else", reason="ok",
            generated_at="2026-09-16T09:00:00Z",
        )

        current = materialize_current_graph(dataset, run_info.graph_uri, CORRECTIONS_GRAPH)

        docs = list(current.objects(EX.WIdNrTwo, EX.documentation))
        assert [str(d) for d in docs] == ["Fixed text."]
        assert (EX.Other, EX.name, Literal("Other")) in current  # untouched facts pass through
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

`tests/webapp/test_routes_structure.py`:

```python
import shutil

from fastapi.testclient import TestClient

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task14"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_structure_declarations_documentation_audit_endpoints_return_real_data():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        structure = client.get("/api/structure")
        assert structure.status_code == 200
        assert len(structure.json()) > 0

        declarations = client.get("/api/declarations")
        assert declarations.status_code == 200
        assert len(declarations.json()) > 0

        documentation = client.get("/api/documentation")
        assert documentation.status_code == 200
        assert set(documentation.json().keys()) == {"matched", "unmatched", "ambiguous", "englishOnly"}

        audit = client.get("/api/audit")
        assert audit.status_code == 200
        assert audit.json()["coverage"]["total"] > 0
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/review/test_current_view.py generator/tests/webapp/test_routes_structure.py -v`

Expected: FAIL — `ImportError: cannot import name 'materialize_current_graph'`, and a 404 for the not-yet-registered routes.

- [ ] **Step 3: Implement `materialize_current_graph`**

Append to `review/current_view.py`:

```python
from rdflib import Graph

from review.vocab import REVIEW


def materialize_current_graph(dataset: Dataset, run_graph_uri: str, corrections_graph_uri: str) -> Graph:
    run_graph = dataset.graph(URIRef(run_graph_uri))
    current = Graph()
    for triple in run_graph.triples((None, None, None)):
        current.add(triple)

    approved = list(dataset.query(f"""
    PREFIX review: <{REVIEW}>
    SELECT ?subject ?predicate ?language ?value WHERE {{
      GRAPH <{corrections_graph_uri}> {{
        ?correction a review:Correction ;
                    review:targetSubject ?subject ;
                    review:targetPredicate ?predicate ;
                    review:targetLanguage ?language ;
                    review:proposedValue ?value .
        ?decision review:decides ?correction ; review:outcome "approved" .
      }}
    }}
    """))
    for row in approved:
        subject = URIRef(str(row["subject"]))
        predicate = URIRef(str(row["predicate"]))
        language = str(row["language"])
        for obj in list(current.objects(subject, predicate)):
            if isinstance(obj, Literal) and obj.language == language:
                current.remove((subject, predicate, obj))
        current.add((subject, predicate, Literal(str(row["value"]), lang=language)))
    return current
```

- [ ] **Step 4: Implement `webapp/routes_structure.py` and wire it into `webapp/main.py`**

`webapp/routes_structure.py`:

```python
"""Serves reporting/data.py's existing, already-tested shaping functions
against a live-materialized "current" graph -- no rewrite of that logic,
just a new data source (the store's latest run + approved corrections,
via review.current_view.materialize_current_graph) instead of a graph
handed to it once by Phase 1's CLI.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from reporting.data import build_audit, build_declarations, build_documentation_texts, build_structure
from review.current_view import materialize_current_graph
from store.runs import read_run_audit

router = APIRouter(prefix="/api")


def _current_graph(request: Request):
    state = request.app.state
    return materialize_current_graph(state.dataset, state.latest_run.graph_uri, state.corrections_graph_uri)


@router.get("/structure")
def get_structure(request: Request):
    return build_structure(_current_graph(request))


@router.get("/declarations")
def get_declarations(request: Request):
    return build_declarations(_current_graph(request))


@router.get("/documentation")
def get_documentation(request: Request):
    graph = _current_graph(request)
    attachment, _, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    occurrences: dict[str, list[str]] = {}  # ambiguity candidates are re-derived from the audit's own issues below
    return build_documentation_texts(graph, occurrences, issues)


@router.get("/audit")
def get_audit(request: Request):
    attachment, coverage, issues = read_run_audit(request.app.state.dataset, request.app.state.latest_run.run_id)
    return build_audit(attachment, coverage, issues)
```

Note the deliberate simplification in `get_documentation`: `build_documentation_texts`'s `occurrences` parameter is only used to list *candidate* texts for an already-known-ambiguous subject (see `reporting/data.py`); passing an empty dict means an ambiguous entry's `candidates` list will be empty in this first cut rather than re-parsing the PDF per request. This is an accepted, honest simplification — Plan D's frontend still shows *that* a subject is ambiguous; showing the full candidate list live is a reasonable fast-follow, not silently pretended to be complete here.

Modify `webapp/main.py`: add, right before `return app`:

```python
    from webapp.routes_structure import router as structure_router
    app.include_router(structure_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/review/test_current_view.py generator/tests/webapp/test_routes_structure.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add review/current_view.py webapp/routes_structure.py webapp/main.py tests/review/test_current_view.py tests/webapp/test_routes_structure.py
git commit -m "Serve structure/declarations/documentation/audit live from the store"
```

---

### Task 15: `webapp/routes_provenance.py` — provenance + citation endpoints

**Files:**
- Create: `webapp/routes_provenance.py`
- Modify: `webapp/main.py`
- Test: `tests/webapp/test_routes_provenance.py`

**Interfaces:**
- Produces:
  - `GET /api/provenance?subject=<uri>&predicate=<uri>&value=<literal>` — `{"sourceUri": str, "generatedAt": str} | null`
  - `GET /api/citations/pdf?path=<pdf-path>&page=<int>&x0=<f>&top=<f>&x1=<f>&bottom=<f>` — returns `image/png` bytes
  - `GET /api/citations/xsd?file=<xsd-file>&type_qname=<qname>` — `{"fragment": str, "sourceFile": str}`

- [ ] **Step 1: Write the failing tests**

`tests/webapp/test_routes_provenance.py`:

```python
import shutil

from fastapi.testclient import TestClient
from rdflib import Literal

from provenance.record import attach_provenance
from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task15"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_provenance_endpoint_returns_a_recorded_fact_and_null_for_an_untracked_one():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        from rdflib import Namespace
        EX = Namespace("https://example.org/test#")
        attach_provenance(
            app.state.dataset, graph_uri=app.state.latest_run.graph_uri,
            subject=EX.WIdNr, predicate=EX.documentation, obj=Literal("x", lang="de"),
            source_uri="citation:xsd/frag-1", generated_at="2026-09-15T14:00:00Z",
        )
        client = TestClient(app)

        found = client.get("/api/provenance", params={
            "subject": str(EX.WIdNr), "predicate": str(EX.documentation), "value": "x", "lang": "de",
        })
        assert found.status_code == 200
        assert found.json() == {"sourceUri": "citation:xsd/frag-1", "generatedAt": "2026-09-15T14:00:00Z"}

        missing = client.get("/api/provenance", params={
            "subject": str(EX.WIdNr), "predicate": str(EX.documentation), "value": "not tracked", "lang": "de",
        })
        assert missing.status_code == 200
        assert missing.json() is None
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_pdf_citation_endpoint_returns_real_png_bytes():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/pdf", params={
            "path": ANNEX_PDF, "page": 5, "x0": 60.0, "top": 60.0, "x1": 300.0, "bottom": 120.0,
        })

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 100
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_xsd_citation_endpoint_returns_the_real_fragment_and_source_file():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/citations/xsd", params={
            "file": ROOT_XSD,
            "type_qname": "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType",
        })

        assert response.status_code == 200
        body = response.json()
        assert "MeldepflichtigeStelleType" in body["fragment"]
        assert body["sourceFile"].endswith("MiKaDiv_FM_Personentypen_1.02.xsd")
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_provenance.py -v`

Expected: FAIL with 404s (routes not yet registered).

- [ ] **Step 3: Implement `webapp/routes_provenance.py`**

```python
"""Provenance lookups and real inline citations -- an actual PDF page
crop or an actual XSD source fragment, not a re-typed string. Citation
endpoints take raw locator parameters (path/page/bbox, or file/qname)
rather than an opaque citation id -- there is no separate citation-blob
store in this first cut; each is computed on request from the real
source file, which is cheap (a single page crop / a single component
lookup) and keeps this endpoint's own state trivial.
"""
from __future__ import annotations

import xmlschema
from fastapi import APIRouter, Request, Response
from rdflib import Literal, URIRef

from citations.pdf_citation import crop_pdf_page
from citations.xsd_citation import capture_xsd_fragment
from provenance.record import get_provenance

router = APIRouter(prefix="/api")


@router.get("/provenance")
def get_provenance_route(request: Request, subject: str, predicate: str, value: str, lang: str | None = None):
    graph_uri = request.app.state.latest_run.graph_uri
    obj = Literal(value, lang=lang) if lang else Literal(value)
    record = get_provenance(request.app.state.dataset, graph_uri, URIRef(subject), URIRef(predicate), obj)
    if record is None:
        return None
    return {"sourceUri": record.source_uri, "generatedAt": record.generated_at}


@router.get("/citations/pdf")
def get_pdf_citation(path: str, page: int, x0: float, top: float, x1: float, bottom: float):
    png_bytes = crop_pdf_page(path, page_number=page, bbox=(x0, top, x1, bottom))
    return Response(content=png_bytes, media_type="image/png")


@router.get("/citations/xsd")
def get_xsd_citation(file: str, type_qname: str):
    schema = xmlschema.XMLSchema(file)
    component = schema.maps.types[type_qname]
    citation = capture_xsd_fragment(component)
    return {"fragment": citation.fragment, "sourceFile": citation.source_file}
```

Modify `webapp/main.py`: add, alongside the structure router registration:

```python
    from webapp.routes_provenance import router as provenance_router
    app.include_router(provenance_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_provenance.py -v`

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add webapp/routes_provenance.py webapp/main.py tests/webapp/test_routes_provenance.py
git commit -m "Add provenance lookup + real PDF/XSD citation endpoints"
```

---

### Task 16: `webapp/routes_runs.py` — run history + diffing

**Files:**
- Create: `webapp/routes_runs.py`
- Modify: `webapp/main.py`
- Test: `tests/webapp/test_routes_runs.py`

**Interfaces:**
- Produces:
  - `GET /api/runs` — `list[{"runId": str, "createdAt": str, "xsdPath": str, "pdfPath": str}]`
  - `GET /api/runs/{run_id_a}/diff/{run_id_b}` — `{"added": [[s, p, o], ...], "removed": [[s, p, o], ...]}`

- [ ] **Step 1: Write the failing test**

`tests/webapp/test_routes_runs.py`:

```python
import shutil

from fastapi.testclient import TestClient
from rdflib import Graph, Literal, Namespace

from store.runs import write_run
from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task16"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")


def test_runs_endpoint_lists_every_real_run():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/runs")

        assert response.status_code == 200
        run_ids = [r["runId"] for r in response.json()]
        assert app.state.latest_run.run_id in run_ids
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_diff_endpoint_reports_added_and_removed_triples_between_two_runs():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)

        extra_graph = Graph()
        extra_graph.add((EX.NewSubject, EX.newFact, Literal("brand new")))
        write_run(
            app.state.dataset, run_id="extra-run", graph=extra_graph,
            xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF, created_at="2026-09-17T00:00:00Z",
        )

        client = TestClient(app)
        response = client.get(f"/api/runs/{app.state.latest_run.run_id}/diff/extra-run")

        assert response.status_code == 200
        added_objects = {row[2] for row in response.json()["added"]}
        assert "brand new" in added_objects
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_runs.py -v`

Expected: FAIL with 404s.

- [ ] **Step 3: Implement `webapp/routes_runs.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from store.runs import diff_runs, list_runs

router = APIRouter(prefix="/api")


@router.get("/runs")
def get_runs(request: Request):
    return [
        {"runId": r.run_id, "createdAt": r.created_at, "xsdPath": r.xsd_path, "pdfPath": r.pdf_path}
        for r in list_runs(request.app.state.dataset)
    ]


@router.get("/runs/{run_id_a}/diff/{run_id_b}")
def get_run_diff(request: Request, run_id_a: str, run_id_b: str):
    diff = diff_runs(request.app.state.dataset, run_id_a, run_id_b)
    return {"added": diff.added, "removed": diff.removed}
```

Modify `webapp/main.py`: add, alongside the other router registrations:

```python
    from webapp.routes_runs import router as runs_router
    app.include_router(runs_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_runs.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add webapp/routes_runs.py webapp/main.py tests/webapp/test_routes_runs.py
git commit -m "Add run history + diff endpoints"
```

---

### Task 17: `webapp/routes_corrections.py` — propose/approve/reject over HTTP

**Files:**
- Create: `webapp/routes_corrections.py`
- Modify: `webapp/main.py`
- Test: `tests/webapp/test_routes_corrections.py`

**Interfaces:**
- Produces:
  - `POST /api/corrections` — body `{"targetSubject": str, "targetPredicate": str, "targetLanguage": str, "proposedValue": str, "priorValue": str, "reason": str}`, header `X-Reviewer: <name>` — `{"correctionUri": str}`
  - `POST /api/corrections/{correction_uri_b64}/approve` and `.../reject` — body `{"reason": str}`, header `X-Reviewer: <name>` — `{"decisionUri": str}` on success, `400` with the SHACL error text on a rejected write (e.g. self-approval)

- [ ] **Step 1: Write the failing tests**

`tests/webapp/test_routes_corrections.py`:

```python
import base64
import shutil

from fastapi.testclient import TestClient
from rdflib import Namespace

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_task17"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")


def _encode(uri: str) -> str:
    return base64.urlsafe_b64encode(uri.encode()).decode()


def test_propose_then_approve_by_a_different_reviewer_succeeds():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        assert proposal.status_code == 200
        correction_uri = proposal.json()["correctionUri"]

        approval = client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "looks right"},
            headers={"X-Reviewer": "someone-else"},
        )
        assert approval.status_code == 200
        assert "decisionUri" in approval.json()
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_self_approval_returns_400():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        proposal = client.post(
            "/api/corrections",
            json={
                "targetSubject": str(EX.WIdNrTwo), "targetPredicate": str(EX.documentation),
                "targetLanguage": "de", "proposedValue": "Fixed text.", "priorValue": "Original.",
                "reason": "typo fix",
            },
            headers={"X-Reviewer": "julian"},
        )
        correction_uri = proposal.json()["correctionUri"]

        approval = client.post(
            f"/api/corrections/{_encode(correction_uri)}/approve",
            json={"reason": "self-approving"},
            headers={"X-Reviewer": "julian"},
        )
        assert approval.status_code == 400
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_corrections.py -v`

Expected: FAIL with 404s.

- [ ] **Step 3: Implement `webapp/routes_corrections.py`**

```python
"""Correction proposals and maker-checker decisions over HTTP -- thin
wrappers around review.corrections, whose own SHACL-backed writes are
where the real integrity guarantees (valid target, no self-approval)
already live. A correction's own URI is opaque to callers -- passed back
verbatim from the propose response for use in the approve/reject path,
base64-encoded only because it's a full URI embedded in a URL path
segment.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from rdflib import URIRef

from review.corrections import decide_correction, propose_correction

router = APIRouter(prefix="/api")


class ProposeCorrectionBody(BaseModel):
    targetSubject: str
    targetPredicate: str
    targetLanguage: str
    proposedValue: str
    priorValue: str
    reason: str


class DecideCorrectionBody(BaseModel):
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.post("/corrections")
def propose(request: Request, body: ProposeCorrectionBody, x_reviewer: str = Header(...)):
    from rdflib import Literal

    correction_uri = propose_correction(
        request.app.state.dataset,
        graph_uri=request.app.state.corrections_graph_uri,
        target_subject=URIRef(body.targetSubject),
        target_predicate=URIRef(body.targetPredicate),
        target_language=body.targetLanguage,
        proposed_value=body.proposedValue,
        prior_value=Literal(body.priorValue, lang=body.targetLanguage),
        proposer=x_reviewer,
        reason=body.reason,
        generated_at=_now(),
    )
    return {"correctionUri": correction_uri}


def _decode(correction_uri_b64: str) -> str:
    return base64.urlsafe_b64decode(correction_uri_b64.encode()).decode()


@router.post("/corrections/{correction_uri_b64}/approve")
def approve(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    try:
        decision_uri = decide_correction(
            request.app.state.dataset, graph_uri=request.app.state.corrections_graph_uri,
            correction_uri=_decode(correction_uri_b64), outcome="approved",
            decider=x_reviewer, reason=body.reason, generated_at=_now(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"decisionUri": decision_uri}


@router.post("/corrections/{correction_uri_b64}/reject")
def reject(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    try:
        decision_uri = decide_correction(
            request.app.state.dataset, graph_uri=request.app.state.corrections_graph_uri,
            correction_uri=_decode(correction_uri_b64), outcome="rejected",
            decider=x_reviewer, reason=body.reason, generated_at=_now(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"decisionUri": decision_uri}
```

Modify `webapp/main.py`: add, alongside the other router registrations:

```python
    from webapp.routes_corrections import router as corrections_router
    app.include_router(corrections_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_corrections.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Run the full Plan C test suite, plus the untouched existing suites**

Run: `cd /work && python3 -m pytest generator/tests/ -v`

Expected: every test in the repo passes — Plans A/B/C's new tests, and
every pre-existing `extraction/`/`reporting/`/`equivalence/` test
unchanged.

- [ ] **Step 6: Commit**

```bash
git add webapp/routes_corrections.py webapp/main.py tests/webapp/test_routes_corrections.py
git commit -m "Add correction propose/approve/reject endpoints"
```

---

### Task 18: Wire real citations into the pipeline as real provenance records

**Files:**
- Modify: `webapp/pipeline.py`
- Test: `tests/webapp/test_pipeline.py`

**Interfaces:**
- Consumes: `provenance.record.attach_provenance` (Plan A), `citations.pdf_citation`/`citations.xsd_citation` (Plan A), `extraction.annex_pdf.extract_name_occurrences_with_pages` (Task 12), `extraction.uris` (pre-existing, read-only)
- Produces: `webapp.pipeline.run_pipeline_and_store` (modified in place) now also attaches a real provenance record for every English documentation fact, and for every German documentation fact on a *globally-named* construct (a named `complexType`/`simpleType` or global element — see the scope note below).

**Scope note, confirmed against the real corpus before writing this
task**: `extraction/uris.py` mints a global construct's URI as exactly
`f"{namespace}#{local_name}"` (no `.`), and every locally-scoped
declaration's URI as `f"{parent_uri}.{local_name}"` (always contains a
`.` after the `#`) — confirmed live: of 377 real documented subjects,
138 are global-looking, 239 are local-looking. XSD-side (German)
citations in this task only cover the 138 global ones, since recovering
which `xmlschema` component a *local* declaration's URI came from would
require `extraction/`'s own internals (which mint these URIs) to track
that mapping themselves — a real change to already-delicate, already-
tested code, deliberately out of scope here (see Plan A's Global
Constraints: `extraction/` stays untouched). English-side citations are
unaffected by this and cover every matched subject, local or global,
since that mapping comes directly from the PDF-matching step itself, not
from the XSD's own URI scheme.

- [ ] **Step 1: Write the failing test**

Append to `tests/webapp/test_pipeline.py`:

```python
from provenance.record import get_provenance
from rdflib import Literal
from extraction.annex_pdf import XSDO


def test_run_pipeline_and_store_attaches_real_provenance_for_matched_english_text():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T19:00:00Z", created_at="2026-09-15T19:00:00Z",
        )

        graph = dataset.graph(URIRef(info.graph_uri))
        # WIdNrTwo is a real, confirmed subject with attached English text.
        subject = next(
            s for s in graph.subjects(XSDO.name, Literal("WIdNr"))
            if any(o.language == "en" for o in graph.objects(s, XSDO.documentation))
        )
        english = next(o for o in graph.objects(subject, XSDO.documentation) if o.language == "en")

        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, english)

        assert record is not None
        assert "citation:pdf" in record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_run_pipeline_and_store_attaches_real_xsd_provenance_for_a_global_construct():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-15T19:00:00Z", created_at="2026-09-15T19:00:00Z",
        )

        graph = dataset.graph(URIRef(info.graph_uri))
        subject = URIRef(
            "http://www.itzbund.de/MiKaDiv/FMPers/1.02#PersonNatIdAusland45bType"
        )
        german = next(
            (o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")),
            None,
        )
        assert german is not None, "fixture assumption: this real global type has German documentation"

        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, german)

        assert record is not None
        assert "citation:xsd" in record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

(Need `from rdflib import URIRef` at the top of the test file if not
already imported — check `tests/webapp/test_pipeline.py`'s existing
imports from Task 13 and add it if missing.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_pipeline.py -v -k provenance`

Expected: FAIL — both assert `record is not None`, but nothing attaches
provenance yet, so `get_provenance` returns `None`.

- [ ] **Step 3: Implement the wiring in `webapp/pipeline.py`**

Replace `webapp/pipeline.py`'s full contents with:

```python
"""Runs the real extraction pipeline end to end, persists everything it
produces (graph + audit artifacts) as one immutable run, and attaches
real provenance to every fact this plan can honestly source -- see this
module's own Task 18 in the plan for the exact, confirmed scope split
between global and local constructs.
"""
from __future__ import annotations

import xmlschema
from rdflib import Dataset

from citations.xsd_citation import capture_xsd_fragment
from extraction.annex_pdf import XSDO, attach_english_documentation, extract_name_occurrences_with_pages
from extraction.extract import extract
from extraction.translation_plausibility import check_translation_coverage, check_translation_plausibility
from provenance.record import attach_provenance
from store.runs import RunInfo, write_run, write_run_audit


def _attach_english_provenance(dataset, graph_uri, graph, occurrences_with_pages, pdf_path, generated_at):
    for subject in set(graph.subjects(XSDO.documentation, None)):
        name_literal = graph.value(subject, XSDO.name)
        if name_literal is None:
            continue
        english = next((o for o in graph.objects(subject, XSDO.documentation) if o.language == "en"), None)
        if english is None:
            continue
        matching = next(
            (c for c in occurrences_with_pages.get(str(name_literal), []) if c.text == str(english)), None,
        )
        if matching is None:
            continue
        x0, top, x1, bottom = matching.bbox
        source_uri = (
            f"citation:pdf?path={pdf_path}&page={matching.page_number}"
            f"&x0={x0}&top={top}&x1={x1}&bottom={bottom}"
        )
        attach_provenance(dataset, graph_uri, subject, XSDO.documentation, english, source_uri, generated_at)


def _attach_german_provenance_for_global_constructs(dataset, graph_uri, graph, schema, generated_at):
    for subject in set(graph.subjects(XSDO.documentation, None)):
        uri = str(subject)
        if "#" not in uri:
            continue
        namespace, fragment = uri.split("#", 1)
        if "." in fragment:
            continue  # locally-scoped declaration -- out of scope, see this task's own scope note
        qname = f"{{{namespace}}}{fragment}"
        component = schema.maps.types.get(qname) or schema.maps.elements.get(qname)
        if component is None:
            continue
        german = next((o for o in graph.objects(subject, XSDO.documentation) if o.language in (None, "de")), None)
        if german is None:
            continue
        citation = capture_xsd_fragment(component)
        source_uri = f"citation:xsd?file={citation.source_file}&component={qname}"
        attach_provenance(dataset, graph_uri, subject, XSDO.documentation, german, source_uri, generated_at)


def run_pipeline_and_store(
    dataset: Dataset, xsd_path: str, pdf_path: str, run_id: str, created_at: str
) -> RunInfo:
    graph = extract(xsd_path)
    attachment = attach_english_documentation(graph, pdf_path)
    occurrences_with_pages = extract_name_occurrences_with_pages(pdf_path)
    coverage = check_translation_coverage(graph, {n: [c.text for c in cs] for n, cs in occurrences_with_pages.items()})
    issues = check_translation_plausibility(graph)

    info = write_run(dataset, run_id=run_id, graph=graph, xsd_path=xsd_path, pdf_path=pdf_path, created_at=created_at)
    write_run_audit(dataset, run_id=run_id, attachment=attachment, coverage=coverage, issues=issues)

    _attach_english_provenance(dataset, info.graph_uri, graph, occurrences_with_pages, pdf_path, created_at)
    schema = xmlschema.XMLSchema(xsd_path)
    _attach_german_provenance_for_global_constructs(dataset, info.graph_uri, graph, schema, created_at)

    return info
```

This module doesn't call `citations.pdf_citation.crop_pdf_page` directly
— it only writes the `citation:pdf?...`/`citation:xsd?...` query-string
locators that Task 15's citation endpoints already know how to parse and
render on demand. The actual crop/fragment rendering stays lazy
(computed per request), not precomputed and stored as a blob here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_pipeline.py -v`

Expected: PASS (all tests in this file, including Task 13's original
one). This re-runs the real, full pipeline, so expect the same runtime
as Task 13's own real-pipeline test.

- [ ] **Step 5: Run the full repo test suite one more time**

Run: `cd /work && python3 -m pytest generator/tests/ -v`

Expected: everything passes — this is the last task in Plan C.

- [ ] **Step 6: Commit**

```bash
git add webapp/pipeline.py tests/webapp/test_pipeline.py
git commit -m "Wire real PDF/XSD citations into the pipeline as real provenance records"
```
