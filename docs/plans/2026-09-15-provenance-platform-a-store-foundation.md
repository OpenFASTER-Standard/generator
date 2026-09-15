# Provenance Platform — Plan A: Store, Provenance & Citations Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the persistent, embedded Oxigraph-backed store that replaces
the static `report.html`: named-graph-per-run history with real diffing,
RDF-star provenance records, and real inline citations (PDF page crops,
XSD source fragments).

**Architecture:** One Oxigraph store file, opened as an `rdflib.Dataset`
(via `oxrdflib`) so existing `rdflib`-based code keeps working. Each
extraction run writes an immutable named graph; provenance is RDF-star
quoted triples in a dedicated `prov` graph; citations are content blobs
referenced by URI from provenance records.

**Tech Stack:** `pyoxigraph`, `oxrdflib`, `rdflib` (already a dependency),
`pdfplumber` (already a dependency), `xmlschema` (already a dependency).

**Spec:** `generator/docs/specs/2026-09-15-provenance-and-review-platform-design.md`

## Global Constraints

- **Two different working directories matter here, and mixing them up is
  a real, previously-hit bug (confirmed live while writing this plan)**:
  `pip install`/git commands run from `/work/generator` (where
  `pyproject.toml`/`.git` live). Pytest runs from `/work` as
  `python3 -m pytest generator/tests/...` — the real fixture files live
  at `/work/ontologies/...`, so any test using a *relative* fixture path
  would silently resolve wrong under `/work/generator`'s own cwd instead.
  New tests in this plan sidestep the ambiguity entirely by using
  *absolute* `/work/ontologies/...` paths for real fixtures, matching
  this repo's own established fix for the same class of bug (see
  `generator/docs/plans/2026-09-15-generator-output-report.md`'s Task 4).
- New packages (`store`, `provenance`, `citations`) must be added to
  `pyproject.toml`'s `[tool.setuptools.packages.find]` `include` list,
  and `pip install -e . --break-system-packages` re-run (from
  `/work/generator`), or `import store` etc. fails with
  `ModuleNotFoundError` even after the files exist on disk (the
  editable-install finder uses a hardcoded package-name map baked in at
  install time — a real, previously-hit gotcha in this repo).
- `extraction/`'s existing code, signatures, and tests are never modified
  in this plan.
- No placeholder/fabricated data: every citation and provenance record
  this plan produces must be built from real inputs (the real
  `ontologies/mikadiv-fm/sources/...` XSD/PDF fixtures already used by
  `extraction/`'s own tests), not synthetic strings standing in for them,
  wherever a test exercises the real corpus.
- Real subject/predicate URIs throughout use the existing
  `XSDO = Namespace("https://purl.openfaster.org/xsdo/")` convention
  already established in `reporting/data.py` and `extraction/`.

---

### Task 1: Dependencies + `store/database.py` — open/create the store

**Files:**
- Modify: `pyproject.toml`
- Create: `store/__init__.py`
- Create: `store/database.py`
- Test: `tests/store/test_database.py`
- Test: `tests/store/__init__.py` (empty, package marker)

**Interfaces:**
- Produces: `store.database.open_store(path: str, create: bool = False) -> rdflib.Dataset`

- [ ] **Step 1: Add new dependencies and package includes**

Edit `pyproject.toml`'s `dependencies` list to add:

```toml
    "pyoxigraph>=0.5",
    "oxrdflib>=0.5",
```

Edit `[tool.setuptools.packages.find]`'s `include` list to:

```toml
include = ["extraction*", "generation*", "equivalence*", "ingestion*", "reporting*", "store*", "provenance*", "review*", "citations*", "webapp*"]
```

(`review`, `citations`, `webapp` aren't created until later tasks/plans —
adding them all now avoids repeating this edit and re-install per plan.)

- [ ] **Step 2: Install and re-register the editable install**

Run: `cd /work/generator && pip install -e . --break-system-packages`

Expected: installs `pyoxigraph`/`oxrdflib`, completes without error.

- [ ] **Step 3: Write the failing test**

`tests/store/__init__.py`: empty file.

`tests/store/test_database.py`:

```python
import shutil

from store.database import open_store

STORE_PATH = "/tmp/test_provenance_store_task1"


def _fresh_path():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return STORE_PATH


def test_open_store_creates_a_new_store_and_persists_data_across_reopen():
    path = _fresh_path()
    try:
        dataset = open_store(path, create=True)
        graph = dataset.graph("urn:test:g1")
        graph.add(
            (
                "urn:test:s".__class__ and __import__("rdflib").URIRef("urn:test:s"),
                __import__("rdflib").URIRef("urn:test:p"),
                __import__("rdflib").Literal("hello"),
            )
        )
        dataset.close()

        reopened = open_store(path, create=False)
        reopened_graph = reopened.graph("urn:test:g1")
        triples = list(reopened_graph.triples((None, None, None)))
        assert len(triples) == 1
        assert str(triples[0][2]) == "hello"
        reopened.close()
    finally:
        shutil.rmtree(path, ignore_errors=True)
```

(The inline `__import__` calls are deliberately avoided in the real
implementation below — rewrite this test's imports properly before
running it; see Step 3b.)

- [ ] **Step 3b: Rewrite the test with clean imports**

Replace the test file content with:

```python
import shutil

from rdflib import Literal, URIRef

from store.database import open_store

STORE_PATH = "/tmp/test_provenance_store_task1"


def _fresh_path():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return STORE_PATH


def test_open_store_creates_a_new_store_and_persists_data_across_reopen():
    path = _fresh_path()
    try:
        dataset = open_store(path, create=True)
        graph = dataset.graph(URIRef("urn:test:g1"))
        graph.add((URIRef("urn:test:s"), URIRef("urn:test:p"), Literal("hello")))
        dataset.close()

        reopened = open_store(path, create=False)
        reopened_graph = reopened.graph(URIRef("urn:test:g1"))
        triples = list(reopened_graph.triples((None, None, None)))
        assert len(triples) == 1
        assert str(triples[0][2]) == "hello"
        reopened.close()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_open_store_without_create_on_a_missing_path_raises():
    path = _fresh_path()
    import pytest

    with pytest.raises(Exception):
        open_store(path, create=False)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /work && python3 -m pytest generator/tests/store/test_database.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'store.database'` (or `store`).

- [ ] **Step 5: Implement `store/database.py`**

`store/__init__.py`: empty file.

`store/database.py`:

```python
"""Opens the single embedded, persistent, transactional Oxigraph store
this whole platform reads and writes -- one file on disk, analogous to
opening a SQLite database, via the real rdflib.Dataset API (oxrdflib
backs it with a real Oxigraph store; no separate server process).
"""
from __future__ import annotations

from rdflib import Dataset


def open_store(path: str, create: bool = False) -> Dataset:
    dataset = Dataset(store="Oxigraph")
    dataset.open(path, create=create)
    return dataset
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/store/test_database.py -v`

Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml store/ tests/store/
git commit -m "Add store package: open/create the embedded Oxigraph dataset"
```

---

### Task 2: `store/runs.py` — write an immutable run graph + metadata

**Files:**
- Create: `store/runs.py`
- Test: `tests/store/test_runs.py`

**Interfaces:**
- Consumes: `store.database.open_store` (Task 1)
- Produces:
  - `store.runs.RUNS` — `Namespace("https://purl.openfaster.org/runs/")`
  - `store.runs.RunInfo` — frozen dataclass: `run_id: str`, `graph_uri: str`, `xsd_path: str`, `xsd_hash: str`, `pdf_path: str`, `pdf_hash: str`, `created_at: str`
  - `store.runs.write_run(dataset: Dataset, run_id: str, graph: rdflib.Graph, xsd_path: str, pdf_path: str, created_at: str) -> RunInfo`
  - `store.runs.list_runs(dataset: Dataset) -> list[RunInfo]` (sorted by `created_at`)

- [ ] **Step 1: Write the failing test**

`tests/store/test_runs.py`:

```python
import shutil

from rdflib import Graph, Literal, Namespace, URIRef

from store.database import open_store
from store.runs import list_runs, write_run

STORE_PATH = "/tmp/test_provenance_store_task2"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_write_run_stores_the_graph_under_a_new_named_graph_and_returns_info():
    dataset = _fresh_dataset()
    try:
        graph = Graph()
        graph.add((EX.WIdNr, EX.documentation, Literal("German text", lang="de")))

        info = write_run(
            dataset,
            run_id="2026-09-15T14:00:00Z",
            graph=graph,
            xsd_path="/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd",
            pdf_path="/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf",
            created_at="2026-09-15T14:00:00Z",
        )

        assert info.run_id == "2026-09-15T14:00:00Z"
        assert info.xsd_hash and info.pdf_hash  # real sha256 hex digests, non-empty

        stored_graph = dataset.graph(URIRef(info.graph_uri))
        stored = list(stored_graph.triples((None, None, None)))
        assert len(stored) == 1
        assert str(stored[0][2]) == "German text"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_list_runs_returns_every_written_run_sorted_by_created_at():
    dataset = _fresh_dataset()
    try:
        write_run(
            dataset, run_id="run-b", graph=Graph(),
            xsd_path="a.xsd", pdf_path="a.pdf", created_at="2026-09-15T09:00:00Z",
        )
        write_run(
            dataset, run_id="run-a", graph=Graph(),
            xsd_path="b.xsd", pdf_path="b.pdf", created_at="2026-09-15T08:00:00Z",
        )

        runs = list_runs(dataset)

        assert [r.run_id for r in runs] == ["run-a", "run-b"]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'store.runs'`.

- [ ] **Step 3: Implement `store/runs.py`**

```python
"""Each extraction run is written as one immutable named graph, never
mutated afterward -- that immutability is itself provenance (you can
always see exactly what a given run believed). Real content hashes (not
just paths) are recorded so a later run can be told apart from an
identical re-run of the same inputs.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rdflib import Dataset, Graph, Literal, Namespace, URIRef

RUNS = Namespace("https://purl.openfaster.org/runs/")


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    graph_uri: str
    xsd_path: str
    xsd_hash: str
    pdf_path: str
    pdf_hash: str
    created_at: str


def _sha256_of_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write_run(
    dataset: Dataset,
    run_id: str,
    graph: Graph,
    xsd_path: str,
    pdf_path: str,
    created_at: str,
) -> RunInfo:
    graph_uri = str(RUNS[run_id])
    run_graph = dataset.graph(URIRef(graph_uri))
    for triple in graph.triples((None, None, None)):
        run_graph.add(triple)

    info = RunInfo(
        run_id=run_id,
        graph_uri=graph_uri,
        xsd_path=xsd_path,
        xsd_hash=_sha256_of_file(xsd_path),
        pdf_path=pdf_path,
        pdf_hash=_sha256_of_file(pdf_path),
        created_at=created_at,
    )

    index = dataset.graph(URIRef(str(RUNS["index"])))
    subject = URIRef(graph_uri)
    index.add((subject, RUNS.runId, Literal(info.run_id)))
    index.add((subject, RUNS.xsdPath, Literal(info.xsd_path)))
    index.add((subject, RUNS.xsdHash, Literal(info.xsd_hash)))
    index.add((subject, RUNS.pdfPath, Literal(info.pdf_path)))
    index.add((subject, RUNS.pdfHash, Literal(info.pdf_hash)))
    index.add((subject, RUNS.createdAt, Literal(info.created_at)))

    return info


def list_runs(dataset: Dataset) -> list[RunInfo]:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    runs = []
    for subject in set(index.subjects(RUNS.runId, None)):
        runs.append(
            RunInfo(
                run_id=str(index.value(subject, RUNS.runId)),
                graph_uri=str(subject),
                xsd_path=str(index.value(subject, RUNS.xsdPath)),
                xsd_hash=str(index.value(subject, RUNS.xsdHash)),
                pdf_path=str(index.value(subject, RUNS.pdfPath)),
                pdf_hash=str(index.value(subject, RUNS.pdfHash)),
                created_at=str(index.value(subject, RUNS.createdAt)),
            )
        )
    runs.sort(key=lambda r: r.created_at)
    return runs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py -v`

Expected: PASS (2 tests). Note: the first test uses real fixture paths
for hashing — confirm those two files exist at
`/work/generator`-relative or absolute paths before running (run pytest
from `/work/generator`, matching this repo's established convention).

- [ ] **Step 5: Commit**

```bash
git add store/runs.py tests/store/test_runs.py
git commit -m "Add store.runs: write immutable run graphs with content-hashed metadata"
```

---

### Task 3: `store/runs.py` — diffing two runs

**Files:**
- Modify: `store/runs.py`
- Test: `tests/store/test_runs.py`

**Interfaces:**
- Produces:
  - `store.runs.RunDiff` — frozen dataclass: `added: list[tuple[str, str, str]]`, `removed: list[tuple[str, str, str]]`
  - `store.runs.diff_runs(dataset: Dataset, run_id_a: str, run_id_b: str) -> RunDiff` (diff is A → B: `removed` = in A not B, `added` = in B not A)

- [ ] **Step 1: Write the failing test**

Append to `tests/store/test_runs.py`:

```python
from rdflib import Graph as PlainGraph
from store.runs import diff_runs


def test_diff_runs_reports_only_added_and_removed_triples_not_unchanged_ones():
    dataset = _fresh_dataset()
    try:
        graph_a = PlainGraph()
        graph_a.add((EX.X, EX.doc, Literal("old text")))
        graph_a.add((EX.Y, EX.doc, Literal("unchanged")))
        write_run(dataset, run_id="a", graph=graph_a, xsd_path="a.xsd", pdf_path="a.pdf", created_at="t1")

        graph_b = PlainGraph()
        graph_b.add((EX.X, EX.doc, Literal("new text")))
        graph_b.add((EX.Y, EX.doc, Literal("unchanged")))
        graph_b.add((EX.Z, EX.doc, Literal("brand new")))
        write_run(dataset, run_id="b", graph=graph_b, xsd_path="b.xsd", pdf_path="b.pdf", created_at="t2")

        diff = diff_runs(dataset, "a", "b")

        removed_objects = {str(o) for (_, _, o) in diff.removed}
        added_objects = {str(o) for (_, _, o) in diff.added}
        assert removed_objects == {"old text"}
        assert added_objects == {"new text", "brand new"}
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py -v -k diff_runs`

Expected: FAIL with `ImportError: cannot import name 'diff_runs'`.

- [ ] **Step 3: Implement `diff_runs`**

Append to `store/runs.py`:

```python
@dataclass(frozen=True)
class RunDiff:
    added: list[tuple[str, str, str]]
    removed: list[tuple[str, str, str]]


def _run_graph_uri(dataset: Dataset, run_id: str) -> str:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    for subject in index.subjects(RUNS.runId, Literal(run_id)):
        return str(subject)
    raise ValueError(f"no run with run_id={run_id!r}")


def diff_runs(dataset: Dataset, run_id_a: str, run_id_b: str) -> RunDiff:
    graph_uri_a = _run_graph_uri(dataset, run_id_a)
    graph_uri_b = _run_graph_uri(dataset, run_id_b)

    removed_query = f"""
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri_a}> {{ ?s ?p ?o }}
      FILTER NOT EXISTS {{ GRAPH <{graph_uri_b}> {{ ?s ?p ?o }} }}
    }}
    """
    added_query = f"""
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri_b}> {{ ?s ?p ?o }}
      FILTER NOT EXISTS {{ GRAPH <{graph_uri_a}> {{ ?s ?p ?o }} }}
    }}
    """
    removed = [(str(r["s"]), str(r["p"]), str(r["o"])) for r in dataset.query(removed_query)]
    added = [(str(r["s"]), str(r["p"]), str(r["o"])) for r in dataset.query(added_query)]
    return RunDiff(added=added, removed=removed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/store/test_runs.py -v`

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add store/runs.py tests/store/test_runs.py
git commit -m "Add store.runs.diff_runs: real SPARQL named-graph diffing"
```

---

### Task 4: `provenance/` — PROV vocabulary + RDF-star record attach/read

**Files:**
- Create: `provenance/__init__.py`
- Create: `provenance/vocab.py`
- Create: `provenance/record.py`
- Test: `tests/provenance/__init__.py` (empty)
- Test: `tests/provenance/test_record.py`

**Interfaces:**
- Consumes: `store.database.open_store` (Task 1)
- Produces:
  - `provenance.vocab.PROV` — `Namespace("http://www.w3.org/ns/prov#")`
  - `provenance.record.attach_provenance(dataset, graph_uri: str, subject, predicate, obj, source_uri: str, generated_at: str) -> None`
  - `provenance.record.ProvenanceRecord` — frozen dataclass: `source_uri: str`, `generated_at: str`
  - `provenance.record.get_provenance(dataset, graph_uri: str, subject, predicate, obj) -> ProvenanceRecord | None`

- [ ] **Step 1: Write the failing test**

`tests/provenance/__init__.py`: empty file.

`tests/provenance/test_record.py`:

```python
import shutil

from rdflib import Literal, Namespace

from provenance.record import attach_provenance, get_provenance
from store.database import open_store

STORE_PATH = "/tmp/test_provenance_store_task4"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_attach_and_get_provenance_round_trips_via_rdf_star():
    dataset = _fresh_dataset()
    try:
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
            source_uri="citation:xsd/frag-1",
            generated_at="2026-09-15T14:00:00Z",
        )

        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
        )

        assert record is not None
        assert record.source_uri == "citation:xsd/frag-1"
        assert record.generated_at == "2026-09-15T14:00:00Z"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_provenance_returns_none_for_an_untracked_fact():
    dataset = _fresh_dataset()
    try:
        record = get_provenance(
            dataset, graph_uri="urn:test:prov",
            subject=EX.Nope, predicate=EX.documentation, obj=Literal("nothing"),
        )
        assert record is None
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/provenance/test_record.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'provenance'`.

- [ ] **Step 3: Implement `provenance/vocab.py` and `provenance/record.py`**

`provenance/__init__.py`: empty file.

`provenance/vocab.py`:

```python
"""This project's real PROV-O usage: only the handful of predicates
actually needed, not the full PROV-O vocabulary -- attached to individual
facts via RDF-star quoted triples, not classical 4-triple reification.
"""
from rdflib import Namespace

PROV = Namespace("http://www.w3.org/ns/prov#")
```

`provenance/record.py`:

```python
"""Attaches/reads provenance for one specific (subject, predicate, object)
fact via an RDF-star quoted triple -- verified live against pyoxigraph to
avoid classical RDF reification's 4-extra-triples-per-statement bloat.
Structural/cardinality facts do NOT get per-triple records here (see the
design spec's Data model section) -- only prose fields that are genuinely
multi-source or correctable route through this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Dataset
from rdflib.term import Node

from provenance.vocab import PROV


@dataclass(frozen=True)
class ProvenanceRecord:
    source_uri: str
    generated_at: str


def _n3(term: Node) -> str:
    return term.n3()


def attach_provenance(
    dataset: Dataset,
    graph_uri: str,
    subject: Node,
    predicate: Node,
    obj: Node,
    source_uri: str,
    generated_at: str,
) -> None:
    quoted = f"<< {_n3(subject)} {_n3(predicate)} {_n3(obj)} >>"
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom <{source_uri}> .
        {quoted} prov:generatedAtTime "{generated_at}" .
      }}
    }}
    """)


def get_provenance(
    dataset: Dataset,
    graph_uri: str,
    subject: Node,
    predicate: Node,
    obj: Node,
) -> ProvenanceRecord | None:
    quoted = f"<< {_n3(subject)} {_n3(predicate)} {_n3(obj)} >>"
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?src ?time WHERE {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom ?src .
        {quoted} prov:generatedAtTime ?time .
      }}
    }}
    """))
    if not results:
        return None
    row = results[0]
    return ProvenanceRecord(source_uri=str(row["src"]), generated_at=str(row["time"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/provenance/test_record.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add provenance/ tests/provenance/
git commit -m "Add provenance package: RDF-star provenance attach/read"
```

---

### Task 5: `citations/pdf_citation.py` — real PDF page crops

**Files:**
- Create: `citations/__init__.py`
- Create: `citations/pdf_citation.py`
- Test: `tests/citations/__init__.py` (empty)
- Test: `tests/citations/test_pdf_citation.py`

**Interfaces:**
- Produces: `citations.pdf_citation.crop_pdf_page(pdf_path: str, page_number: int, bbox: tuple[float, float, float, float], padding: float = 5.0) -> bytes`
  (`bbox` is `(x0, top, x1, bottom)` in `pdfplumber` coordinates; `page_number` is 0-indexed; returns real PNG bytes.)

- [ ] **Step 1: Write the failing test**

`tests/citations/__init__.py`: empty file.

`tests/citations/test_pdf_citation.py`:

```python
import io

from PIL import Image

from citations.pdf_citation import crop_pdf_page

ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_crop_pdf_page_returns_real_nonempty_png_bytes():
    png_bytes = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0))

    assert len(png_bytes) > 100
    image = Image.open(io.BytesIO(png_bytes))
    assert image.format == "PNG"
    assert image.width > 0 and image.height > 0


def test_crop_pdf_page_applies_padding_around_the_bbox():
    tight = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0), padding=0.0)
    padded = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0), padding=20.0)

    tight_image = Image.open(io.BytesIO(tight))
    padded_image = Image.open(io.BytesIO(padded))
    assert padded_image.width > tight_image.width
    assert padded_image.height > tight_image.height
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_pdf_citation.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'citations'`.

- [ ] **Step 3: Implement `citations/pdf_citation.py`**

`citations/__init__.py`: empty file.

`citations/pdf_citation.py`:

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


def crop_pdf_page(
    pdf_path: str,
    page_number: int,
    bbox: tuple[float, float, float, float],
    padding: float = 5.0,
    resolution: int = 150,
) -> bytes:
    x0, top, x1, bottom = bbox
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_pdf_citation.py -v`

Expected: PASS (2 tests). If `PIL`/`Pillow` isn't already present, `pip install --break-system-packages Pillow` first — `pdfplumber` depends on it transitively, so it should already be available; confirm with `python3 -c "import PIL"` before assuming a new dependency is needed.

- [ ] **Step 5: Commit**

```bash
git add citations/pdf_citation.py tests/citations/
git commit -m "Add citations.pdf_citation: real PDF page-region crops for inline evidence"
```

---

### Task 6: `citations/xsd_citation.py` — real XSD source fragments

**Files:**
- Create: `citations/xsd_citation.py`
- Test: `tests/citations/test_xsd_citation.py`

**Interfaces:**
- Produces:
  - `citations.xsd_citation.XsdCitation` — frozen dataclass: `fragment: str`, `source_file: str`
  - `citations.xsd_citation.capture_xsd_fragment(xsd_component) -> XsdCitation` (`xsd_component` is any `xmlschema` validator object exposing `.elem` and `.schema.source.url`, e.g. an `XsdComplexType`/`XsdElement`/`XsdAttribute`)

- [ ] **Step 1: Write the failing test**

`tests/citations/test_xsd_citation.py`:

```python
import xmlschema

from citations.xsd_citation import capture_xsd_fragment

ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"


def test_capture_xsd_fragment_returns_the_exact_real_source_fragment_and_file():
    schema = xmlschema.XMLSchema(ROOT_XSD)
    type_name = "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType"
    component = schema.maps.types[type_name]

    citation = capture_xsd_fragment(component)

    assert "MeldepflichtigeStelleType" in citation.fragment
    assert citation.fragment.strip().startswith("<xs:complexType")
    assert citation.source_file.endswith("MiKaDiv_FM_Personentypen_1.02.xsd")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_xsd_citation.py -v`

Expected: FAIL with `ImportError: cannot import name 'capture_xsd_fragment'`.

- [ ] **Step 3: Implement `citations/xsd_citation.py`**

```python
"""Real inline evidence for a structural XSD fact: the exact source
fragment and file it came from, not a re-typed summary. Verified live
during design: xmlschema's parsed objects expose `.elem` (a stdlib
ElementTree element, since xmlschema itself doesn't use lxml) --
ET.tostring gives the exact byte-faithful fragment, and
`.schema.source.url` gives the real file (the corpus is split across
multiple included files, so this is often not the root file extraction
was pointed at). No line number here -- xmlschema's stdlib ElementTree
parse drops source line info; recovering it needs a separate lxml pass,
deliberately out of scope for this task (see the design spec's
Non-Goals).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class XsdCitation:
    fragment: str
    source_file: str


def capture_xsd_fragment(xsd_component) -> XsdCitation:
    fragment = ET.tostring(xsd_component.elem, encoding="unicode")
    source_file = xsd_component.schema.source.url
    return XsdCitation(fragment=fragment, source_file=source_file)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /work && python3 -m pytest generator/tests/citations/test_xsd_citation.py -v`

Expected: PASS (1 test).

- [ ] **Step 5: Run the full Plan A test suite**

Run: `cd /work && python3 -m pytest generator/tests/store/ tests/provenance/ tests/citations/ -v`

Expected: all tests from Tasks 1-6 pass (10 tests total).

- [ ] **Step 6: Commit**

```bash
git add citations/xsd_citation.py tests/citations/test_xsd_citation.py
git commit -m "Add citations.xsd_citation: exact real source fragment + file capture"
```
