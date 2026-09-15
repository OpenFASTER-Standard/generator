# Generator Output Report — Design

Sub-project 3b of `/work/openfaster-restructuring/STATUS.md`, inserted
between sub-project 3a (XSD extraction logic, complete) and 3c (`mikadiv-fm`
concept curation, not started) per explicit operator request: a
standardized, very easily accessible way for the operator to visually
verify what the generator produces, with their own eyes.

## Context

Sub-project 3a built `generator/extraction/`: `extract(xsd_path)` produces
a real `xsdo:`-shaped `rdflib.Graph` from the official MiKaDiv-FM XSD
family; `attach_english_documentation(graph, pdf_path)` matches and
attaches real English text from BZSt's official Annex PDF, returning an
`AttachmentReport`; `check_translation_plausibility(graph)` and
`check_translation_coverage(graph, occurrences)` audit the result. Today
the only way to look at any of this is ad hoc `python3 -c "..."` scripts
run during development — there is no standing, reusable way for the
operator to actually see the output. This sub-project builds that.

**Explicitly not scoped to 3a's output alone.** Whatever `generator`
produces next (3c's structural realization, sub-projects 4/5's own
extraction work) should get the same report shape for free — the report
generator's input is a plain `rdflib.Graph` plus the audit result types
already defined in `extraction/annex_pdf.py`/`extraction/translation_plausibility.py`,
not anything MiKaDiv-FM-specific.

## Non-Goals

- **Not a general-purpose RDF/ontology browser.** It's shaped around this
  project's own `xsdo:` vocabulary and audit types, not SPARQL, not
  arbitrary graphs.
- **No server, no CI automation, no history/diffing.** The report is
  regenerated and committed on demand (by the agent, when there's
  something new worth looking at), showing current reality only. If a
  standing, always-current URL becomes worth the operational overhead
  later, that's a future decision, not built speculatively now.
- **No new Python dependency for templating** (see Architecture).
- **Not a replacement for `check_translation_plausibility`'s own automated
  checks or `test_whole_corpus_regression.py`'s locked baseline.** This is
  for human eyes; the automated checks stay the source of truth for CI/
  regression purposes.

## Architecture

```
generator/reporting/
  __init__.py
  data.py            # rdflib.Graph + audit results -> plain JSON-serializable dict
  assets/
    report.html      # shell: structure, embeds {{DATA_JSON}}
    report.css
    report.js         # vanilla JS: render, search/filter, expand/collapse
  __main__.py         # CLI: runs the real pipeline, writes the HTML file
```

**No templating library.** `data.py` does all the real work — walking the
graph into a plain dict. `__main__.py` reads `assets/report.html` as a
string, substitutes one placeholder with `json.dumps(data)`, and writes
the result. `assets/report.js` (inlined into the output, not a separate
HTTP request) renders that embedded JSON into the DOM and handles all
interactivity client-side. This keeps the generated file genuinely
self-contained — opens correctly from a plain `file://` path, no server,
no external requests, no new Python dependency.

## Data model (`data.py`)

```python
def build_report_data(
    graph: Graph,
    occurrences: dict[str, list[str]],
    plausibility_issues: list[PlausibilityIssue],
    coverage: CoverageReport,
    attachment: AttachmentReport,
) -> dict:
    ...
```

Returns a plain dict, JSON-serializable, shaped roughly as:

```python
{
    "structure": {
        "<namespace>": {
            "complexTypes": [
                {
                    "uri": "...", "name": "...", "abstract": bool,
                    "extends": "<uri or null>",
                    "contentModel": {"kind": "Sequence"|"Choice", "particles": [
                        {"minOccurs": int, "maxOccurs": int|"unbounded",
                         "term": {...nested contentModel...} | {"ref": "<element uri>"}}
                    ]},
                    "attributeUses": [{"required": bool, "ref": "<attribute uri>"}],
                    "identityConstraints": [{"kind": "Key"|"Unique"|"KeyRef",
                        "selector": str, "fields": [str], "refer": str|None}],
                },
                ...
            ],
            "simpleTypes": [...],
        },
    },
    "declarations": {
        "<uri>": {"name": str, "kind": "Element"|"Attribute", "type": "<uri>",
                  "default": str|None, "fixed": str|None,
                  "documentation": {"de": str|None, "en": str|None}},
        ...
    },
    "documentationPairs": {
        "matched": [{"uri": str, "name": str, "de": str, "en": str,
                     "issues": [{"kind": str, "detail": str}]}],
        "unmatched": [{"uri": str, "name": str, "de": str}],
        "ambiguous": [{"uri": str, "name": str, "de": str, "candidates": [str]}],
    },
    "audit": {
        "attachment": {"attached": int, "ambiguous": int, "unmatched": int},
        "coverage": {"total": int, "attached": int, "ambiguous": int, "unmatched": int},
        "issues": [{"kind": str, "subjectName": str, "detail": str}],
    },
}
```

`structure`/`declarations` are built by walking `graph` directly (real
`rdflib` queries against the `xsdo:` predicates already established by
extraction). `documentationPairs` is built by cross-referencing
`occurrences` (which names had ambiguous/no PDF matches at all) against
what actually ended up on the graph. `audit` is a direct, thin
reshaping of the already-computed `AttachmentReport`/`CoverageReport`/
`list[PlausibilityIssue]` — no new computation.

## Report content (`report.html`/`.js`)

Three sections, navigable via a fixed top bar; one plain-text search box
filters all three by name substring simultaneously (client-side, no
server round-trip):

- **§1 Structure** — collapsible tree, grouped by namespace then
  construct kind. Each complex type shows name/abstract/`extends` (a
  clickable in-page link to the base type's own entry), its content
  model rendered as a nested indented list (Sequence/Choice, particle
  occurrence bounds, each leaf linking to its element's entry), its
  attribute uses (required/optional, linking to the attribute), and its
  identity constraints. Elements/attributes are leaf entries showing
  name, type (linked), default/fixed, and inline documentation.
- **§2 Documentation pairs** — four visible groups (matched/unmatched/
  ambiguous/**english-only**, per the data model above — the fourth
  group was added during implementation after the final review found
  real subjects with `@en`-only documentation, e.g. from a corrupted
  PDF-parsing artifact, were being silently dropped). A matched pair
  with a plausibility issue shows that issue's reason directly beneath
  it, highlighted — except when the same bare name maps to 2+ distinct
  matched subjects, in which case the issue is deliberately left
  unattributed at this level (real `PlausibilityIssue`s carry no URI,
  only a bare name, so attaching to one specific subject would be a
  guess) and surfaces only in §3 instead. An ambiguous name shows every
  distinct candidate text found, so the reader can see why nothing was
  attached.
- **§1 Structure** also renders a small "Global declarations" group per
  namespace, added during implementation: any element/attribute
  declaration never reached by a particle/attribute-use reference
  during the normal structure walk (real example: `MiKaDivFMRoot`, the
  schema's own root element, referenced by nothing) is rendered there
  instead of being silently omitted.
- **§3 Audit dashboard** — the raw `attached`/`ambiguous`/`unmatched`
  numbers from both report types, then the full issue list (kind,
  subject, detail). (Not yet implemented: cross-linking each issue back
  to its subject's own §2 entry — deferred, not a correctness gap.)

## CLI (`__main__.py`)

```
python -m reporting <xsd_path> <pdf_path> -o report.html
```

(Run from `/work/generator` — `reporting` is a real, flat, top-level
package in this repo, matching `extraction`/`equivalence`/etc.'s own
layout, not a submodule of a `generator` package.)

Runs the real pipeline end to end (`extract` → `attach_english_documentation`
→ `check_translation_coverage`/`check_translation_plausibility`), builds
the report data, writes the HTML file. No flags beyond `-o`/`--output`
(default `report.html` in the current directory) — YAGNI on configurability
until a real second use case demands it.

## Testing strategy

- Real unit tests on `data.py` against small, hand-built graphs (the
  same style as `extraction/`'s own tests) — assert the right tree
  shape, the right documentation-pair grouping, and the right audit
  numbers come out for known inputs. This is where real bugs would hide;
  covered like any other real logic in this codebase.
- A smoke test: generate a report against a tiny synthetic graph, assert
  the output is well-formed HTML and its embedded JSON parses back to
  the exact `build_report_data` output.
- One real, whole-corpus generation: run the CLI against the real
  MiKaDiv-FM XSD family + real Annex PDF, confirm it completes without
  error and produces a non-trivial file.
- Per this project's own UI-verification convention, render the real
  generated report with Playwright and take a screenshot as a sanity
  check (catches an obviously broken render) — not a substitute for the
  operator's own visual review, which is this whole sub-project's actual
  point.

## Definition of Done

- `python -m generator.reporting` runs against the real MiKaDiv-FM family
  and produces a single, self-contained `report.html` that opens
  correctly from a plain file path (no server) and shows all three
  sections with real data.
- `report.html` is committed to the `generator` repo.
- The report generator's own input types (`Graph`, `AttachmentReport`,
  `CoverageReport`, `list[PlausibilityIssue]`) are exactly the types
  `extraction/` already produces — no new, sub-project-specific
  extraction logic invented here.
