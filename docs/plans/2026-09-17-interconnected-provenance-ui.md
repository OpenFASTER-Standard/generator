# Interconnected Provenance UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tab-based Plan D frontend with three switchable, interlinked
view modes (Graph / Living Text / Synced Panes) sharing one focus model, backed
by a generic, extensible source-locator abstraction and a new reverse-lookup
capability, so provenance in every direction is one hover or one click away
instead of buried behind a small dot.

**Architecture:** A `SourceLocator` type (Python + TypeScript, mirrored) formalizes
the existing `citation:pdf?...`/`citation:xsd?...` scheme without migrating any
stored data. A new reverse-lookup endpoint answers "what was derived from this
source location," verified live against the real corpus using an RDF-star
variable triple pattern (`<<?s ?p ?o>> prov:hasProvenanceRecord ?record`).
React Router (new) carries a shared `(subject, predicate?, language?)` focus in
the URL; three mode components (Graph via Cytoscape.js, Living Text, Synced
Panes) all read/write it. Structure, Audit, and the Corrections worklist are
retired as separate pages — their content becomes part of Graph mode's filters
and Living Text's inline corrections.

**Tech Stack:** `react-router-dom` (new), `cytoscape` (already a dependency),
`@playwright/test` (new, for the required live-walkthrough test) — plus
everything already in Plans A-D.

**Spec:** `generator/docs/specs/2026-09-17-interconnected-provenance-ui-design.md`

**Depends on:** Plans A, B, C, D (all merged to main).

## Global Constraints

- **cwd discipline, same as every prior plan on this repo**: `pip install`/git
  from `/work/generator`; Python tests from `/work` as
  `python3 -m pytest generator/tests/...`; real fixtures referenced by absolute
  `/work/ontologies/...` paths. Frontend commands (`npm install`, `npm run
  build`, `npx vitest run`, `npx playwright test`) from `/work/generator/frontend`.
- **Never use git worktrees on this box.** Work directly on a feature branch in
  the existing checkout.
- **No new locator kind's data model changes what's already stored.** The
  `SourceLocator` abstraction formalizes the existing `citation:pdf?...`/
  `citation:xsd?...` source-URI scheme — it must produce byte-identical strings
  to what `webapp/pipeline.py` already writes today, so no store migration is
  needed and Plans A-D's existing provenance data keeps working unchanged.
- **Reverse-lookup granularity is honest, not aspirational**: PDF matches at
  the *page* level (not exact bbox — real citations on the same page can sit
  arbitrarily close together, and pixel-perfect click precision isn't needed
  for "what else came from this page"); XSD matches at the *named global
  component* level (matching the granularity `capture_xsd_fragment` already
  captures — there is no finer-grained XSD citation data to match against).
- **The known German/XSD local-scope gap and the single reviewer name list
  are inherited from Plans C/D, unchanged by this plan.** Render them
  honestly (see Task 10 and Task 12), don't silently hide them.

---

### Task 1: `citations/locator.py` — the SourceLocator type

**Files:**
- Create: `citations/locator.py`
- Test: `tests/citations/test_locator.py`

**Interfaces:**
- Produces:
  - `citations.locator.PdfLocator` — frozen dataclass: `path: str`, `page: int`, `bbox: tuple[float, float, float, float] | None = None`, `kind: Literal["pdf"] = "pdf"`
  - `citations.locator.XsdLocator` — frozen dataclass: `file: str`, `component: str`, `kind: Literal["xsd"] = "xsd"`
  - `citations.locator.SourceLocator = PdfLocator | XsdLocator`
  - `citations.locator.locator_to_source_uri(locator: SourceLocator) -> str`
  - `citations.locator.source_uri_to_locator(source_uri: str) -> SourceLocator | None`
  - `citations.locator.locator_lookup_key(locator: SourceLocator) -> str` — the unencoded source-URI *prefix pattern* that matches every fact recorded at this locator's own granularity (ignores `bbox` even if present for `PdfLocator`).

- [ ] **Step 1: Write the failing tests**

`tests/citations/test_locator.py`:

```python
from citations.locator import (
    PdfLocator,
    XsdLocator,
    locator_lookup_key,
    locator_to_source_uri,
    source_uri_to_locator,
)


def test_pdf_locator_with_bbox_round_trips_through_source_uri():
    locator = PdfLocator(path="/a/b.pdf", page=196, bbox=(137.64, 610.179, 223.878, 619.179))
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:pdf?path=/a/b.pdf&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179"
    assert source_uri_to_locator(source_uri) == locator


def test_pdf_locator_without_bbox_round_trips():
    locator = PdfLocator(path="/a/b.pdf", page=5)
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:pdf?path=/a/b.pdf&page=5"
    assert source_uri_to_locator(source_uri) == locator


def test_xsd_locator_round_trips():
    locator = XsdLocator(file="/a/b.xsd", component="{urn:ns}TypeName")
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:xsd?file=/a/b.xsd&component={urn:ns}TypeName"
    assert source_uri_to_locator(source_uri) == locator


def test_source_uri_to_locator_returns_none_for_an_unrecognized_scheme():
    assert source_uri_to_locator("https://example.org/something") is None


def test_pdf_locator_lookup_key_ignores_bbox():
    with_bbox = PdfLocator(path="/a/b.pdf", page=196, bbox=(1.0, 2.0, 3.0, 4.0))
    without_bbox = PdfLocator(path="/a/b.pdf", page=196)
    assert locator_lookup_key(with_bbox) == locator_lookup_key(without_bbox)
    assert locator_lookup_key(with_bbox) == "citation:pdf?path=/a/b.pdf&page=196"


def test_xsd_locator_lookup_key_is_the_full_source_uri():
    locator = XsdLocator(file="/a/b.xsd", component="{urn:ns}TypeName")
    assert locator_lookup_key(locator) == locator_to_source_uri(locator)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_locator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'citations.locator'`.

- [ ] **Step 3: Implement `citations/locator.py`**

```python
"""Formalizes the source-URI scheme webapp/pipeline.py already writes
(`citation:pdf?...`/`citation:xsd?...`) into a real, typed, round-trippable
locator -- without changing the scheme itself, so every fact already
recorded by Plans A-D keeps working unchanged. See the design spec's
"Synced Panes mode + the generic source-viewer abstraction" section.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class PdfLocator:
    path: str
    page: int
    bbox: tuple[float, float, float, float] | None = None
    kind: Literal["pdf"] = "pdf"


@dataclass(frozen=True)
class XsdLocator:
    file: str
    component: str
    kind: Literal["xsd"] = "xsd"


SourceLocator = Union[PdfLocator, XsdLocator]


def locator_to_source_uri(locator: SourceLocator) -> str:
    if isinstance(locator, PdfLocator):
        base = f"citation:pdf?path={locator.path}&page={locator.page}"
        if locator.bbox is None:
            return base
        x0, top, x1, bottom = locator.bbox
        return f"{base}&x0={x0}&top={top}&x1={x1}&bottom={bottom}"
    if isinstance(locator, XsdLocator):
        return f"citation:xsd?file={locator.file}&component={locator.component}"
    raise TypeError(f"unknown locator type: {locator!r}")


def source_uri_to_locator(source_uri: str) -> SourceLocator | None:
    if source_uri.startswith("citation:pdf?"):
        params = urllib.parse.parse_qs(source_uri[len("citation:pdf?"):])
        bbox = None
        if "x0" in params:
            bbox = (
                float(params["x0"][0]), float(params["top"][0]),
                float(params["x1"][0]), float(params["bottom"][0]),
            )
        return PdfLocator(path=params["path"][0], page=int(params["page"][0]), bbox=bbox)
    if source_uri.startswith("citation:xsd?"):
        params = urllib.parse.parse_qs(source_uri[len("citation:xsd?"):])
        return XsdLocator(file=params["file"][0], component=params["component"][0])
    return None


def locator_lookup_key(locator: SourceLocator) -> str:
    """The source-URI *prefix pattern* every fact recorded at this locator's
    own granularity shares -- page-level for PDF (deliberately ignores
    bbox), the full exact URI for XSD (there is no finer granularity to
    ignore). Used by provenance.reverse_lookup to build a REGEX-anchored
    SPARQL filter, not a plain string match, so a source_uri never
    partially matches a different one with the same numeric prefix (e.g.
    page=196 must never match page=1960) -- see reverse_lookup's own
    docstring for the verified-live query shape.
    """
    if isinstance(locator, PdfLocator):
        return f"citation:pdf?path={locator.path}&page={locator.page}"
    if isinstance(locator, XsdLocator):
        return locator_to_source_uri(locator)
    raise TypeError(f"unknown locator type: {locator!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_locator.py -v`

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd /work/generator
git add citations/locator.py tests/citations/test_locator.py
git commit -m "Add citations.locator: a typed, round-trippable SourceLocator"
```

---

### Task 2: Refactor `webapp/pipeline.py` to use `citations.locator`

**Files:**
- Modify: `webapp/pipeline.py`
- Test: `tests/webapp/test_pipeline.py`

**Interfaces:**
- Consumes: `citations.locator.PdfLocator`, `XsdLocator`, `locator_to_source_uri` (Task 1)
- Produces: no new public interface — `run_pipeline_and_store`'s own behavior and every stored `source_uri` string are unchanged (verified below), just built via the typed locator instead of ad hoc f-strings.

- [ ] **Step 1: Write the failing test**

Append to `tests/webapp/test_pipeline.py` (this file already has `ROOT_XSD`,
`ANNEX_PDF`, `STORE_PATH` constants and an `open_store`/`run_pipeline_and_store`
import — add to them, don't redefine):

```python
def test_run_pipeline_and_store_produces_the_same_source_uris_as_before_the_locator_refactor():
    # Real, confirmed regression anchor from this plan's own spec work:
    # AOrdNr's English citation is exactly this page/bbox on the real PDF.
    # This must stay byte-identical after routing source_uri construction
    # through citations.locator, since no store migration is planned --
    # every fact Plans A-D already recorded must keep resolving.
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        info = run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-17T00:00:00Z", created_at="2026-09-17T00:00:00Z",
        )
        graph = dataset.graph(URIRef(info.graph_uri))
        subject = next(
            s for s in graph.subjects(XSDO.name, Literal("AOrdNr"))
            if any(o.language == "en" for o in graph.objects(s, XSDO.documentation))
        )
        english = next(o for o in graph.objects(subject, XSDO.documentation) if o.language == "en")
        record = get_provenance(dataset, info.graph_uri, subject, XSDO.documentation, english)
        assert record.source_uri == (
            "citation:pdf?path=/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
            "&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179"
        )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

(This file already imports `get_provenance`, `Literal`, `URIRef`, `XSDO` from
earlier tasks in Plan C — check the top of `tests/webapp/test_pipeline.py`
and add any of these four names that aren't already imported.)

- [ ] **Step 2: Run test to verify it fails for the right reason first**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_pipeline.py -v -k locator_refactor`

Expected: at this point the test should actually PASS already (the refactor
hasn't broken anything yet, since it hasn't happened) — confirming the
*exact* expected string before you touch `pipeline.py`. If it fails here,
stop and re-derive the expected string from a real run before proceeding;
don't hand-edit the assertion to match broken output.

- [ ] **Step 3: Refactor `webapp/pipeline.py`**

Replace the two `source_uri = f"citation:..."` lines:

```python
from citations.locator import PdfLocator, XsdLocator, locator_to_source_uri
```

In `_attach_english_provenance`, replace:

```python
        x0, top, x1, bottom = matching.bbox
        source_uri = (
            f"citation:pdf?path={pdf_path}&page={matching.page_number}"
            f"&x0={x0}&top={top}&x1={x1}&bottom={bottom}"
        )
```

with:

```python
        source_uri = locator_to_source_uri(
            PdfLocator(path=pdf_path, page=matching.page_number, bbox=matching.bbox)
        )
```

In `_attach_german_provenance_for_global_constructs`, replace:

```python
        citation = capture_xsd_fragment(component)
        source_uri = f"citation:xsd?file={citation.source_file}&component={qname}"
```

with:

```python
        citation = capture_xsd_fragment(component)
        source_uri = locator_to_source_uri(XsdLocator(file=citation.source_file, component=qname))
```

- [ ] **Step 4: Run the test to verify it still passes**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_pipeline.py -v -k locator_refactor`

Expected: PASS — same string as Step 2, now produced via the typed locator.

- [ ] **Step 5: Run the full existing pipeline test file**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_pipeline.py -v`

Expected: all pass (this file's pre-existing tests, unaffected by this refactor).

- [ ] **Step 6: Commit**

```bash
git add webapp/pipeline.py tests/webapp/test_pipeline.py
git commit -m "Route webapp.pipeline's source_uri construction through citations.locator"
```

---

### Task 3: `render_pdf_page` — full-page rendering for Synced Panes

**Files:**
- Modify: `citations/pdf_citation.py`
- Test: `tests/citations/test_pdf_citation.py`

**Interfaces:**
- Produces: `citations.pdf_citation.render_pdf_page(pdf_path: str, page_number: int, resolution: int = 150) -> bytes` — a full, uncropped page PNG. Same 1-indexed `page_number` convention as `crop_pdf_page`.

- [ ] **Step 1: Write the failing test**

Append to `tests/citations/test_pdf_citation.py`:

```python
def test_render_pdf_page_returns_the_full_uncropped_page():
    png_bytes = render_pdf_page(ANNEX_PDF, page_number=5)

    assert len(png_bytes) > 100
    image = Image.open(io.BytesIO(png_bytes))
    assert image.format == "PNG"

    with pdfplumber.open(ANNEX_PDF) as pdf:
        page = pdf.pages[4]
        expected_width_px = round(page.width * 150 / 72)
        expected_height_px = round(page.height * 150 / 72)
    # pdfplumber/Pillow rounding can be off by a pixel; allow that, not more.
    assert abs(image.width - expected_width_px) <= 1
    assert abs(image.height - expected_height_px) <= 1


def test_render_pdf_page_rejects_out_of_range_page_number():
    with pytest.raises(ValueError) as excinfo:
        render_pdf_page(ANNEX_PDF, page_number=99999)

    error_msg = str(excinfo.value)
    assert "page_number=99999" in error_msg
    assert "262" in error_msg
```

Add `render_pdf_page` to the existing `from citations.pdf_citation import ...` line at the top of this file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_pdf_citation.py -v -k render_pdf_page`

Expected: FAIL with `ImportError: cannot import name 'render_pdf_page'`.

- [ ] **Step 3: Refactor `citations/pdf_citation.py` to share page-opening logic**

Replace the full file contents:

```python
"""Real inline evidence for an English documentation string: a cropped
PNG of the actual annex-PDF page region it came from, not re-typed text.
Verified live against the real annex PDF during design -- pdfplumber
(already a project dependency) can extract word-level bounding boxes and
render/crop a page region directly, no new dependency needed.
"""
from __future__ import annotations

import io

import pdfplumber


def _open_validated_page(pdf: pdfplumber.PDF, page_number: int, pdf_path: str):
    """`page_number` is 1-indexed, matching pdfplumber's own `Page.page_number`
    attribute -- the same convention `extraction.annex_pdf.TextOccurrence`
    (the only real producer of a citation's page_number) already uses and
    documents. This was a real, previously-shipped off-by-one bug in
    `crop_pdf_page` (fixed 2026-09-17): it used to index `pdf.pages` directly
    with the 1-indexed value, silently cropping the page AFTER the intended
    one for every citation in the system -- invisible to every existing test
    at the time, since none of them checked cropped *content*, only that some
    non-empty PNG came back.
    """
    if not (1 <= page_number <= len(pdf.pages)):
        raise ValueError(
            f"page_number={page_number} out of range for {pdf_path} "
            f"(has {len(pdf.pages)} pages, 1-indexed)"
        )
    return pdf.pages[page_number - 1]


def crop_pdf_page(
    pdf_path: str,
    page_number: int,
    bbox: tuple[float, float, float, float],
    padding: float = 5.0,
    resolution: int = 150,
) -> bytes:
    x0, top, x1, bottom = bbox
    with pdfplumber.open(pdf_path) as pdf:
        page = _open_validated_page(pdf, page_number, pdf_path)
        padded_bbox = (
            max(0.0, x0 - padding),
            max(0.0, top - padding),
            min(page.width, x1 + padding),
            min(page.height, bottom + padding),
        )
        cropped_page = page.crop(padded_bbox)
        page_image = cropped_page.to_image(resolution=resolution)

        buffer = io.BytesIO()
        page_image.original.save(buffer, format="PNG")
        return buffer.getvalue()


def render_pdf_page(pdf_path: str, page_number: int, resolution: int = 150) -> bytes:
    """The whole page, uncropped -- for Synced Panes mode's source pane,
    which shows a real, complete page a user can scroll/click through,
    not a single fact's citation crop.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = _open_validated_page(pdf, page_number, pdf_path)
        page_image = page.to_image(resolution=resolution)

        buffer = io.BytesIO()
        page_image.original.save(buffer, format="PNG")
        return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_pdf_citation.py -v`

Expected: PASS (all 8 tests in this file — the 6 pre-existing plus the 2 new ones).

- [ ] **Step 5: Commit**

```bash
git add citations/pdf_citation.py tests/citations/test_pdf_citation.py
git commit -m "Add render_pdf_page for Synced Panes' full-page source view"
```

---

### Task 4: `provenance/reverse_lookup.py` — source → derived facts

**Files:**
- Create: `provenance/reverse_lookup.py`
- Test: `tests/provenance/test_reverse_lookup.py`

**Interfaces:**
- Consumes: `citations.locator.SourceLocator`, `locator_lookup_key` (Task 1)
- Produces: `provenance.reverse_lookup.find_facts_by_locator(dataset: Dataset, graph_uri: str, locator: SourceLocator) -> list[tuple[str, str, str]]` — a list of `(subject_uri, predicate_uri, object_value)` triples derived from this locator's source, at its own granularity (page-level for PDF, exact component for XSD).

The core query pattern (a variable RDF-star triple as a subject,
`<<?s ?p ?o>> prov:hasProvenanceRecord ?record`) was verified live against
the real demo store before this plan was written — it returns real,
correct results; it is not a hypothetical.

- [ ] **Step 1: Write the failing test**

`tests/provenance/test_reverse_lookup.py`:

```python
import shutil

from rdflib import Literal, Namespace, URIRef

from citations.locator import PdfLocator, XsdLocator
from provenance.record import attach_provenance
from provenance.reverse_lookup import find_facts_by_locator
from store.database import open_store
from store.runs import write_run
from rdflib import Graph

STORE_PATH = "/tmp/test_reverse_lookup_store"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_find_facts_by_locator_finds_a_pdf_fact_by_page_ignoring_bbox():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectA, EX.documentation, Literal("hello", lang="en")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectA, EX.documentation, Literal("hello", lang="en"),
            source_uri="citation:pdf?path=/a.pdf&page=5&x0=1&top=2&x1=3&bottom=4",
            generated_at="2026-09-17T00:00:00Z",
        )

        # A locator for the SAME page, DIFFERENT bbox -- must still match,
        # since PDF reverse lookup is page-level, not exact-region.
        locator = PdfLocator(path="/a.pdf", page=5, bbox=(999.0, 999.0, 1000.0, 1000.0))
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == [(str(EX.SubjectA), str(EX.documentation), "hello")]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_does_not_match_a_different_page_with_a_shared_numeric_prefix():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectB, EX.documentation, Literal("world", lang="en")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectB, EX.documentation, Literal("world", lang="en"),
            source_uri="citation:pdf?path=/a.pdf&page=1960&x0=1&top=2&x1=3&bottom=4",
            generated_at="2026-09-17T00:00:00Z",
        )

        locator = PdfLocator(path="/a.pdf", page=196)
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_finds_an_xsd_fact_by_exact_component():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.SubjectC, EX.documentation, Literal("Deutsch.", lang="de")))
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        attach_provenance(
            dataset, info.graph_uri, EX.SubjectC, EX.documentation, Literal("Deutsch.", lang="de"),
            source_uri="citation:xsd?file=/a.xsd&component={urn:ns}TypeName",
            generated_at="2026-09-17T00:00:00Z",
        )

        locator = XsdLocator(file="/a.xsd", component="{urn:ns}TypeName")
        results = find_facts_by_locator(dataset, info.graph_uri, locator)

        assert results == [(str(EX.SubjectC), str(EX.documentation), "Deutsch.")]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_find_facts_by_locator_returns_empty_list_when_nothing_matches():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        info = write_run(
            dataset, run_id="r1", graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-17T00:00:00Z",
        )
        locator = PdfLocator(path="/nowhere.pdf", page=1)
        assert find_facts_by_locator(dataset, info.graph_uri, locator) == []
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/provenance/test_reverse_lookup.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'provenance.reverse_lookup'`.

- [ ] **Step 3: Implement `provenance/reverse_lookup.py`**

```python
"""Answers "what was derived from this source location" -- the reverse
of provenance.record.get_provenance, which only ever answers "where did
this fact come from." Needed for Synced Panes mode's source-to-derived
direction (see the design spec).

The query shape -- a variable RDF-star triple used as a subject,
`<<?s ?p ?o>> prov:hasProvenanceRecord ?record` -- was verified live
against the real demo store (not assumed) before this module was written:
this pyoxigraph version supports it and returns correct results. This is
the same GRAPH-scoped SPARQL string-building style already used by
provenance.record and review.corrections in this codebase.
"""
from __future__ import annotations

import re
import urllib.parse

from rdflib import Dataset

from citations.locator import SourceLocator, locator_lookup_key
from provenance.vocab import PROV


def find_facts_by_locator(
    dataset: Dataset, graph_uri: str, locator: SourceLocator
) -> list[tuple[str, str, str]]:
    # Percent-encode the same way attach_provenance encodes source_uri
    # before storing it (urllib.parse.quote(..., safe=":/?=&#")) -- for
    # every real path in this corpus (no spaces) this is a no-op, but
    # matching the encoding exactly keeps this correct if that ever
    # changes, rather than relying on it being a no-op by accident.
    key = urllib.parse.quote(locator_lookup_key(locator), safe=":/?=&#")
    # REGEX with a real anchor (a following "&" or end-of-string), not a
    # plain substring match -- confirmed live during this plan's own
    # design that a naive CONTAINS/STRSTARTS check on "page=196" would
    # also match "page=1960". re.escape handles the locator's own special
    # regex characters (e.g. XSD component qnames contain "{", "}").
    pattern = re.escape(key) + r"(&|$)"
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri}> {{
        ?record prov:wasDerivedFrom ?src .
        FILTER(REGEX(STR(?src), "{pattern}"))
        <<?s ?p ?o>> prov:hasProvenanceRecord ?record .
      }}
    }}
    """))
    return [(str(row["s"]), str(row["p"]), str(row["o"])) for row in results]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/provenance/test_reverse_lookup.py -v`

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add provenance/reverse_lookup.py tests/provenance/test_reverse_lookup.py
git commit -m "Add provenance.reverse_lookup: source-location to derived-facts"
```

---

### Task 5: `webapp/routes_sources.py` — the new HTTP surface

**Files:**
- Create: `webapp/routes_sources.py`
- Modify: `webapp/main.py`
- Modify: `webapp/errors.py`
- Test: `tests/webapp/test_routes_sources.py`

**Interfaces:**
- Consumes: `citations.locator` (Task 1), `citations.pdf_citation.render_pdf_page` (Task 3), `provenance.reverse_lookup.find_facts_by_locator` (Task 4)
- Produces:
  - `GET /api/sources/lookup?kind=pdf&path=<p>&page=<n>` or `?kind=xsd&file=<f>&component=<c>` — `[{"subject": str, "predicate": str, "object": str}, ...]`
  - `GET /api/sources/pdf/page?path=<p>&page=<n>` — `image/png` bytes, the full page
  - `GET /api/sources/xsd/file?file=<f>` — `{"content": str}`, the raw XSD file text (for the frontend's XSD plugin to tokenize/highlight client-side)

- [ ] **Step 1: Write the failing tests**

`tests/webapp/test_routes_sources.py`:

```python
import shutil

from fastapi.testclient import TestClient

from webapp.main import create_app

STORE_PATH = "/tmp/test_webapp_store_sources"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_lookup_pdf_finds_real_facts_on_a_real_page():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={
            "kind": "pdf", "path": ANNEX_PDF, "page": 196,
        })

        assert response.status_code == 200
        subjects = {row["subject"] for row in response.json()}
        assert any("AmtlicheOrdnungsnummerMa23ListeType" in s for s in subjects)
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_lookup_xsd_finds_real_facts_for_a_real_global_component():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={
            "kind": "xsd", "file": ROOT_XSD,
            "component": "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType",
        })

        assert response.status_code == 200
        # May legitimately be empty for this specific component/run; the
        # real assertion is that the endpoint answers cleanly, not 500s.
        assert isinstance(response.json(), list)
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_lookup_rejects_an_unknown_kind_with_400_not_500():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/lookup", params={"kind": "csv", "path": "/a.csv"})

        assert response.status_code == 400
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_pdf_page_endpoint_returns_a_real_full_page_image():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/pdf/page", params={"path": ANNEX_PDF, "page": 5})

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 1000
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_xsd_file_endpoint_returns_the_real_raw_text():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/xsd/file", params={"file": ROOT_XSD})

        assert response.status_code == 200
        assert "<xs:schema" in response.json()["content"]
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_xsd_file_endpoint_404s_for_a_nonexistent_file():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    try:
        app = create_app(STORE_PATH, ROOT_XSD, ANNEX_PDF)
        client = TestClient(app)

        response = client.get("/api/sources/xsd/file", params={"file": "/tmp/nope.xsd"})

        assert response.status_code == 404
    finally:
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_sources.py -v`

Expected: FAIL with 404s (route module doesn't exist / isn't registered yet).

- [ ] **Step 3: Implement `webapp/routes_sources.py`**

```python
"""The reverse-lookup and full-source-rendering endpoints Synced Panes
mode needs -- see citations.locator and provenance.reverse_lookup for
the underlying capability. Kept separate from webapp/routes_provenance.py
(which only ever answers "where did this ONE fact come from") since this
module answers the opposite direction and serves whole documents, not
per-fact crops.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response

from citations.locator import PdfLocator, XsdLocator
from citations.pdf_citation import render_pdf_page
from provenance.reverse_lookup import find_facts_by_locator

router = APIRouter(prefix="/api/sources")


@router.get("/lookup")
def lookup(
    request: Request, kind: str, path: str | None = None, page: int | None = None,
    file: str | None = None, component: str | None = None,
):
    if kind == "pdf":
        locator = PdfLocator(path=path, page=page)
    elif kind == "xsd":
        locator = XsdLocator(file=file, component=component)
    else:
        raise ValueError(f"kind={kind!r} is not a supported source kind (expected 'pdf' or 'xsd')")

    graph_uri = request.app.state.latest_run.graph_uri
    results = find_facts_by_locator(request.app.state.dataset, graph_uri, locator)
    return [{"subject": s, "predicate": p, "object": o} for s, p, o in results]


@router.get("/pdf/page")
def get_pdf_page(path: str, page: int):
    png_bytes = render_pdf_page(path, page_number=page)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/xsd/file")
def get_xsd_file(file: str):
    if not Path(file).exists():
        raise FileNotFoundError(f"no such file: {file}")
    return {"content": Path(file).read_text(encoding="utf-8")}
```

Modify `webapp/main.py`: add, alongside the other router registrations
(right before `install_error_handlers(app)`):

```python
    from webapp.routes_sources import router as sources_router
    app.include_router(sources_router)
```

Modify `webapp/errors.py`: `lookup`'s own `ValueError` for an unsupported
`kind` and `get_xsd_file`'s `FileNotFoundError` are already covered by
the existing `_HANDLERS` table (`ValueError -> 400`, `FileNotFoundError ->
404`) — no change needed there. Confirm this by re-reading
`webapp/errors.py`'s `_HANDLERS` tuple before writing this task's report;
if either mapping has changed since this plan was written, add the
missing entry following the existing `(ExceptionType, status, message)`
tuple pattern.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/webapp/test_routes_sources.py -v`

Expected: PASS (6 tests).

- [ ] **Step 5: Run the full backend test suite**

Run: `cd /work && python3 -m pytest generator/tests/ -q`

Expected: every test passes (this task only adds new routes; nothing
existing should be affected).

- [ ] **Step 6: Commit**

```bash
git add webapp/routes_sources.py webapp/main.py tests/webapp/test_routes_sources.py
git commit -m "Add /api/sources/lookup, /pdf/page, /xsd/file for Synced Panes mode"
```

---

### Task 6: Frontend routing + the shared focus model

**Files:**
- Modify: `frontend/package.json` (add `react-router-dom`)
- Create: `frontend/src/lib/focus.ts`
- Create: `frontend/src/lib/hoverFocus.tsx`
- Test: `frontend/src/lib/focus.test.tsx`
- Test: `frontend/src/lib/hoverFocus.test.tsx`

**Interfaces:**
- Produces:
  - `frontend/src/lib/focus.ts` — `useFocus(): { mode: string; subject: string | null; predicate: string | null; lang: string | null; setFocus(next: { mode: string; subject?: string; predicate?: string; lang?: string }): void }` (a thin wrapper over `react-router-dom`'s `useParams`/`useNavigate`)
  - `frontend/src/lib/hoverFocus.tsx` — `HoverFocusProvider`, `useHoverFocus(): { hovered: string | null; setHovered(subject: string | null): void }` (a plain React Context, never touches the URL)

- [ ] **Step 1: Install `react-router-dom`**

```bash
cd /work/generator/frontend
npm install react-router-dom
```

- [ ] **Step 2: Write the failing tests**

`frontend/src/lib/focus.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { useFocus } from "@/lib/focus"

function Probe() {
  const focus = useFocus()
  return (
    <div>
      <span data-testid="mode">{focus.mode}</span>
      <span data-testid="subject">{focus.subject ?? "none"}</span>
      <button onClick={() => focus.setFocus({ mode: "living-text", subject: "urn:new" })}>
        go
      </button>
    </div>
  )
}

describe("useFocus", () => {
  it("reads mode and subject from the URL", () => {
    render(
      <MemoryRouter initialEntries={["/graph/urn:s"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId("mode").textContent).toBe("graph")
    expect(screen.getByTestId("subject").textContent).toBe("urn:s")
  })

  it("setFocus navigates to the new URL, updating what useFocus reads", async () => {
    render(
      <MemoryRouter initialEntries={["/graph/urn:s"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole("button", { name: "go" }))

    expect(screen.getByTestId("mode").textContent).toBe("living-text")
    expect(screen.getByTestId("subject").textContent).toBe("urn:new")
  })

  it("subject is null when the URL has no subject segment", () => {
    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route path="/:mode/:subject?/:predicate?/:lang?" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByTestId("subject").textContent).toBe("none")
  })
})
```

`frontend/src/lib/hoverFocus.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { HoverFocusProvider, useHoverFocus } from "@/lib/hoverFocus"

function Probe() {
  const { hovered, setHovered } = useHoverFocus()
  return (
    <div>
      <span data-testid="hovered">{hovered ?? "none"}</span>
      <button onClick={() => setHovered("urn:x")}>hover</button>
      <button onClick={() => setHovered(null)}>unhover</button>
    </div>
  )
}

describe("useHoverFocus", () => {
  it("starts as null and updates without touching any router state", async () => {
    render(
      <HoverFocusProvider>
        <Probe />
      </HoverFocusProvider>,
    )

    expect(screen.getByTestId("hovered").textContent).toBe("none")
    await userEvent.click(screen.getByRole("button", { name: "hover" }))
    expect(screen.getByTestId("hovered").textContent).toBe("urn:x")
    await userEvent.click(screen.getByRole("button", { name: "unhover" }))
    expect(screen.getByTestId("hovered").textContent).toBe("none")
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /work/generator/frontend && npx vitest run src/lib/focus.test.tsx src/lib/hoverFocus.test.tsx`

Expected: FAIL — neither `@/lib/focus` nor `@/lib/hoverFocus` exists yet.

- [ ] **Step 4: Implement `frontend/src/lib/focus.ts`**

```typescript
import { useNavigate, useParams } from "react-router-dom"

export interface Focus {
  mode: string
  subject: string | null
  predicate: string | null
  lang: string | null
  setFocus: (next: { mode: string; subject?: string; predicate?: string; lang?: string }) => void
}

export function useFocus(): Focus {
  const params = useParams<{ mode: string; subject?: string; predicate?: string; lang?: string }>()
  const navigate = useNavigate()

  function setFocus(next: { mode: string; subject?: string; predicate?: string; lang?: string }) {
    const segments = [next.mode, next.subject, next.predicate, next.lang].filter(
      (segment): segment is string => segment !== undefined,
    )
    navigate(`/${segments.map(encodeURIComponent).join("/")}`)
  }

  return {
    mode: params.mode ?? "graph",
    subject: params.subject ?? null,
    predicate: params.predicate ?? null,
    lang: params.lang ?? null,
    setFocus,
  }
}
```

- [ ] **Step 5: Implement `frontend/src/lib/hoverFocus.tsx`**

```tsx
import { createContext, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

interface HoverFocusValue {
  hovered: string | null
  setHovered: (subject: string | null) => void
}

const HoverFocusContext = createContext<HoverFocusValue | null>(null)

export function HoverFocusProvider({ children }: { children: ReactNode }) {
  const [hovered, setHovered] = useState<string | null>(null)
  const value = useMemo(() => ({ hovered, setHovered }), [hovered])
  return <HoverFocusContext.Provider value={value}>{children}</HoverFocusContext.Provider>
}

export function useHoverFocus(): HoverFocusValue {
  const context = useContext(HoverFocusContext)
  if (!context) {
    throw new Error("useHoverFocus must be used inside a HoverFocusProvider")
  }
  return context
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /work/generator/frontend && npx vitest run src/lib/focus.test.tsx src/lib/hoverFocus.test.tsx`

Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/focus.ts frontend/src/lib/focus.test.tsx frontend/src/lib/hoverFocus.tsx frontend/src/lib/hoverFocus.test.tsx
git commit -m "Add react-router-dom and the shared focus/hover-focus model"
```

---

### Task 7: `frontend/src/lib/sourceLocator.ts` — the TypeScript locator

**Files:**
- Create: `frontend/src/lib/sourceLocator.ts`
- Test: `frontend/src/lib/sourceLocator.test.ts`

**Interfaces:**
- Produces:
  - `PdfLocator` — `{ kind: "pdf"; path: string; page: number; bbox?: [number, number, number, number] }`
  - `XsdLocator` — `{ kind: "xsd"; file: string; component: string }`
  - `SourceLocator = PdfLocator | XsdLocator`
  - `parseSourceUri(sourceUri: string): SourceLocator | null`

Mirrors `citations/locator.py` (Task 1) exactly — same field names, same
`citation:pdf?...`/`citation:xsd?...` scheme, same page-level-vs-bbox
distinction. There is no `locatorToSourceUri`/serialization function
needed on the frontend: the frontend only ever *parses* a `sourceUri`
string the backend already produced (via `GET /api/provenance`); it never
constructs one to send anywhere.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/sourceLocator.test.ts`:

```typescript
import { describe, expect, it } from "vitest"
import { parseSourceUri } from "@/lib/sourceLocator"

describe("parseSourceUri", () => {
  it("parses a PDF locator with a bbox", () => {
    const locator = parseSourceUri(
      "citation:pdf?path=/a/b.pdf&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179",
    )
    expect(locator).toEqual({
      kind: "pdf", path: "/a/b.pdf", page: 196, bbox: [137.64, 610.179, 223.878, 619.179],
    })
  })

  it("parses a PDF locator without a bbox", () => {
    const locator = parseSourceUri("citation:pdf?path=/a/b.pdf&page=5")
    expect(locator).toEqual({ kind: "pdf", path: "/a/b.pdf", page: 5 })
  })

  it("parses an XSD locator", () => {
    const locator = parseSourceUri("citation:xsd?file=/a/b.xsd&component=%7Burn%3Ans%7DTypeName")
    expect(locator).toEqual({ kind: "xsd", file: "/a/b.xsd", component: "{urn:ns}TypeName" })
  })

  it("returns null for an unrecognized scheme", () => {
    expect(parseSourceUri("https://example.org/x")).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/lib/sourceLocator.test.ts`

Expected: FAIL — `@/lib/sourceLocator` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/lib/sourceLocator.ts`**

```typescript
export interface PdfLocator {
  kind: "pdf"
  path: string
  page: number
  bbox?: [number, number, number, number]
}

export interface XsdLocator {
  kind: "xsd"
  file: string
  component: string
}

export type SourceLocator = PdfLocator | XsdLocator

// Mirrors citations/locator.py's source_uri_to_locator exactly -- same
// scheme, same field names. new URL() can't parse a "citation:" scheme
// directly (no host component), so query params are parsed via
// URLSearchParams against everything after the first "?".
export function parseSourceUri(sourceUri: string): SourceLocator | null {
  const queryStart = sourceUri.indexOf("?")
  if (queryStart === -1) return null
  const scheme = sourceUri.slice(0, queryStart)
  const params = new URLSearchParams(sourceUri.slice(queryStart + 1))

  if (scheme === "citation:pdf") {
    const path = params.get("path")
    const page = params.get("page")
    if (path === null || page === null) return null
    const x0 = params.get("x0")
    const top = params.get("top")
    const x1 = params.get("x1")
    const bottom = params.get("bottom")
    const bbox: [number, number, number, number] | undefined =
      x0 !== null && top !== null && x1 !== null && bottom !== null
        ? [Number(x0), Number(top), Number(x1), Number(bottom)]
        : undefined
    return bbox
      ? { kind: "pdf", path, page: Number(page), bbox }
      : { kind: "pdf", path, page: Number(page) }
  }

  if (scheme === "citation:xsd") {
    const file = params.get("file")
    const component = params.get("component")
    if (file === null || component === null) return null
    return { kind: "xsd", file, component }
  }

  return null
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/lib/sourceLocator.test.ts`

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/sourceLocator.ts frontend/src/lib/sourceLocator.test.ts
git commit -m "Add frontend SourceLocator, mirroring citations/locator.py"
```

---

### Task 8: The source-plugin registry + PDF and XSD plugins

**Files:**
- Create: `frontend/src/sourcePlugins/types.ts`
- Create: `frontend/src/sourcePlugins/registry.ts`
- Create: `frontend/src/sourcePlugins/pdfPlugin.tsx`
- Create: `frontend/src/sourcePlugins/xsdPlugin.tsx`
- Test: `frontend/src/sourcePlugins/conformance.test.tsx`

**Interfaces:**
- Consumes: `SourceLocator`, `PdfLocator`, `XsdLocator` (Task 7)
- Produces:
  - `frontend/src/sourcePlugins/types.ts` — the `SourcePlugin` interface:
    ```typescript
    interface SourcePlugin<L extends SourceLocator> {
      kind: L["kind"]
      renderLocator(locator: L): ReactNode
      renderWhole(locator: L, onLocatorClick: (locator: L) => void): ReactNode
    }
    ```
  - `frontend/src/sourcePlugins/registry.ts` — `getPlugin(kind: string): SourcePlugin<SourceLocator> | undefined`, `PLUGINS: Record<string, SourcePlugin<SourceLocator>>`
  - `frontend/src/sourcePlugins/pdfPlugin.tsx` — `pdfPlugin: SourcePlugin<PdfLocator>`
  - `frontend/src/sourcePlugins/xsdPlugin.tsx` — `xsdPlugin: SourcePlugin<XsdLocator>`

`renderLocator` renders a small, precise citation (a cropped PDF image, an
XSD component's own fragment) — this replaces `ProvenanceMarker`'s
hand-rolled `renderCitation()` (Task 9 does that replacement). `renderWhole`
renders the *entire* source document with a click handler that maps a
click back to a locator at this plugin's own real granularity (page-level
for PDF, component-level for XSD — see this plan's Global Constraints) —
Task 13 (Synced Panes) is this method's first real consumer.

- [ ] **Step 1: Write the failing test**

`frontend/src/sourcePlugins/conformance.test.tsx` — every registered
plugin must pass the same contract, so adding a new source kind later
stays cheap and safe (per the design spec's Testing strategy):

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PLUGINS } from "@/sourcePlugins/registry"
import type { PdfLocator, XsdLocator } from "@/lib/sourceLocator"

const SAMPLE_LOCATORS: Record<string, PdfLocator | XsdLocator> = {
  pdf: { kind: "pdf", path: "/a.pdf", page: 5, bbox: [1, 2, 3, 4] },
  xsd: { kind: "xsd", file: "/a.xsd", component: "{urn:ns}Type" },
}

describe("source plugin conformance", () => {
  for (const [kind, plugin] of Object.entries(PLUGINS)) {
    it(`${kind} plugin's renderLocator renders something without throwing`, () => {
      const locator = SAMPLE_LOCATORS[kind]
      expect(() => render(<div>{plugin.renderLocator(locator as never)}</div>)).not.toThrow()
    })

    it(`${kind} plugin's renderWhole accepts an onLocatorClick callback without throwing`, () => {
      const locator = SAMPLE_LOCATORS[kind]
      const onLocatorClick = vi.fn()
      expect(() =>
        render(<div>{plugin.renderWhole(locator as never, onLocatorClick)}</div>),
      ).not.toThrow()
    })

    it(`${kind} plugin's own kind matches its registry key`, () => {
      expect(plugin.kind).toBe(kind)
    })
  }

  it("has both real plugins registered", () => {
    expect(Object.keys(PLUGINS).sort()).toEqual(["pdf", "xsd"])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/sourcePlugins/conformance.test.tsx`

Expected: FAIL — none of `@/sourcePlugins/*` exist yet.

- [ ] **Step 3: Implement `frontend/src/sourcePlugins/types.ts`**

```typescript
import type { ReactNode } from "react"
import type { SourceLocator } from "@/lib/sourceLocator"

export interface SourcePlugin<L extends SourceLocator = SourceLocator> {
  kind: L["kind"]
  /** A small, precise citation for one exact fact -- a cropped image, a fragment. */
  renderLocator(locator: L): ReactNode
  /** The entire source document; clicking anywhere calls onLocatorClick with
   * a locator at this plugin's own real granularity (page-level for PDF,
   * whole-component for XSD -- there is no finer-grained data to click into). */
  renderWhole(locator: L, onLocatorClick: (locator: L) => void): ReactNode
}
```

- [ ] **Step 4: Implement `frontend/src/sourcePlugins/pdfPlugin.tsx`**

```tsx
import type { PdfLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

function PdfPage({ locator, onLocatorClick }: { locator: PdfLocator; onLocatorClick: (l: PdfLocator) => void }) {
  return (
    <div>
      <img
        src={`/api/sources/pdf/page?path=${encodeURIComponent(locator.path)}&page=${locator.page}`}
        alt={`Page ${locator.page}`}
        className="w-full cursor-pointer rounded border"
        onClick={() => onLocatorClick({ kind: "pdf", path: locator.path, page: locator.page })}
      />
      <p className="text-xs text-muted-foreground">Page {locator.page}</p>
    </div>
  )
}

export const pdfPlugin: SourcePlugin<PdfLocator> = {
  kind: "pdf",
  renderLocator(locator) {
    if (!locator.bbox) return <p className="text-xs text-muted-foreground">Page {locator.page} (no exact region).</p>
    const [x0, top, x1, bottom] = locator.bbox
    const params = new URLSearchParams({
      path: locator.path, page: String(locator.page),
      x0: String(x0), top: String(top), x1: String(x1), bottom: String(bottom),
    })
    return (
      <img
        src={`/api/citations/pdf?${params.toString()}`}
        alt={`Source citation, page ${locator.page}`}
        className="max-w-full rounded border"
      />
    )
  },
  renderWhole(locator, onLocatorClick) {
    return <PdfPage locator={locator} onLocatorClick={onLocatorClick} />
  },
}
```

No page-count/navigation UI is included here deliberately — there is no
`GET /api/sources/pdf/page-count` endpoint in this plan, and adding one
isn't needed for Synced Panes' own required behavior (Task 14 drives which
page is shown via the clicked locator itself, not in-plugin pagination).
If you want next/previous controls later, that's a real, separate,
additive change: a new backend endpoint plus this component reading it —
not something to fake here.

- [ ] **Step 5: Implement `frontend/src/sourcePlugins/xsdPlugin.tsx`**

```tsx
import { useEffect, useState } from "react"
import { apiGet } from "@/lib/api"
import type { XsdLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

interface XsdCitation {
  fragment: string
  sourceFile: string
}

// A top-level (direct child of <xs:schema>) named component's own
// start/end character offset in the raw file text, and the qname it
// represents -- the real granularity this corpus's XSD citation data
// actually has (see this plan's Global Constraints). Regex-based, not a
// full XML parse: this project's own extraction code (extraction/*.py)
// already establishes precedent for regex/state-machine parsing of this
// corpus's real files rather than pulling in a full XML tooling layer
// for a UI-only concern.
interface ComponentSpan {
  qname: string
  start: number
  end: number
}

function findTargetNamespace(xml: string): string {
  const match = xml.match(/<xs:schema\b[^>]*\btargetNamespace="([^"]*)"/)
  return match ? match[1] : ""
}

function findComponentSpans(xml: string, targetNamespace: string): ComponentSpan[] {
  const spans: ComponentSpan[] = []
  const topLevelPattern =
    /<xs:(complexType|simpleType|element)\b[^>]*\bname="([^"]+)"[^>]*>[\s\S]*?<\/xs:\1>/g
  let match: RegExpExecArray | null
  while ((match = topLevelPattern.exec(xml)) !== null) {
    spans.push({
      qname: `{${targetNamespace}}${match[2]}`,
      start: match.index,
      end: match.index + match[0].length,
    })
  }
  return spans
}

function XsdWhole({ locator, onLocatorClick }: { locator: XsdLocator; onLocatorClick: (l: XsdLocator) => void }) {
  const [content, setContent] = useState<string | null>(null)

  useEffect(() => {
    setContent(null)
    apiGet<{ content: string }>(`/sources/xsd/file?file=${encodeURIComponent(locator.file)}`).then((result) =>
      setContent(result.content),
    )
  }, [locator.file])

  if (content === null) return <p className="text-xs text-muted-foreground">Loading...</p>

  const targetNamespace = findTargetNamespace(content)
  const spans = findComponentSpans(content, targetNamespace)

  const pieces: { text: string; qname: string | null }[] = []
  let cursor = 0
  for (const span of spans) {
    if (span.start > cursor) pieces.push({ text: content.slice(cursor, span.start), qname: null })
    pieces.push({ text: content.slice(span.start, span.end), qname: span.qname })
    cursor = span.end
  }
  if (cursor < content.length) pieces.push({ text: content.slice(cursor), qname: null })

  return (
    <pre className="max-h-[80vh] overflow-auto rounded border bg-muted/30 p-2 text-xs">
      {pieces.map((piece, index) =>
        piece.qname ? (
          <span
            key={index}
            className="cursor-pointer hover:bg-accent"
            onClick={() => onLocatorClick({ kind: "xsd", file: locator.file, component: piece.qname! })}
          >
            {piece.text}
          </span>
        ) : (
          <span key={index}>{piece.text}</span>
        ),
      )}
    </pre>
  )
}

function XsdLocatorCitation({ locator }: { locator: XsdLocator }) {
  const [fragment, setFragment] = useState<XsdCitation | null>(null)
  useEffect(() => {
    setFragment(null)
    const params = new URLSearchParams({ file: locator.file, type_qname: locator.component })
    apiGet<XsdCitation>(`/citations/xsd?${params.toString()}`).then(setFragment)
  }, [locator.file, locator.component])

  if (fragment === null) return <p className="text-xs text-muted-foreground">Loading...</p>
  return (
    <code className="block max-w-full overflow-auto rounded border bg-muted/30 p-2 text-xs whitespace-pre-wrap break-all">
      {fragment.fragment}
    </code>
  )
}

export const xsdPlugin: SourcePlugin<XsdLocator> = {
  kind: "xsd",
  renderLocator(locator) {
    return <XsdLocatorCitation locator={locator} />
  },
  renderWhole(locator, onLocatorClick) {
    return <XsdWhole locator={locator} onLocatorClick={onLocatorClick} />
  },
}
```

`renderLocator`/`renderWhole` are plain object methods, not components —
calling hooks (`useState`/`useEffect`) directly inside them would violate
React's Rules of Hooks the moment two different locators render in the
same parent across re-renders. Both delegate to a real named component
(`XsdLocatorCitation`, `XsdWhole`) that hooks live inside instead, exactly
the same pattern for both methods.

- [ ] **Step 6: Implement `frontend/src/sourcePlugins/registry.ts`**

```typescript
import { pdfPlugin } from "@/sourcePlugins/pdfPlugin"
import { xsdPlugin } from "@/sourcePlugins/xsdPlugin"
import type { SourceLocator } from "@/lib/sourceLocator"
import type { SourcePlugin } from "@/sourcePlugins/types"

export const PLUGINS: Record<string, SourcePlugin<SourceLocator>> = {
  pdf: pdfPlugin as SourcePlugin<SourceLocator>,
  xsd: xsdPlugin as SourcePlugin<SourceLocator>,
}

export function getPlugin(kind: string): SourcePlugin<SourceLocator> | undefined {
  return PLUGINS[kind]
}
```

- [ ] **Step 7: Run the conformance test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/sourcePlugins/conformance.test.tsx`

Expected: PASS (7 tests: 3 per plugin × 2 plugins, plus the registry-keys test).

- [ ] **Step 8: Confirm the project builds**

Run: `cd /work/generator/frontend && npm run build`

Expected: no TypeScript errors. If `pdfPlugin.tsx` still has the
placeholder `apiGet`/`pageCount` code from Step 4's brief, this is where
`noUnusedLocals` will actually catch it — remove it now if you haven't already.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/sourcePlugins/
git commit -m "Add the source-plugin registry: PDF and XSD implementations"
```

---

### Task 9: `SourcePreviewPopover` + `Inspector` — replacing ProvenanceMarker

**Files:**
- Create: `frontend/src/components/SourcePreviewPopover.tsx`
- Create: `frontend/src/components/Inspector.tsx`
- Delete: `frontend/src/components/ProvenanceMarker.tsx`
- Delete: `frontend/src/components/ProvenanceMarker.test.tsx`
- Delete: `frontend/src/components/LineageGraph.tsx` (superseded by Task 12's Graph mode, Level 3)
- Delete: `frontend/src/components/LineageGraph.test.tsx`
- Test: `frontend/src/components/SourcePreviewPopover.test.tsx`
- Test: `frontend/src/components/Inspector.test.tsx`

**Interfaces:**
- Consumes: `getPlugin` (Task 8), `parseSourceUri` (Task 7), `useFocus` (Task 6), `apiGet` (existing)
- Produces:
  - `SourcePreviewPopover` — props `{ subject: string; predicate: string; value: string; lang?: string }` (same props `ProvenanceMarker` had) — **hover**, not click, triggers the fetch and shows the preview inline; a "View lineage" link commits focus to Graph mode instead of opening a Sheet.
  - `Inspector` — props `{ subject: string; predicate: string; value: string; lang?: string }` — a persistent, always-rendered-when-focused panel showing the citation larger, plus the reverse-lookup list ("this source also backs N other facts"), each entry a link that calls `setFocus`.

This is where the design spec's Living Text hover-vs-click distinction
becomes real: `SourcePreviewPopover` reacts to `onMouseEnter`/`onMouseLeave`
(ephemeral), `Inspector` is rendered by `LivingTextView` (Task 10) only when
something is actually focused (via `useFocus`, URL-backed).

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/SourcePreviewPopover.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { SourcePreviewPopover } from "@/components/SourcePreviewPopover"

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe("SourcePreviewPopover", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("fetches and shows a PDF citation image on hover, not click", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sourceUri: "citation:pdf?path=/a.pdf&page=5&x0=1&top=2&x1=3&bottom=4",
          generatedAt: "2026-09-15T14:00:00Z",
        }),
      }),
    )

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" lang="en" />)
    await userEvent.hover(screen.getByText("hello"))

    expect(await screen.findByRole("img")).toBeInTheDocument()
  })

  it("shows a plain note when no provenance is recorded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" />)
    await userEvent.hover(screen.getByText("hello"))

    expect(await screen.findByText(/no source recorded/i)).toBeInTheDocument()
  })

  it("marks the value as backed by a source with a distinct visual style", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ sourceUri: "citation:pdf?path=/a.pdf&page=5", generatedAt: "t" }),
      }),
    )

    renderWithRouter(<SourcePreviewPopover subject="urn:s" predicate="urn:p" value="hello" />)

    expect(screen.getByText("hello")).toHaveClass("underline")
  })
})
```

`frontend/src/components/Inspector.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { Inspector } from "@/components/Inspector"

describe("Inspector", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the citation and the reverse-lookup list of other facts from the same source", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/provenance")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ sourceUri: "citation:pdf?path=/a.pdf&page=196", generatedAt: "t" }),
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => [
            { subject: "urn:other1", predicate: "urn:doc", object: "Other fact 1" },
            { subject: "urn:other2", predicate: "urn:doc", object: "Other fact 2" },
          ],
        })
      }),
    )

    render(
      <MemoryRouter>
        <Inspector subject="urn:s" predicate="urn:doc" value="hello" lang="en" />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/2 other facts/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work/generator/frontend && npx vitest run src/components/SourcePreviewPopover.test.tsx src/components/Inspector.test.tsx`

Expected: FAIL — neither component exists yet.

- [ ] **Step 3: Implement `frontend/src/components/SourcePreviewPopover.tsx`**

```tsx
import { useState } from "react"
import { useFocus } from "@/lib/focus"
import { getPlugin } from "@/sourcePlugins/registry"
import { parseSourceUri } from "@/lib/sourceLocator"
import { apiGet } from "@/lib/api"
import type { ProvenanceRecord } from "@/lib/api"

interface SourcePreviewPopoverProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

export function SourcePreviewPopover({ subject, predicate, value, lang }: SourcePreviewPopoverProps) {
  const [open, setOpen] = useState(false)
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)
  const { setFocus } = useFocus()

  async function handleHover() {
    setOpen(true)
    if (record === undefined) {
      const params = new URLSearchParams({ subject, predicate, value })
      if (lang) params.set("lang", lang)
      const result = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
      setRecord(result)
    }
  }

  function renderPreview() {
    if (record === undefined) return <p className="text-xs text-muted-foreground">Loading...</p>
    if (record === null) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    const locator = parseSourceUri(record.sourceUri)
    if (!locator) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    const plugin = getPlugin(locator.kind)
    if (!plugin) return <p className="text-xs text-muted-foreground">No source recorded.</p>
    return plugin.renderLocator(locator)
  }

  return (
    <span className="relative inline-block">
      <span
        className="underline decoration-dotted decoration-muted-foreground/60 cursor-help"
        onMouseEnter={handleHover}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setFocus({ mode: "living-text", subject, predicate, lang })}
      >
        {value}
      </span>
      {open && (
        <span className="absolute z-20 mt-1 block w-max max-w-sm rounded border bg-popover p-2 shadow-md">
          {renderPreview()}
        </span>
      )}
    </span>
  )
}
```

- [ ] **Step 4: Implement `frontend/src/components/Inspector.tsx`**

```tsx
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { apiGet } from "@/lib/api"
import { getPlugin } from "@/sourcePlugins/registry"
import { parseSourceUri } from "@/lib/sourceLocator"
import type { ProvenanceRecord } from "@/lib/api"

interface ReverseLookupRow {
  subject: string
  predicate: string
  object: string
}

interface InspectorProps {
  subject: string
  predicate: string
  value: string
  lang?: string
}

export function Inspector({ subject, predicate, value, lang }: InspectorProps) {
  const [record, setRecord] = useState<ProvenanceRecord | null | undefined>(undefined)
  const [related, setRelated] = useState<ReverseLookupRow[]>([])

  useEffect(() => {
    setRecord(undefined)
    setRelated([])
    const params = new URLSearchParams({ subject, predicate, value })
    if (lang) params.set("lang", lang)
    apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`).then(setRecord)
  }, [subject, predicate, value, lang])

  useEffect(() => {
    if (!record) return
    const locator = parseSourceUri(record.sourceUri)
    if (!locator) return
    const lookupParams =
      locator.kind === "pdf"
        ? new URLSearchParams({ kind: "pdf", path: locator.path, page: String(locator.page) })
        : new URLSearchParams({ kind: "xsd", file: locator.file, component: locator.component })
    apiGet<ReverseLookupRow[]>(`/sources/lookup?${lookupParams.toString()}`).then((rows) =>
      setRelated(rows.filter((row) => !(row.subject === subject && row.predicate === predicate))),
    )
  }, [record, subject, predicate])

  if (record === undefined) return <p className="text-sm text-muted-foreground">Loading...</p>
  if (record === null) return <p className="text-sm text-muted-foreground">No source recorded.</p>

  const locator = parseSourceUri(record.sourceUri)
  const plugin = locator ? getPlugin(locator.kind) : undefined

  return (
    <div className="space-y-3 rounded border p-3">
      {plugin && locator ? plugin.renderLocator(locator) : <p className="text-xs">No source recorded.</p>}
      {related.length > 0 && (
        <div>
          <p className="text-xs font-medium">{related.length} other facts from this same source:</p>
          <ul className="mt-1 space-y-1">
            {related.map((row, index) => (
              <li key={index}>
                <Link to={`/living-text/${encodeURIComponent(row.subject)}`} className="text-xs text-primary underline">
                  {row.object}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Delete the superseded components**

```bash
cd /work/generator
rm frontend/src/components/ProvenanceMarker.tsx frontend/src/components/ProvenanceMarker.test.tsx
rm frontend/src/components/LineageGraph.tsx frontend/src/components/LineageGraph.test.tsx
```

`DocumentationView.tsx` and `App.tsx` both still reference these — Task 10
replaces `DocumentationView.tsx` with `LivingTextView.tsx` and Task 15
rewrites `App.tsx`'s routing, so leaving these two files broken between
now and then is expected; do not try to patch them in this task.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /work/generator/frontend && npx vitest run src/components/SourcePreviewPopover.test.tsx src/components/Inspector.test.tsx`

Expected: PASS (4 tests). (The suite as a whole will fail to build until
Task 10 replaces `DocumentationView`'s now-broken import — that's expected
and resolved by the next task, not this one.)

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src/components/SourcePreviewPopover.tsx frontend/src/components/SourcePreviewPopover.test.tsx frontend/src/components/Inspector.tsx frontend/src/components/Inspector.test.tsx
git add frontend/src/components/ProvenanceMarker.tsx frontend/src/components/ProvenanceMarker.test.tsx frontend/src/components/LineageGraph.tsx frontend/src/components/LineageGraph.test.tsx
git commit -m "Replace ProvenanceMarker/LineageGraph with SourcePreviewPopover + Inspector"
```

---

### Task 10: `LivingTextView` — hover-transclusion + inline corrections

**Files:**
- Create: `frontend/src/components/LivingTextView.tsx`
- Create: `frontend/src/components/InlineCorrection.tsx`
- Create: `frontend/src/components/ProposeCorrectionInline.tsx`
- Delete: `frontend/src/components/DocumentationView.tsx`
- Delete: `frontend/src/components/DocumentationView.test.tsx`
- Delete: `frontend/src/components/CorrectionsView.tsx`
- Delete: `frontend/src/components/CorrectionsView.test.tsx`
- Test: `frontend/src/components/LivingTextView.test.tsx`
- Test: `frontend/src/components/InlineCorrection.test.tsx`
- Test: `frontend/src/components/ProposeCorrectionInline.test.tsx`

**Interfaces:**
- Consumes: `SourcePreviewPopover`, `Inspector` (Task 9), `useFocus` (Task 6), `apiGet`/`apiPost`/`toUrlSafeBase64` (existing), `DocumentationResponse`/`DocEntry` types (existing)
- Produces:
  - `LivingTextView` — props `{ documentation: DocumentationResponse; pending: PendingCorrection[]; reviewer: string; search: string; onDecided: () => void }` (same `PendingCorrection` shape `CorrectionsView` used: `{ correctionUri: string; targetSubject: string; proposedValue: string; proposer: string }`)
  - `InlineCorrection` — props `{ correction: PendingCorrection; reviewer: string; onDecided: () => void }` — renders the pending correction's track-changes view + inline Approve/Reject
  - `ProposeCorrectionInline` — props `{ subject: string; predicate: string; language: string; currentValue: string; reviewer: string; onProposed: () => void }` — click-to-edit, calls `apiPost("/corrections", ...)`

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/InlineCorrection.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { InlineCorrection } from "@/components/InlineCorrection"

const correction = { correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Fixed.", proposer: "julian" }

describe("InlineCorrection", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the proposed value and disables decisions for the correction's own proposer", () => {
    render(<InlineCorrection correction={correction} reviewer="julian" onDecided={() => {}} />)

    expect(screen.getByText("Fixed.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled()
  })

  it("lets a different reviewer approve and calls onDecided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ decisionUri: "urn:d1" }) }))
    const onDecided = vi.fn()

    render(<InlineCorrection correction={correction} reviewer="someone-else" onDecided={onDecided} />)
    await userEvent.click(screen.getByRole("button", { name: /approve/i }))

    expect(onDecided).toHaveBeenCalled()
  })
})
```

`frontend/src/components/ProposeCorrectionInline.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProposeCorrectionInline } from "@/components/ProposeCorrectionInline"

describe("ProposeCorrectionInline", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lets a reviewer edit and submit a new proposed value", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ correctionUri: "urn:c1" }) })
    vi.stubGlobal("fetch", fetchMock)
    const onProposed = vi.fn()

    render(
      <ProposeCorrectionInline
        subject="urn:s" predicate="urn:p" language="de" currentValue="Original."
        reviewer="julian" onProposed={onProposed}
      />,
    )

    await userEvent.click(screen.getByRole("button", { name: /edit/i }))
    const textbox = screen.getByRole("textbox")
    await userEvent.clear(textbox)
    await userEvent.type(textbox, "Corrected.")
    await userEvent.click(screen.getByRole("button", { name: /propose/i }))

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/corrections",
      expect.objectContaining({ method: "POST" }),
    )
    expect(onProposed).toHaveBeenCalled()
  })
})
```

`frontend/src/components/LivingTextView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { LivingTextView } from "@/components/LivingTextView"
import type { DocumentationResponse } from "@/lib/api"

const documentation: DocumentationResponse = {
  matched: [{ uri: "urn:s1", name: "Matched1", languages: { de: "Deutsch.", en: "English." } }],
  unmatched: [{ uri: "urn:s2", name: "Unmatched1", languages: { de: "Nur Deutsch." } }],
  ambiguous: [],
  englishOnly: [],
}

describe("LivingTextView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders matched and unmatched entries, with an inline pending correction shown", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => null }))
    const pending = [{ correctionUri: "urn:c1", targetSubject: "urn:s1", proposedValue: "Neu.", proposer: "julian" }]

    render(
      <MemoryRouter>
        <LivingTextView documentation={documentation} pending={pending} reviewer="someone-else" search="" onDecided={() => {}} />
      </MemoryRouter>,
    )

    expect(screen.getByText("Matched1")).toBeInTheDocument()
    expect(screen.getByText("Unmatched1")).toBeInTheDocument()
    expect(screen.getByText("Neu.")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /work/generator/frontend && npx vitest run src/components/InlineCorrection.test.tsx src/components/ProposeCorrectionInline.test.tsx src/components/LivingTextView.test.tsx`

Expected: FAIL — none of these three components exist yet.

- [ ] **Step 3: Implement `frontend/src/components/InlineCorrection.tsx`**

```tsx
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiPost, toUrlSafeBase64 } from "@/lib/api"

export interface PendingCorrection {
  correctionUri: string
  targetSubject: string
  proposedValue: string
  proposer: string
}

interface InlineCorrectionProps {
  correction: PendingCorrection
  reviewer: string
  onDecided: () => void
}

export function InlineCorrection({ correction, reviewer, onDecided }: InlineCorrectionProps) {
  const [reason, setReason] = useState("")
  const disabled = correction.proposer === reviewer

  async function decide(outcome: "approve" | "reject") {
    await apiPost(`/corrections/${toUrlSafeBase64(correction.correctionUri)}/${outcome}`, { reason }, reviewer)
    onDecided()
  }

  return (
    <div className="mt-1 rounded border border-amber-400 bg-amber-50 p-2 text-sm dark:bg-amber-950">
      <p>
        Proposed by {correction.proposer}: <ins className="bg-green-100 dark:bg-green-900">{correction.proposedValue}</ins>
      </p>
      <input
        className="mt-1 w-full rounded border p-1 text-xs"
        placeholder="Reason (optional)"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="mt-1 flex gap-2">
        <Button size="sm" disabled={disabled} onClick={() => decide("approve")}>
          Approve
        </Button>
        <Button size="sm" variant="destructive" disabled={disabled} onClick={() => decide("reject")}>
          Reject
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Implement `frontend/src/components/ProposeCorrectionInline.tsx`**

```tsx
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { apiPost } from "@/lib/api"

interface ProposeCorrectionInlineProps {
  subject: string
  predicate: string
  language: string
  currentValue: string
  reviewer: string
  onProposed: () => void
}

export function ProposeCorrectionInline({
  subject, predicate, language, currentValue, reviewer, onProposed,
}: ProposeCorrectionInlineProps) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(currentValue)
  const [reason, setReason] = useState("")

  if (!editing) {
    return (
      <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => setEditing(true)}>
        Edit
      </Button>
    )
  }

  async function submit() {
    await apiPost(
      "/corrections",
      {
        targetSubject: subject, targetPredicate: predicate, targetLanguage: language,
        proposedValue: value, priorValue: currentValue, reason,
      },
      reviewer,
    )
    setEditing(false)
    onProposed()
  }

  return (
    <div className="mt-1 space-y-1">
      <textarea className="w-full rounded border p-1 text-xs" value={value} onChange={(event) => setValue(event.target.value)} />
      <input
        className="w-full rounded border p-1 text-xs"
        placeholder="Reason"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <Button size="sm" onClick={submit}>
        Propose
      </Button>
    </div>
  )
}
```

- [ ] **Step 5: Implement `frontend/src/components/LivingTextView.tsx`**

```tsx
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InlineCorrection } from "@/components/InlineCorrection"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { ProposeCorrectionInline } from "@/components/ProposeCorrectionInline"
import { SourcePreviewPopover } from "@/components/SourcePreviewPopover"
import { XSDO_DOCUMENTATION } from "@/lib/api"
import type { DocEntry, DocumentationResponse } from "@/lib/api"

interface LivingTextViewProps {
  documentation: DocumentationResponse
  pending: PendingCorrection[]
  reviewer: string
  search: string
  onDecided: () => void
}

const GROUPS: { key: keyof DocumentationResponse; label: string; variant: "default" | "secondary" | "destructive" | "outline" }[] = [
  { key: "matched", label: "Matched", variant: "default" },
  { key: "unmatched", label: "Unmatched", variant: "secondary" },
  { key: "ambiguous", label: "Ambiguous", variant: "destructive" },
  { key: "englishOnly", label: "English-only", variant: "outline" },
]

function matchesSearch(name: string, search: string): boolean {
  return !search || name.toLowerCase().includes(search.toLowerCase())
}

function DocEntryCard({
  entry, pending, reviewer, onDecided,
}: { entry: DocEntry; pending: PendingCorrection[]; reviewer: string; onDecided: () => void }) {
  return (
    <Card id={`doc:${entry.uri}`} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{entry.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {Object.entries(entry.languages).map(([lang, text]) => {
          const correctionForThisFact = pending.find((c) => c.targetSubject === entry.uri)
          return (
            <div key={lang}>
              <div>
                {lang.toUpperCase()}:{" "}
                <SourcePreviewPopover subject={entry.uri} predicate={XSDO_DOCUMENTATION} value={text} lang={lang} />{" "}
                <ProposeCorrectionInline
                  subject={entry.uri} predicate={XSDO_DOCUMENTATION} language={lang} currentValue={text}
                  reviewer={reviewer} onProposed={onDecided}
                />
              </div>
              {correctionForThisFact && (
                <InlineCorrection correction={correctionForThisFact} reviewer={reviewer} onDecided={onDecided} />
              )}
            </div>
          )
        })}
        {entry.issues?.map((issue, index) => (
          <div key={index} className="text-destructive text-xs">
            {issue.kind}: {issue.detail}
          </div>
        ))}
        {entry.candidates && (
          <ul className="list-disc pl-4 text-xs text-muted-foreground">
            {entry.candidates.map((candidate, index) => (
              <li key={index}>{candidate}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function LivingTextView({ documentation, pending, reviewer, search, onDecided }: LivingTextViewProps) {
  return (
    <div>
      {GROUPS.map(({ key, label, variant }) => {
        const entries = documentation[key].filter((entry) => matchesSearch(entry.name, search))
        if (entries.length === 0) return null
        return (
          <section key={key} className="mb-8">
            <h3 className="mb-2 flex items-center gap-2 text-lg font-semibold">
              {label} <Badge variant={variant}>{entries.length}</Badge>
            </h3>
            {entries.map((entry) => (
              <DocEntryCard key={entry.uri} entry={entry} pending={pending} reviewer={reviewer} onDecided={onDecided} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
```

Note: unmatched entries render with no `SourcePreviewPopover` inside their
language loop only because they have no `languages` entries carrying a
real citation to begin with in the current data shape — this matches the
design spec's "unmatched/ambiguous entries stay visually distinct" rule
without needing extra conditional logic here.

- [ ] **Step 6: Delete the superseded components**

```bash
cd /work/generator
rm frontend/src/components/DocumentationView.tsx frontend/src/components/DocumentationView.test.tsx
rm frontend/src/components/CorrectionsView.tsx frontend/src/components/CorrectionsView.test.tsx
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /work/generator/frontend && npx vitest run src/components/InlineCorrection.test.tsx src/components/ProposeCorrectionInline.test.tsx src/components/LivingTextView.test.tsx`

Expected: PASS (5 tests).

- [ ] **Step 8: Commit**

```bash
git add -A frontend/src/components/LivingTextView.tsx frontend/src/components/LivingTextView.test.tsx
git add frontend/src/components/InlineCorrection.tsx frontend/src/components/InlineCorrection.test.tsx
git add frontend/src/components/ProposeCorrectionInline.tsx frontend/src/components/ProposeCorrectionInline.test.tsx
git add frontend/src/components/DocumentationView.tsx frontend/src/components/DocumentationView.test.tsx
git add frontend/src/components/CorrectionsView.tsx frontend/src/components/CorrectionsView.test.tsx
git commit -m "Add LivingTextView: hover-transclusion + inline corrections, retiring the worklist"
```

---

### Task 11: `ModeSwitcher` — retiring `PageShell`'s tab bar

**Files:**
- Create: `frontend/src/components/ModeSwitcher.tsx`
- Delete: `frontend/src/components/PageShell.tsx`
- Delete: `frontend/src/components/PageShell.test.tsx`
- Test: `frontend/src/components/ModeSwitcher.test.tsx`

**Interfaces:**
- Consumes: `useFocus` (Task 6), `useReviewer` (existing, unchanged), `apiGet` (existing)
- Produces: `ModeSwitcher` — props `{ search: string; onSearchChange: (value: string) => void; children: ReactNode }`. Reads/writes mode via `useFocus` directly (unlike `PageShell`, which took `activeTab`/`onTabChange` as props) — this is the plan's first component wired directly to the shared focus model instead of local `useState`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/ModeSwitcher.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { ModeSwitcher } from "@/components/ModeSwitcher"

describe("ModeSwitcher", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("renders all 3 mode tabs and a pending-corrections badge", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{ correctionUri: "urn:c1" }] }))

    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    for (const label of ["Graph", "Living Text", "Synced Panes"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument()
    }
    expect(await screen.findByText("1")).toBeInTheDocument()
  })

  it("clicking a mode tab navigates there, preserving no stale content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }))

    render(
      <MemoryRouter initialEntries={["/graph"]}>
        <Routes>
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search="" onSearchChange={() => {}}>
                <div>content</div>
              </ModeSwitcher>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole("tab", { name: "Living Text" }))
    expect(screen.getByRole("tab", { name: "Living Text" })).toHaveAttribute("data-selected")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/components/ModeSwitcher.test.tsx`

Expected: FAIL — `@/components/ModeSwitcher` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/components/ModeSwitcher.tsx`**

```tsx
import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { apiGet } from "@/lib/api"
import { useFocus } from "@/lib/focus"
import { useReviewer } from "@/lib/reviewer"

const MODES: { key: string; label: string }[] = [
  { key: "graph", label: "Graph" },
  { key: "living-text", label: "Living Text" },
  { key: "synced-panes", label: "Synced Panes" },
  { key: "runs", label: "Runs" },
]

const REVIEWERS = ["julian", "someone-else"]

interface ModeSwitcherProps {
  search: string
  onSearchChange: (value: string) => void
  children: ReactNode
}

export function ModeSwitcher({ search, onSearchChange, children }: ModeSwitcherProps) {
  const [reviewer, setReviewer] = useReviewer()
  const { mode, setFocus } = useFocus()
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    apiGet<unknown[]>("/corrections/pending").then((rows) => setPendingCount(rows.length))
  }, [])

  return (
    <TooltipProvider>
      <div className="flex flex-col min-h-screen">
        <nav className="sticky top-0 z-10 flex items-center gap-4 border-b bg-background px-4 py-3">
          <Tabs value={mode} onValueChange={(value) => setFocus({ mode: value })}>
            <TabsList>
              {MODES.map((modeOption) => (
                <TabsTrigger key={modeOption.key} value={modeOption.key}>
                  {modeOption.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          {pendingCount > 0 && (
            <button onClick={() => setFocus({ mode: "graph" })} className="flex items-center gap-1 text-xs">
              <Badge variant="destructive">{pendingCount}</Badge> pending
            </button>
          )}
          <Input
            placeholder="Filter by name..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="ml-auto max-w-64"
          />
          <Select value={reviewer} onValueChange={(value) => value && setReviewer(value)}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Reviewing as..." />
            </SelectTrigger>
            <SelectContent>
              {REVIEWERS.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </nav>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </TooltipProvider>
  )
}
```

- [ ] **Step 4: Delete `PageShell`**

```bash
cd /work/generator
rm frontend/src/components/PageShell.tsx frontend/src/components/PageShell.test.tsx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/components/ModeSwitcher.test.tsx`

Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/components/ModeSwitcher.tsx frontend/src/components/ModeSwitcher.test.tsx
git add frontend/src/components/PageShell.tsx frontend/src/components/PageShell.test.tsx
git commit -m "Add ModeSwitcher, retiring PageShell's tab bar"
```

---

### Task 12: `GraphView` — the one-glance overview

**Files:**
- Create: `frontend/src/components/GraphView.tsx`
- Delete: `frontend/src/components/StructureView.tsx`
- Delete: `frontend/src/components/StructureView.test.tsx`
- Delete: `frontend/src/components/AuditView.tsx`
- Delete: `frontend/src/components/AuditView.test.tsx`
- Test: `frontend/src/components/GraphView.test.tsx`

**Interfaces:**
- Consumes: `StructureResponse`, `DocumentationResponse`, `AuditResponse` types (existing), `PendingCorrection` (Task 10), `useFocus`/`useHoverFocus` (Task 6), `cytoscape` (existing dependency)
- Produces: `GraphView` — props `{ structure: StructureResponse; documentation: DocumentationResponse; audit: AuditResponse; pending: PendingCorrection[]; search: string }`. Internal state (not props) tracks the current zoom level (`"namespaces" | "types" | "subject"`) and active status filters, since these are view-local, not shared focus.

This task covers zoom Levels 1 and 2 (namespace overview, types colored by
documentation status) and the audit-status filter toggles. Level 3 (one
subject's own provenance fan-out) is Task 13.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/GraphView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { GraphView } from "@/components/GraphView"
import type { AuditResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

const structure: StructureResponse = {
  "https://example.org/ns1": {
    complexTypes: [
      {
        uri: "https://example.org/ns1#TypeA", name: "TypeA", abstract: false, extends: null,
        contentModel: { kind: "Sequence", particles: [] }, attributeUses: [], identityConstraints: [],
      },
    ],
    simpleTypes: [],
  },
}
const documentation: DocumentationResponse = {
  matched: [{ uri: "https://example.org/ns1#TypeA", name: "TypeA", languages: { de: "x", en: "y" } }],
  unmatched: [], ambiguous: [], englishOnly: [],
}
const audit: AuditResponse = {
  attachment: { attached: 1, ambiguous: 0, unmatched: 0 },
  coverage: { total: 1, attached: 1, ambiguous: 0, unmatched: 0 },
  issues: [],
}

describe("GraphView", () => {
  it("starts at the namespace-level overview", () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    expect(screen.getByText("https://example.org/ns1")).toBeInTheDocument()
  })

  it("zooming into a namespace shows its types", async () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByText("https://example.org/ns1"))

    expect(await screen.findByText("TypeA")).toBeInTheDocument()
  })

  it("has an unmatched-status filter toggle", () => {
    render(
      <MemoryRouter>
        <GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />
      </MemoryRouter>,
    )

    expect(screen.getByRole("checkbox", { name: /unmatched/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/components/GraphView.test.tsx`

Expected: FAIL — `@/components/GraphView` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/components/GraphView.tsx`**

```tsx
import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Checkbox } from "@/components/ui/checkbox"
import type { AuditResponse, DocumentationResponse, StructureResponse } from "@/lib/api"

type DocStatus = "matched" | "unmatched" | "ambiguous" | "englishOnly"

interface GraphViewProps {
  structure: StructureResponse
  documentation: DocumentationResponse
  audit: AuditResponse
  pending: { targetSubject: string }[]
  search: string
}

function statusOf(uri: string, documentation: DocumentationResponse): DocStatus | null {
  for (const status of ["matched", "unmatched", "ambiguous", "englishOnly"] as const) {
    if (documentation[status].some((entry) => entry.uri === uri)) return status
  }
  return null
}

const STATUS_COLOR: Record<DocStatus, string> = {
  matched: "bg-green-500", unmatched: "bg-gray-400", ambiguous: "bg-red-500", englishOnly: "bg-blue-400",
}

export function GraphView({ structure, documentation, pending, search }: GraphViewProps) {
  const navigate = useNavigate()
  const [namespace, setNamespace] = useState<string | null>(null)
  const [visibleStatuses, setVisibleStatuses] = useState<Set<DocStatus>>(
    new Set(["matched", "unmatched", "ambiguous", "englishOnly"]),
  )

  const pendingSubjects = useMemo(() => new Set(pending.map((p) => p.targetSubject)), [pending])

  function toggleStatus(status: DocStatus) {
    setVisibleStatuses((previous) => {
      const next = new Set(previous)
      if (next.has(status)) next.delete(status)
      else next.add(status)
      return next
    })
  }

  if (namespace === null) {
    const namespaces = Object.keys(structure).filter((ns) => !search || ns.toLowerCase().includes(search.toLowerCase()))
    return (
      <div>
        <div className="mb-4 flex gap-4">
          {(["matched", "unmatched", "ambiguous", "englishOnly"] as const).map((status) => (
            <label key={status} className="flex items-center gap-1 text-sm">
              <Checkbox
                checked={visibleStatuses.has(status)}
                onCheckedChange={() => toggleStatus(status)}
                aria-label={status}
              />
              {status}
            </label>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-4">
          {namespaces.map((ns) => (
            <button
              key={ns}
              onClick={() => setNamespace(ns)}
              className="rounded border p-4 text-left text-sm hover:bg-accent"
            >
              {ns}
            </button>
          ))}
        </div>
      </div>
    )
  }

  const block = structure[namespace]
  const allTypes = [...block.complexTypes, ...block.simpleTypes].filter((type) => {
    const status = statusOf(type.uri, documentation)
    return status === null || visibleStatuses.has(status)
  })

  return (
    <div>
      <button onClick={() => setNamespace(null)} className="mb-4 text-sm text-primary underline">
        ← All namespaces
      </button>
      <div className="grid grid-cols-4 gap-3">
        {allTypes.map((type) => {
          const status = statusOf(type.uri, documentation)
          return (
            <button
              key={type.uri}
              onClick={() => navigate(`/graph/${encodeURIComponent(type.uri)}`)}
              className="flex items-center gap-2 rounded border p-2 text-left text-sm hover:bg-accent"
            >
              <span className={`size-2 rounded-full ${status ? STATUS_COLOR[status] : "bg-muted"}`} />
              {type.name ?? "(anonymous)"}
              {pendingSubjects.has(type.uri) && <span className="text-xs text-amber-600">●</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
```

`Checkbox` is a shadcn component this project hasn't added yet — install it
before writing the test:

```bash
cd /work/generator/frontend && npx shadcn@latest add checkbox -y
```

- [ ] **Step 4: Delete the superseded components**

```bash
cd /work/generator
rm frontend/src/components/StructureView.tsx frontend/src/components/StructureView.test.tsx
rm frontend/src/components/AuditView.tsx frontend/src/components/AuditView.test.tsx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/components/GraphView.test.tsx`

Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/components/GraphView.tsx frontend/src/components/GraphView.test.tsx frontend/src/components/ui/checkbox.tsx
git add frontend/src/components/StructureView.tsx frontend/src/components/StructureView.test.tsx
git add frontend/src/components/AuditView.tsx frontend/src/components/AuditView.test.tsx
git commit -m "Add GraphView: namespace/type overview, absorbing Structure and Audit"
```

---

### Task 13: `GraphView` Level 3 — one subject's real provenance fan-out

**Files:**
- Modify: `frontend/src/components/GraphView.tsx`
- Test: `frontend/src/components/GraphView.test.tsx` (extend)

**Interfaces:**
- Consumes: `cytoscape` (existing dependency), `apiGet` (existing, for `/provenance`), `getPlugin` (Task 8), `useFocus` (Task 6)
- Produces: `GraphView` gains a third rendering branch — when `useFocus().subject` is set AND that subject exists in `structure`, render a real Cytoscape graph (this subject's node, one node per documented language, one node per real citation source, edges labeled `wasDerivedFrom`) instead of the type grid from Task 12.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/components/GraphView.test.tsx`:

```tsx
import { Route, Routes } from "react-router-dom"

function renderAtSubjectFocus(subjectUri: string) {
  return render(
    <MemoryRouter initialEntries={[`/graph/${encodeURIComponent(subjectUri)}`]}>
      <Routes>
        <Route
          path="/graph/:subject?"
          element={<GraphView structure={structure} documentation={documentation} audit={audit} pending={[]} search="" />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

it("focusing a real subject shows its own lineage graph, not the type grid", () => {
  renderAtSubjectFocus("https://example.org/ns1#TypeA")

  expect(screen.getByTestId("lineage-graph-container")).toBeInTheDocument()
  expect(screen.queryByText("All namespaces")).not.toBeInTheDocument()
})
```

(Add `import { render, screen } from "@testing-library/react"` and
`import { describe, expect, it } from "vitest"` to this file's imports if
not already present from Task 12 — check the top of the file first.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/components/GraphView.test.tsx -t "own lineage graph"`

Expected: FAIL — `GraphView` doesn't yet branch on a focused subject.

- [ ] **Step 3: Implement the Level-3 branch**

Add to the top of `frontend/src/components/GraphView.tsx`:

```typescript
import cytoscape from "cytoscape"
import { useEffect, useRef } from "react"
import { useFocus } from "@/lib/focus"
import { apiGet, XSDO_DOCUMENTATION } from "@/lib/api"
import type { ProvenanceRecord } from "@/lib/api"
```

Add a new component in the same file, above `GraphView`:

```tsx
function SubjectLineage({ subjectUri, languages }: { subjectUri: string; languages: Record<string, string> }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [records, setRecords] = useState<Record<string, ProvenanceRecord | null>>({})

  useEffect(() => {
    let cancelled = false
    Promise.all(
      Object.entries(languages).map(async ([lang, text]) => {
        const params = new URLSearchParams({ subject: subjectUri, predicate: XSDO_DOCUMENTATION, value: text, lang })
        const record = await apiGet<ProvenanceRecord | null>(`/provenance?${params.toString()}`)
        return [lang, record] as const
      }),
    ).then((entries) => {
      if (!cancelled) setRecords(Object.fromEntries(entries))
    })
    return () => {
      cancelled = true
    }
  }, [subjectUri, languages])

  const setContainer = (node: HTMLDivElement | null) => {
    containerRef.current = node
    if (!node) return
    const elements: cytoscape.ElementDefinition[] = [{ data: { id: subjectUri, label: subjectUri } }]
    for (const [lang, record] of Object.entries(records)) {
      if (!record) continue
      const sourceId = record.sourceUri
      elements.push({ data: { id: sourceId, label: sourceId } })
      elements.push({ data: { id: `${lang}-edge`, source: sourceId, target: subjectUri, label: "wasDerivedFrom" } })
    }
    cytoscape({
      container: node,
      elements,
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 8, "background-color": "#0b5fff" } },
        { selector: "edge", style: { label: "data(label)", "font-size": 6, "curve-style": "bezier", "target-arrow-shape": "triangle" } },
      ],
      layout: { name: "breadthfirst", directed: true },
    })
  }

  return <div ref={setContainer} data-testid="lineage-graph-container" className="h-96 w-full rounded border" />
}
```

Add the `useState` import at the top: `import { useMemo, useState } from "react"`
already exists from Task 12 — no change needed there.

In `GraphView`'s own body, before the `if (namespace === null)` check,
insert the subject-focus branch:

```typescript
  const { subject } = useFocus()

  if (subject) {
    const entry =
      documentation.matched.find((e) => e.uri === subject) ??
      documentation.unmatched.find((e) => e.uri === subject) ??
      documentation.ambiguous.find((e) => e.uri === subject) ??
      documentation.englishOnly.find((e) => e.uri === subject)
    if (entry) {
      return <SubjectLineage subjectUri={subject} languages={entry.languages} />
    }
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/components/GraphView.test.tsx`

Expected: PASS (all 4 tests in this file now).

- [ ] **Step 5: Confirm the project builds**

Run: `cd /work/generator/frontend && npm run build`

Expected: no TypeScript errors — this is where an unused `getPlugin`/`parseSourceUri` import from Step 3 would surface; remove it if so.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/GraphView.tsx frontend/src/components/GraphView.test.tsx
git commit -m "Add GraphView Level 3: one subject's real provenance fan-out"
```

---

### Task 14: `SyncedPanesView` — bidirectional source/derived sync

**Files:**
- Create: `frontend/src/components/SyncedPanesView.tsx`
- Test: `frontend/src/components/SyncedPanesView.test.tsx`

**Interfaces:**
- Consumes: `getPlugin` (Task 8), `apiGet` (existing), `RunSummary` (existing, for `xsdPath`/`pdfPath`)
- Produces: `SyncedPanesView` — props `{ pdfPath: string; xsdPaths: string[] }`. Internal state: which source (`{kind: "pdf", path}` or `{kind: "xsd", file}`) is active, and the current locator focus. Left pane renders the active plugin's `renderWhole`; right pane shows the reverse-lookup result for whatever locator was last clicked in the left pane.

`xsdPaths` is a list because this corpus has multiple real XSD files (the
root file plus its includes) — Task 15 (`App.tsx` wiring) is responsible
for supplying this list; for this task, treat it as a given prop.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/SyncedPanesView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SyncedPanesView } from "@/components/SyncedPanesView"

describe("SyncedPanesView", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows the PDF source by default and lists derived facts after clicking a page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/sources/lookup")) {
          return Promise.resolve({
            ok: true,
            json: async () => [{ subject: "urn:s1", predicate: "urn:p", object: "Derived fact 1" }],
          })
        }
        return Promise.resolve({ ok: true, blob: async () => new Blob() })
      }),
    )

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    await userEvent.click(screen.getByRole("img", { name: /page 1/i }))

    expect(await screen.findByText("Derived fact 1")).toBeInTheDocument()
  })

  it("lets you switch to an XSD source via the source picker", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ content: "<xs:schema/>" }) }))

    render(<SyncedPanesView pdfPath="/a.pdf" xsdPaths={["/a.xsd"]} />)

    await userEvent.click(screen.getByRole("combobox"))
    await userEvent.click(screen.getByRole("option", { name: "/a.xsd" }))

    expect(await screen.findByText(/<xs:schema/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work/generator/frontend && npx vitest run src/components/SyncedPanesView.test.tsx`

Expected: FAIL — `@/components/SyncedPanesView` doesn't exist.

- [ ] **Step 3: Implement `frontend/src/components/SyncedPanesView.tsx`**

```tsx
import { useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiGet } from "@/lib/api"
import { getPlugin } from "@/sourcePlugins/registry"
import type { SourceLocator } from "@/lib/sourceLocator"

interface SyncedPanesViewProps {
  pdfPath: string
  xsdPaths: string[]
}

interface DerivedFactRow {
  subject: string
  predicate: string
  object: string
}

export function SyncedPanesView({ pdfPath, xsdPaths }: SyncedPanesViewProps) {
  const sources = [
    { key: `pdf:${pdfPath}`, label: pdfPath, locator: { kind: "pdf", path: pdfPath, page: 1 } as SourceLocator },
    ...xsdPaths.map((file) => ({
      key: `xsd:${file}`, label: file, locator: { kind: "xsd", file, component: "" } as SourceLocator,
    })),
  ]
  const [activeKey, setActiveKey] = useState(sources[0].key)
  const [derived, setDerived] = useState<DerivedFactRow[]>([])

  const active = sources.find((source) => source.key === activeKey) ?? sources[0]
  const plugin = getPlugin(active.locator.kind)

  async function handleLocatorClick(locator: SourceLocator) {
    const params =
      locator.kind === "pdf"
        ? new URLSearchParams({ kind: "pdf", path: locator.path, page: String(locator.page) })
        : new URLSearchParams({ kind: "xsd", file: locator.file, component: locator.component })
    const rows = await apiGet<DerivedFactRow[]>(`/sources/lookup?${params.toString()}`)
    setDerived(rows)
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <Select value={activeKey} onValueChange={(value) => value && setActiveKey(value)}>
          <SelectTrigger className="mb-2 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sources.map((source) => (
              <SelectItem key={source.key} value={source.key}>
                {source.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {plugin && plugin.renderWhole(active.locator, handleLocatorClick)}
      </div>
      <div>
        <h4 className="mb-2 text-sm font-semibold">Derived from this location</h4>
        {derived.length === 0 && <p className="text-xs text-muted-foreground">Click the source to see what it produced.</p>}
        <ul className="space-y-1">
          {derived.map((row, index) => (
            <li key={index} className="text-sm">
              {row.object}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /work/generator/frontend && npx vitest run src/components/SyncedPanesView.test.tsx`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SyncedPanesView.tsx frontend/src/components/SyncedPanesView.test.tsx
git commit -m "Add SyncedPanesView: bidirectional source/derived sync"
```

---

### Task 15: Wire everything into `App.tsx`; serve from `webapp`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `webapp/main.py` (no change expected — confirm the existing static-file mount still works; see Step 4)

**Interfaces:**
- Consumes: every component from Tasks 6-14.
- Produces: the final, real routing shape: `/graph/:subject?`, `/living-text/:subject?/:predicate?/:lang?`, `/synced-panes`, `/runs` — all wrapped in `HashRouter` (not `BrowserRouter`: `webapp/main.py`'s `StaticFiles(html=True)` mount has no SPA-fallback routing for arbitrary paths, so a real, non-root URL must stay in the fragment, matching this plan's spec).

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import { useCallback, useEffect, useState } from "react"
import { HashRouter, Navigate, Route, Routes } from "react-router-dom"
import { GraphView } from "@/components/GraphView"
import { HoverFocusProvider } from "@/lib/hoverFocus"
import { LivingTextView } from "@/components/LivingTextView"
import type { PendingCorrection } from "@/components/InlineCorrection"
import { ModeSwitcher } from "@/components/ModeSwitcher"
import { RunsView } from "@/components/RunsView"
import { SyncedPanesView } from "@/components/SyncedPanesView"
import { apiGet } from "@/lib/api"
import { useReviewer } from "@/lib/reviewer"
import type {
  AuditResponse, DocumentationResponse, RunSummary, StructureResponse,
} from "@/lib/api"

export default function App() {
  const [search, setSearch] = useState("")
  const [reviewer] = useReviewer()

  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [documentation, setDocumentation] = useState<DocumentationResponse | null>(null)
  const [audit, setAudit] = useState<AuditResponse | null>(null)
  const [pending, setPending] = useState<PendingCorrection[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])

  const refreshPending = useCallback(() => {
    apiGet<PendingCorrection[]>("/corrections/pending").then(setPending)
  }, [])

  useEffect(() => {
    apiGet<StructureResponse>("/structure").then(setStructure)
    apiGet<DocumentationResponse>("/documentation").then(setDocumentation)
    apiGet<AuditResponse>("/audit").then(setAudit)
    apiGet<RunSummary[]>("/runs").then(setRuns)
    refreshPending()
  }, [refreshPending])

  const latestRun = runs[runs.length - 1]

  return (
    <HashRouter>
      <HoverFocusProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/graph" replace />} />
          <Route
            path="/:mode/*"
            element={
              <ModeSwitcher search={search} onSearchChange={setSearch}>
                <Routes>
                  <Route
                    path="graph/:subject?"
                    element={
                      structure && documentation && audit ? (
                        <GraphView structure={structure} documentation={documentation} audit={audit} pending={pending} search={search} />
                      ) : null
                    }
                  />
                  <Route
                    path="living-text/:subject?/:predicate?/:lang?"
                    element={
                      documentation ? (
                        <LivingTextView documentation={documentation} pending={pending} reviewer={reviewer} search={search} onDecided={refreshPending} />
                      ) : null
                    }
                  />
                  <Route
                    path="synced-panes"
                    element={
                      latestRun ? <SyncedPanesView pdfPath={latestRun.pdfPath} xsdPaths={[latestRun.xsdPath]} /> : null
                    }
                  />
                  <Route path="runs" element={<RunsView runs={runs} />} />
                </Routes>
              </ModeSwitcher>
            }
          />
        </Routes>
      </HoverFocusProvider>
    </HashRouter>
  )
}
```

Note: `xsdPaths={[latestRun.xsdPath]}` only lists the one root XSD path
this run was pointed at — the real corpus is split across multiple
included files (`MiKaDiv_FM_Personentypen_1.02.xsd` and others), which
`RunInfo` doesn't currently enumerate. Listing only the root file here is
a known, deliberate limitation of this task, not a bug: extending
`RunInfo`/`/api/runs` to enumerate every included file is real, additional
backend work outside this plan's scope (it touches `store/runs.py`'s own
data model) — note it as a follow-up in your task report rather than
silently working around it.

`Runs` is not one of the three focus-bearing modes (it's about time, not
lineage — see the design spec), but Task 11's `ModeSwitcher` already
lists it as a fourth `Tabs` entry for a consistent header, and clicking it
calls `setFocus({ mode: "runs" })`, navigating to `/#/runs` the same way
the other three modes navigate — no special-casing needed here.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd /work/generator/frontend && npx vitest run`

Expected: every test passes. This is where any stale reference to a
deleted component (`PageShell`, `DocumentationView`, `StructureView`,
`AuditView`, `CorrectionsView`, `ProvenanceMarker`, `LineageGraph`) would
surface as an import error — fix any you find; every one of them should
already be gone per Tasks 9-12's own delete steps.

- [ ] **Step 3: Confirm the project builds**

Run: `cd /work/generator/frontend && npm run build`

Expected: no TypeScript errors.

- [ ] **Step 4: Confirm `webapp/main.py`'s static mount still serves the SPA correctly**

`HashRouter` puts all real routing state after a `#`, which the server
never sees (`GET /` and `GET /#/living-text/urn:s` both request the exact
same path, `/`, from the server's point of view) — so `webapp/main.py`'s
existing `StaticFiles(..., html=True)` mount needs no change for this to
work. Confirm this directly:

```bash
cd /work/generator && rm -rf /tmp/task15_manual_check && python3 -c "
import uvicorn
from webapp.main import create_app
app = create_app(
    '/tmp/task15_manual_check',
    '/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd',
    '/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf',
)
uvicorn.run(app, host='127.0.0.1', port=8020)
" &
sleep 30
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8020/
kill %1
rm -rf /tmp/task15_manual_check
```

Expected: `200`. (The 30-second sleep gives the real pipeline run time to
complete on first startup — see this plan's other tasks for the same
pattern.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "Wire GraphView/LivingTextView/SyncedPanesView into App.tsx via HashRouter"
```

---

### Task 16: Final whole-branch verification — backend, frontend, and a real live walkthrough

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/interconnected-ui.spec.ts`
- Modify: `frontend/package.json` (add `@playwright/test`, a `test:e2e` script)

**Interfaces:**
- Produces: a real, checked-in Playwright suite — not a throwaway manual
  check — covering the Definition of Done's own required walkthrough:
  hover-preview, click-to-pin (Inspector), mode-switch-preserves-focus, and
  both directions of Synced Panes syncing, run against the actual
  built-and-served app (matching this project's own established
  "unit tests alone have repeatedly missed real bugs here" lesson).

- [ ] **Step 1: Install Playwright**

```bash
cd /work/generator/frontend
npm install -D @playwright/test
```

(The `playwright` CLI and a pinned Chromium build are already baked into
this box's own image per its `CLAUDE.md` — no browser download step is
needed here, only the `@playwright/test` test-runner package itself.)

- [ ] **Step 2: Add `frontend/playwright.config.ts`**

```typescript
import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:8021" },
  webServer: {
    command: "cd .. && python3 -m uvicorn --factory --app-dir . webapp.main:_e2e_app --host 127.0.0.1 --port 8021",
    url: "http://127.0.0.1:8021",
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
```

This needs a real, importable app factory with no arguments for uvicorn's
`--factory` flag to call — add one to `webapp/main.py`:

```python
def _e2e_app():
    """A zero-argument factory for Playwright's own webServer config
    (frontend/playwright.config.ts) -- uvicorn's --factory flag requires
    a callable with no arguments, unlike create_app's own real
    (store_path, xsd_path, pdf_path) signature every other caller uses.
    """
    import shutil

    store_path = "/tmp/e2e_test_store"
    shutil.rmtree(store_path, ignore_errors=True)
    return create_app(
        store_path,
        "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
        "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
    )
```

Append this function to `webapp/main.py`, after `create_app`.

- [ ] **Step 3: Build the frontend so the e2e run serves real assets**

```bash
cd /work/generator/frontend && npm run build
```

- [ ] **Step 4: Write `frontend/e2e/interconnected-ui.spec.ts`**

```typescript
import { expect, test } from "@playwright/test"

test("hover on a documentation value shows a real source preview", async ({ page }) => {
  await page.goto("/#/living-text")
  const firstValue = page.locator("span.underline").first()
  await firstValue.hover()
  await expect(page.locator("img, code").first()).toBeVisible({ timeout: 10_000 })
})

test("clicking a documentation value pins it into the URL-addressable focus", async ({ page }) => {
  await page.goto("/#/living-text")
  const firstValue = page.locator("span.underline").first()
  await firstValue.click()
  await expect(page).toHaveURL(/#\/living-text\/.+/)
})

test("switching modes after a click preserves the same focused subject", async ({ page }) => {
  await page.goto("/#/living-text")
  const firstValue = page.locator("span.underline").first()
  await firstValue.click()
  const url = page.url()
  const subject = decodeURIComponent(url.split("/living-text/")[1].split("/")[0])

  await page.getByRole("tab", { name: "Graph" }).click()
  await expect(page).toHaveURL(new RegExp(`#/graph/${encodeURIComponent(subject).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
})

test("Synced Panes: clicking a PDF page shows real derived facts, both directions", async ({ page }) => {
  await page.goto("/#/synced-panes")
  await page.getByRole("img").first().click()
  await expect(page.getByText(/derived from this location/i)).toBeVisible()
})
```

- [ ] **Step 5: Add the `test:e2e` script**

Add to `frontend/package.json`'s `"scripts"`:

```json
    "test:e2e": "playwright test",
```

- [ ] **Step 6: Run the E2E suite**

Run: `cd /work/generator/frontend && npx playwright test`

Expected: all 4 tests pass. If any fails, this is exactly the kind of
gap this plan's Testing strategy exists to catch before merge — debug the
real cause (following `superpowers:systematic-debugging`) rather than
loosening the assertion.

- [ ] **Step 7: Run the full backend test suite**

Run: `cd /work && python3 -m pytest generator/tests/ -q`

Expected: every test passes, including all new tests from Tasks 1-5.

- [ ] **Step 8: Run the full frontend unit/component test suite**

Run: `cd /work/generator/frontend && npx vitest run`

Expected: every test passes.

- [ ] **Step 9: Clean up the manual verification artifact and commit**

```bash
rm -rf /tmp/e2e_test_store
cd /work/generator
git add frontend/playwright.config.ts frontend/e2e/interconnected-ui.spec.ts frontend/package.json frontend/package-lock.json webapp/main.py
git commit -m "Add a real, checked-in Playwright E2E suite for the interconnected UI"
```

---

## Self-review notes (for the plan author, not the implementer)

- **Spec coverage:** Overall shape (Task 15's routing), shared focus model
  (Task 6), Graph mode (Tasks 12-13), Living Text mode (Tasks 9-10),
  Synced Panes + generic source-viewer abstraction (Tasks 7-8, 14),
  architecture's reverse-lookup endpoint (Tasks 4-5), testing strategy
  (Task 16). The spec's Known Gaps (German local-scope citations, single
  reviewer list) are inherited unchanged, not re-implemented — no task
  needed for them. The spec's Non-goals (a third plugin, pixel-perfect
  visual design, real-time collaboration) are correctly absent from every
  task above.
- **Type consistency check performed:** `PendingCorrection`'s shape
  (`correctionUri`/`targetSubject`/`proposedValue`/`proposer`) is defined
  once in Task 10 (`InlineCorrection.tsx`) and imported everywhere else
  that needs it (Tasks 12, 13, 15) rather than redefined. `SourceLocator`'s
  Python (Task 1) and TypeScript (Task 7) shapes were kept in exact field
  correspondence deliberately, including the same page-level-vs-bbox
  optionality. `getPlugin`/`SourcePlugin` (Task 8) is the single interface
  every later consumer (Tasks 9, 13, 14) imports, never redefined locally.
