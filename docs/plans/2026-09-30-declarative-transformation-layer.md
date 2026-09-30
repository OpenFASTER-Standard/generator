# Declarative Transformation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `annotation_model/transform/`, a new subpackage turning a
named, registered `(SPARQL query, renderer, min_rows)` transformation
into real rendered output (text or a workbook) by querying an
`rdflib.Graph` and handing the result rows to the renderer.

**Architecture:** Three bottom-up tasks. Task 1 is a registry, mirroring
`reference_model/registry.py`'s existing register/get idiom exactly.
Task 2 is `apply_transformation()`, the one function that runs a
registered transformation end to end, with `TransformationError` as the
single, specific failure mode for every stage. Task 3 proves the
renderer contract (`Callable[[list[dict]], Any]`) is expressive enough
for both named output kinds — Jinja2 text and a raw `openpyxl` workbook
— by running each through Task 2's own `apply_transformation()`, with no
separate renderer-kind module for the Excel case.

**Tech Stack:** Python 3.11, `rdflib>=7.6` (already a dependency,
`Graph.query()` used directly — no new SPARQL library), `jinja2>=3.1`
and `openpyxl>=3.1` (new runtime dependencies — both real code paths use
them, unlike `pyshacl` in the task-1 plan, which was test-only).

**Spec:** `docs/specs/2026-09-30-declarative-transformation-design.md`

## Global Constraints

- **A renderer is exactly `Callable[[list[dict]], Any]`** — no
  renderer-kind base class, no separate `TextRenderer`/`WorkbookRenderer`
  types. Task 3 exists specifically to prove this one contract already
  covers both named output kinds.
- **`min_rows` defaults to `1`.** A transformation registered without an
  explicit `min_rows` must error on an empty query result; only a
  transformation that explicitly passes `min_rows=0` may return nothing
  without raising.
- **Every failure surfaces as `TransformationError`, naming the
  transformation and which stage failed** (query, min_rows, or
  renderer) — never a bare `pyparsing.exceptions.ParseException` or
  other underlying library exception reaching the caller directly.
- **This plan is purely additive**: `annotation_model/rdf.py`,
  `store.py`, `drift.py`, and `selectors/` (all from roadmap task 1,
  already shipped and reviewed) are not modified.
- **Registry error style matches the existing selector registry
  exactly** (`reference_model/registry.py`'s `register()`/
  `get_resolver()`): `register()` raises `ValueError` on a name collision
  unless `replace=True`; a missing lookup raises `KeyError` listing every
  known name, sorted.
- **Real values, verified live against the real MiKaDiv-FM corpus
  before this plan was written** (safe to use directly in test code, no
  further verification needed):
  - `REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"`
  - Two distinct, uniquely-resolvable XPaths in that file:
    `"//xs:element[@name='AOrdNr']"` and
    `"//xs:element[@name='AbgefKapitalertragsteuer']"` (both
    `Status.RESOLVED`).
  - `rdflib.URIRef` is a real `str` subclass — a property IRI's local
    name is recoverable with plain Python/Jinja2 string splitting
    (`row.property.split('/')[-1]`); neither real name above contains a
    percent-encoded character, so no URL-decoding is needed for this
    plan's tests.
  - An invalid SPARQL string raises `pyparsing.exceptions.ParseException`
    from `Graph.query()` — this plan catches the broad `Exception` at
    that call, not this specific type, since a different malformed query
    could fail at a different stage of rdflib's SPARQL engine.

## Review Focus

- **A transformation's renderer receiving zero rows when `min_rows=0`
  must not itself crash** — an empty `list[dict]` is a real input a
  renderer must handle, not just a `min_rows` edge case to reject.
- **A `min_rows` violation and a renderer exception must be
  distinguishable from each other and from a query failure** in
  `TransformationError`'s own message — a caller catching the one
  exception type still needs to tell the three stages apart.
- **Two different transformations must not see each other's
  registrations** — registering `"a"` then `"b"` must not make `"a"`
  invisible or vice versa (a plain dict-backed registry gets this for
  free, but it's worth a real test given Task 1 has no prior art in this
  package to lean on).
- **A query that runs but selects the wrong variable names** (e.g. the
  renderer expects `row["hash"]` but the query only selected `?value`)
  must surface as a renderer-stage `TransformationError`, not a
  confusing failure blamed on the query stage — `apply_transformation`'s
  broad `try/except Exception` around the renderer call (Task 2) already
  catches a `KeyError` from this exact scenario the same way it catches
  the test's `ValueError`, since both are raised from inside the
  renderer call; no separate test is needed beyond Task 2's existing
  renderer-failure test to prove the mechanism.
- **Provenance columns must survive an `ORDER BY`** on a different
  column — confirmed live already (see Global Constraints), but the test
  in Task 2 should query with an `ORDER BY ?property` so this isn't
  accidentally only proven for an unordered result.

---

### Task 1: Transformation registry

**Files:**
- Create: `annotation_model/transform/__init__.py` (empty)
- Create: `annotation_model/transform/registry.py`
- Test: `tests/annotation_model/transform/__init__.py` (empty)
- Test: `tests/annotation_model/transform/test_registry.py`

**Interfaces:**
- Produces:
  - `Transformation` (frozen dataclass): `name: str`, `query: str`,
    `renderer: Callable[[list[dict]], Any]`, `min_rows: int = 1`
  - `register(transformation: Transformation, *, replace: bool = False) -> None`
  - `get(name: str) -> Transformation`

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/transform/test_registry.py
import pytest

from annotation_model.transform.registry import Transformation, get, register


def _transformation(name="t1", query="SELECT ?x WHERE { ?x ?p ?o }", min_rows=1):
    return Transformation(name=name, query=query, renderer=lambda rows: rows, min_rows=min_rows)


def test_register_then_get_round_trips():
    register(_transformation(name="round-trip-1"))
    result = get("round-trip-1")
    assert result.name == "round-trip-1"


def test_registering_the_same_name_twice_raises_without_replace():
    register(_transformation(name="dup-1"))
    with pytest.raises(ValueError, match="already registered"):
        register(_transformation(name="dup-1"))


def test_registering_the_same_name_twice_with_replace_succeeds():
    register(_transformation(name="replace-1", min_rows=1))
    register(_transformation(name="replace-1", min_rows=0), replace=True)
    assert get("replace-1").min_rows == 0


def test_get_missing_name_raises_with_known_names_listed():
    register(_transformation(name="known-1"))
    with pytest.raises(KeyError, match="known-1"):
        get("no-such-transformation-xyz")


def test_two_transformations_do_not_see_each_others_registration():
    register(_transformation(name="a-1", query="SELECT ?a WHERE { ?a ?p ?o }"))
    register(_transformation(name="b-1", query="SELECT ?b WHERE { ?b ?p ?o }"))
    assert get("a-1").query != get("b-1").query
    assert get("a-1").name == "a-1"
    assert get("b-1").name == "b-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/transform/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.transform'`

- [ ] **Step 3: Implement `annotation_model/transform/registry.py`**

Mirror `reference_model/registry.py`'s `register()`/`get_resolver()`
exactly (same `_REGISTRY: dict[str, Transformation] = {}` module-level
dict, same `ValueError`/`KeyError` message shapes, `get()`'s `KeyError`
message includes `sorted(_REGISTRY)`), renamed to `register()`/`get()`
and typed against `Transformation` instead of `Resolver`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/transform/test_registry.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add annotation_model/transform/__init__.py annotation_model/transform/registry.py \
        tests/annotation_model/transform/__init__.py tests/annotation_model/transform/test_registry.py
git commit -m "feat(annotation_model): add transformation registry"
```

---

### Task 2: apply_transformation()

**Files:**
- Create: `annotation_model/transform/apply.py`
- Test: `tests/annotation_model/transform/test_apply.py`

**Interfaces:**
- Consumes: Task 1's `Transformation`, `register`, `get`.
- Produces:
  - `TransformationError(RuntimeError)`
  - `apply_transformation(graph: rdflib.Graph, name: str) -> Any`

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/transform/test_apply.py
import pytest
from rdflib import Graph

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import TransformationError, apply_transformation
from annotation_model.transform.registry import Transformation, register
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

PROVENANCE_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
SELECT ?property ?hash ?annotation ?source WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
  ?property prov:wasDerivedFrom ?annotation .
  ?annotation oa:hasTarget ?target .
  ?target oa:hasSource ?source .
}
ORDER BY ?property
"""


def _two_field_graph() -> Graph:
    graph = Graph()
    for name, xpath in [
        ("AOrdNr", "//xs:element[@name='AOrdNr']"),
        ("AbgefKapitalertragsteuer", "//xs:element[@name='AbgefKapitalertragsteuer']"),
    ]:
        outcome = resolve_xpath(REAL_XSD, xpath)
        content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
        annotate_xpath(
            graph, standard="MiKaDiv-FM Meldeart23", shape_name="Meldeart23Fields",
            property_name=name, xpath=xpath, source_uri=f"file://{REAL_XSD}",
            content_hash=content_hash,
        )
    return graph


@requires_real_corpus
def test_returns_real_rows_from_a_real_graph():
    register(Transformation(name="fields-1", query=FIELD_QUERY, renderer=lambda rows: rows))
    rows = apply_transformation(_two_field_graph(), "fields-1")
    assert len(rows) == 2
    names = sorted(str(row["property"]).split("/")[-1] for row in rows)
    assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])


@requires_real_corpus
def test_provenance_columns_are_never_stripped():
    register(Transformation(name="fields-with-provenance-1", query=PROVENANCE_QUERY, renderer=lambda rows: rows))
    rows = apply_transformation(_two_field_graph(), "fields-with-provenance-1")
    assert len(rows) == 2
    for row in rows:
        assert str(row["source"]) == f"file://{REAL_XSD}"
        assert "/annotation" in str(row["annotation"])


def test_invalid_sparql_raises_transformation_error_naming_the_transformation():
    register(Transformation(name="broken-query-1", query="SELECT ?x WHERE not valid sparql", renderer=lambda rows: rows))
    with pytest.raises(TransformationError, match="broken-query-1"):
        apply_transformation(Graph(), "broken-query-1")


def test_fewer_than_min_rows_raises_by_default():
    register(Transformation(
        name="empty-by-default-1",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
    ))
    with pytest.raises(TransformationError, match="returned 0 row"):
        apply_transformation(Graph(), "empty-by-default-1")


def test_fewer_than_min_rows_does_not_raise_when_min_rows_is_zero():
    register(Transformation(
        name="empty-allowed-1",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
        min_rows=0,
    ))
    assert apply_transformation(Graph(), "empty-allowed-1") == []


def test_renderer_failure_raises_transformation_error_naming_the_renderer_stage():
    def _broken_renderer(rows):
        raise ValueError("boom")

    register(Transformation(
        name="broken-renderer-1",
        query="SELECT ?x WHERE { BIND(1 AS ?x) }",
        renderer=_broken_renderer,
    ))
    with pytest.raises(TransformationError, match="broken-renderer-1"):
        apply_transformation(Graph(), "broken-renderer-1")


def test_a_min_rows_violation_and_a_renderer_failure_have_distinguishable_messages():
    register(Transformation(
        name="empty-by-default-2",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
    ))

    def _broken_renderer(rows):
        raise ValueError("boom")

    register(Transformation(name="broken-renderer-2", query="SELECT ?x WHERE { BIND(1 AS ?x) }", renderer=_broken_renderer))

    min_rows_message = ""
    try:
        apply_transformation(Graph(), "empty-by-default-2")
    except TransformationError as exc:
        min_rows_message = str(exc)

    renderer_message = ""
    try:
        apply_transformation(Graph(), "broken-renderer-2")
    except TransformationError as exc:
        renderer_message = str(exc)

    assert min_rows_message != renderer_message
    assert "row" in min_rows_message.lower()
    assert "render" in renderer_message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/transform/test_apply.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.transform.apply'`

- [ ] **Step 3: Implement `TransformationError` and `apply_transformation` in `annotation_model/transform/apply.py`**

`apply_transformation(graph, name)`: look up `name` via Task 1's `get()`
(a `KeyError` here is not caught — it already names every known
transformation, per Task 1). Run `transformation.query` via
`graph.query(...)` inside a broad `try/except Exception`, re-raising as
`TransformationError(f"transformation {name!r} query failed: {exc}")`.
Convert results to `[row.asdict() for row in results]`. If
`len(rows) < transformation.min_rows`, raise
`TransformationError(f"transformation {name!r} returned {len(rows)} row(s), expected at least {transformation.min_rows}")`.
Call `transformation.renderer(rows)` inside its own `try/except
Exception`, re-raising as
`TransformationError(f"transformation {name!r} renderer failed: {exc}")`.
Return the renderer's result.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/transform/test_apply.py -v`
Expected: `7 passed`

- [ ] **Step 5: Add new dependencies to `pyproject.toml`**

Add `"jinja2>=3.1"` and `"openpyxl>=3.1"` to `[project] dependencies`
(both used by real code starting Task 3). Run `pip install -e .`.

- [ ] **Step 6: Commit**

```bash
git add annotation_model/transform/apply.py tests/annotation_model/transform/test_apply.py pyproject.toml
git commit -m "feat(annotation_model): apply a registered transformation against a graph"
```

---

### Task 3: Both renderer kinds through the same apply path

**Files:**
- Create: `annotation_model/transform/jinja.py`
- Test: `tests/annotation_model/transform/test_renderers.py`

**Interfaces:**
- Consumes: Task 1's `Transformation`/`register`; Task 2's
  `apply_transformation`.
- Produces:
  - `jinja_text_renderer(template_source: str) -> Callable[[list[dict]], str]`

No workbook-renderer module is created — Task 3's second test proves a
plain function using `openpyxl` directly already satisfies
`Callable[[list[dict]], Any]` with zero `annotation_model`-owned code.

- [ ] **Step 1: Write the failing tests**

```python
# tests/annotation_model/transform/test_renderers.py
from openpyxl import Workbook

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation, register
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus
from rdflib import Graph

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

TEMPLATE = """{% for row in rows %}{{ row.property.split('/')[-1] }}: {{ row.hash }}
{% endfor %}"""


def _two_field_graph() -> Graph:
    graph = Graph()
    for name, xpath in [
        ("AOrdNr", "//xs:element[@name='AOrdNr']"),
        ("AbgefKapitalertragsteuer", "//xs:element[@name='AbgefKapitalertragsteuer']"),
    ]:
        outcome = resolve_xpath(REAL_XSD, xpath)
        content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
        annotate_xpath(
            graph, standard="MiKaDiv-FM Meldeart23", shape_name="Meldeart23Fields",
            property_name=name, xpath=xpath, source_uri=f"file://{REAL_XSD}",
            content_hash=content_hash,
        )
    return graph


@requires_real_corpus
def test_jinja_text_renderer_produces_real_rendered_bikeshed_like_text():
    register(Transformation(name="bikeshed-fields-1", query=FIELD_QUERY, renderer=jinja_text_renderer(TEMPLATE)))
    rendered = apply_transformation(_two_field_graph(), "bikeshed-fields-1")

    assert "AOrdNr: sha256:" in rendered
    assert "AbgefKapitalertragsteuer: sha256:" in rendered


@requires_real_corpus
def test_a_plain_openpyxl_function_works_as_a_renderer_with_no_framework_code():
    def _workbook_renderer(rows: list[dict]) -> Workbook:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["property", "hash"])
        for row in rows:
            sheet.append([str(row["property"]).split("/")[-1], str(row["hash"])])
        return workbook

    register(Transformation(name="excel-fields-1", query=FIELD_QUERY, renderer=_workbook_renderer))
    workbook = apply_transformation(_two_field_graph(), "excel-fields-1")

    sheet = workbook.active
    rows = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
    assert rows[0] == ("property", "hash")
    names = sorted(r[0] for r in rows[1:])
    assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])
    assert all(str(r[1]).startswith("sha256:") for r in rows[1:])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/annotation_model/transform/test_renderers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotation_model.transform.jinja'`

- [ ] **Step 3: Implement `jinja_text_renderer` in `annotation_model/transform/jinja.py`**

```python
from typing import Any, Callable

from jinja2 import Template


def jinja_text_renderer(template_source: str) -> Callable[[list[dict]], str]:
    template = Template(template_source)

    def render(rows: list[dict[str, Any]]) -> str:
        return template.render(rows=rows)

    return render
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/annotation_model/transform/test_renderers.py -v`
Expected: `2 passed`

- [ ] **Step 5: Run the full test suite**

Run: `pytest`
Expected: all tests pass (this plan only added `annotation_model/transform/`
and touched no existing file except `pyproject.toml`'s dependency list).

- [ ] **Step 6: Commit**

```bash
git add annotation_model/transform/jinja.py tests/annotation_model/transform/test_renderers.py
git commit -m "feat(annotation_model): prove one renderer contract covers text and workbook output"
```

---

## Task-Master Bookkeeping

After Task 3's commit, mark roadmap task 2 done with real evidence:

```bash
npx -y --package=task-master-ai task-master set-status --id=2 --status=done
```

Then hand-edit `.taskmaster/tasks/tasks.json`'s task 2 to add an
`evidence.commits` array containing the real commit SHAs from Tasks 1–3
above, and run `scripts/validate-tasks` to confirm it passes.
