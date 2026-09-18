# Interconnected Provenance UI — Design

**Status:** Approved for planning (section-by-section design approved live; see
`.superpowers/sdd/` plans once written).

**Supersedes/extends:** Plan D of
`2026-09-15-provenance-and-review-platform-design.md`. That plan shipped a
correct, tested, tab-based frontend. This spec replaces its *information
architecture* — the tabs, the click-to-expand citation dot, the isolated
per-field lineage sheet — while keeping every backend capability it built
(the store, provenance model, review workflow, FastAPI service) unchanged.

## Motivation

Live use of the Plan D frontend surfaced two kinds of problem:

1. **Two real, previously-undetected bugs**, found only by actually clicking
   through the running app in a browser: a citation-rendering off-by-one
   (every PDF citation showed the page *after* the correct one — see
   `citations/pdf_citation.py`'s fix, already shipped independently of this
   spec) and `LineageGraph` being fully built and tested but never wired into
   any reachable user flow (also already fixed independently). Both were
   invisible to the existing test suite because no test checked *content*,
   only "something non-empty came back."
2. **A structural UX problem no bug fix addresses**: tabs of long scrollable
   cards give no overview of the system as a whole, provenance is hidden
   behind a small low-visibility dot, and there is no way to go from a source
   document back to everything derived from it. The product's whole premise —
   *full provenance for every piece of data* — isn't felt by someone using it,
   because the connections it tracks are one click deep at best, and the
   scale (~380 documented subjects × 2 languages × citations × corrections)
   makes "just add more content to the page" unworkable.

The goal is for the system to *feel* the way real hypertext/transclusion
systems and coordinated-multiple-view tools do: hovering something shows you
its source immediately; every fact and every source is bidirectionally
reachable from the other; and there's a real one-glance map of the whole
thing, not just detail screens.

## Research grounding

- **Transclusion** (Xanadu's original concept; shipped in weaker form by
  TiddlyWiki's `{{transclude}}`, Roam/Logseq/Obsidian block embeds): a
  derived value is a *live window onto its source*, not a copy with a
  citation footnote — the link back is always visible, not hidden behind an
  interaction.
- **Coordinated multiple views / brushing-and-linking** (established
  InfoVis technique): the same data shown in several linked panes; hovering
  or selecting in one instantly highlights the related elements in every
  other visible pane, without navigation.
- **Shneiderman's Visual Information-Seeking Mantra**: *overview first, zoom
  and filter, then details on demand* — naming exactly what today's tabs
  skip (there is no overview level at all).
- **PROV-O visualizers / nanopublications** (e.g. ProvViz, nanopub.net):
  render assertion + provenance + source as one small interactive graph you
  pan/zoom, not a document you scroll.
- **Code-editor navigation idioms**: VS Code's "Peek Definition" (light
  inline preview, no navigation) and "Find All References" (a panel of every
  usage, click to jump into context, always a path back).

## Overall shape

The current five tabs (Structure / Documentation / Audit / Corrections /
Runs) answer *what* content you're looking at. This design adds an
orthogonal axis — *how* you're looking at it — with three interchangeable,
switchable modes:

- **Graph** — the one-glance overview of the entire system, semantically
  zoomable.
- **Living Text** — hover-transclusion inline, for prose fields and their
  corrections.
- **Synced Panes** — a real source document alongside the derived report,
  synced bidirectionally.

Consolidation as part of this: **Graph absorbs Structure** (structural
hierarchy becomes part of the same network, not a separate page) and
**Audit becomes a filter on Graph** (toggle "show only unmatched," rather
than a static list) instead of its own page. **Corrections** move inline
into Living Text (see below) rather than a separate worklist table. **Runs**
stays independent — it's about *time*, not lineage — but a run diff's
changed facts become clickable into the other three modes.

A persistent mode switcher is always visible (not nested in a tab). Content
filters (by namespace, by documentation status, by pending-correction state)
apply within whichever mode is active.

## The shared focus model

A **focus** is a `(subject, predicate?, language?)` value, held in the URL
(`#/graph/<subject>`, `#/living-text/<subject>/<predicate>/<lang>`, etc.),
not just component state — so any focus is a shareable, bookmarkable link,
and refreshing never loses your place. All three modes read and write the
same focus: a subject resolves to the same node in Graph, the same card in
Living Text, and the same highlighted region in Synced Panes — one identity,
three renderings.

Two interactions are kept deliberately distinct:

- **Hover** — ephemeral. Lights up related elements everywhere on screen
  (brushing-and-linking). Never touches the URL or committed focus; moving
  the mouse away reverts everything.
- **Click / select** — commits the focus, updates the URL. Switching modes
  after a click opens the new mode already centered on the same subject/fact.

## Graph mode

Semantically zoomed, not one flat network — the real risk otherwise is a
hairball at this project's real scale.

- **Zoomed all the way out**: one node per XSD namespace (the same grouping
  Structure already uses) — the literal one-glance overview.
- **Zoom into a namespace**: expands into its complexTypes / simpleTypes /
  elements, colored by documentation status (matched / ambiguous /
  unmatched / English-only — Audit's own categories, now a graph filter
  instead of a separate page).
- **Zoom into (or click) one subject**: its provenance fan-out appears —
  each language's documentation, each with an edge to its real source, plus
  any pending/decided corrections as satellite nodes. This is the existing
  Plan D `LineageGraph` concept, generalized and anchored in the bigger map
  instead of trapped in an isolated per-field sheet.
- Structural edges (extends/contains) render by default at outer zoom
  levels; provenance edges (`wasDerivedFrom`) only render once zoomed into
  one subject's neighborhood.
- Hovering a node reuses the same preview-card component Living Text uses
  (one implementation, shared). Clicking commits focus and offers "open in
  Living Text" / "open in Synced Panes."
- Built on Cytoscape.js (already a dependency), with a real
  clustering/hierarchical layout and zoom-triggered style rules (both native
  to Cytoscape), rather than one flat force-directed layout of everything.

## Living Text mode

Documentation and Corrections live together here, not as separate pages. A
documented value is marked (subtle dotted underline, visually distinct from
"no citation exists") as a live window onto its source:

- **Hover** → an inline popover renders the real source (PDF crop, XSD
  fragment) immediately, no click, no page navigation.
- **Click** → pins it into a persistent Inspector panel alongside the
  content (not a modal) showing the citation larger, plus the *reverse*
  direction: "this same source also backs: N other facts," each a live jump
  that moves the shared focus.

**Corrections happen on the text itself.** A pending correction for a fact
renders inline — current value, proposed replacement (track-changes style),
Approve/Reject right there — because the correction *is* part of the text,
not a queue referring to it elsewhere. Proposing a *new* correction also
happens inline (click to edit; the proposed value becomes visible in place
as "pending" for every reviewer immediately) — **this is a real capability
gap relative to Plan D**, which only ever built approve/reject UI, never a
propose-a-correction UI; this design adds it.

A small persistent badge shows the system-wide pending-correction count;
clicking it focuses Graph mode filtered to pending corrections, rather than
a second, separate corrections UI.

Unmatched/ambiguous entries stay visually distinct (no dotted underline —
there is no citation to hover), styled as a visible gap rather than
something quietly missing.

## Synced Panes mode + the generic source-viewer abstraction

Any source format reduces to three things: a renderer, a **locator**
scheme (an opaque, format-specific address — a PDF's `{page, bbox}`, an
XSD's `{file, element}`, later perhaps a JSON Pointer or a spreadsheet
range), and a two-way mapping between a locator and an on-screen highlighted
region.

- A `SourceLocator` is a small tagged type (`{kind: "pdf-region", ...}`,
  `{kind: "xml-range", ...}`, extensible). Each source *kind* gets one
  plugin implementing "render this locator" and "render the whole document,
  mapping screen positions back to locators."
- Synced Panes mode itself — the sync, the hover-brushing, the
  click-to-filter-derived-facts — is written once, fully generic, and
  delegates to whichever plugin matches the current source's kind. A new
  input format later means one new plugin, not changes to Synced Panes.
- **This unifies with Living Text's hover-preview**: the same per-kind
  plugin (asked to render a small crop instead of the whole document) powers
  both the inline hover popover and the Synced Panes left pane.
- The existing `citation:pdf?...` / `citation:xsd?...` source-URI scheme is
  already, in effect, a serialized locator — it needs formalizing into this
  plugin shape, not reinventing.

Interaction, both directions (design intent — see the implementation note
immediately below for what actually shipped in the first cut):

- **Derived → source**: hover a fact in the right pane, the left pane
  auto-scrolls to and highlights the exact region it came from.
- **Source → derived**: scroll or click in the source pane itself, the right
  pane filters/highlights to only what was derived from that exact spot.

**Implementation note (added post-merge-review, 2026-09-18):** the first
cut ships **source → derived only**. Derived → source (hovering a
right-pane fact to highlight/scroll the left pane to its source region)
needs a real interface addition (`SourcePlugin` currently has no way to
express "highlight this locator in an already-rendered whole-document
view") and was never scheduled as a task in this design's own
implementation plan — a plan-authoring gap caught only by the final
whole-branch review, after all 16 scheduled tasks were already complete.
Rather than design and ship a from-scratch bidirectional-highlighting
feature inside a time-boxed final-review fix wave with no dedicated task
brief or test-first design, it's tracked here as real, explicit follow-up
work instead. See "Known gaps" below.

A small switcher at the top of the source pane picks which real source file
is in view (this corpus has one PDF but multiple XSD files). Facts with no
derivable source region (unmatched entries, the known local-scope German
citation gap — see Known Gaps below) show an explicit "not tied to one place
in this source," never a silent absence.

## Architecture

**Backend.** One genuinely new capability: a **reverse-lookup endpoint**
(`GET /api/sources/lookup?kind=pdf&page=196&bbox=...`) finding every fact
whose provenance record points at a given locator. Today provenance only
flows fact → source (`GET /api/provenance`); this is the RDF-star query run
the other direction — natural given the existing `<<s p o>>
prov:hasProvenanceRecord` design, but genuinely new query logic, not
reuse. Graph mode's zoomed views are assembled client-side from the
existing `/api/structure` + `/api/documentation` + `/api/audit` endpoints —
no new "graph summary" endpoint needed.

**Frontend.** The biggest structural change: introducing real client-side
routing (there is none today — `activeTab` is bare `useState`), since focus
must live in the URL. Shared components carry the interconnection: a
`SourcePreviewPopover` (hover), a persistent `Inspector` panel (click/pin),
and one `SourceViewer` dispatching to a per-kind plugin registry
(`PdfSourcePlugin`, `XsdSourcePlugin` first; a third format is additive
later). Graph mode wraps Cytoscape.js with zoom-triggered style rules and
the same shared focus/hover wiring as everything else — one hover/focus
system, not three.

## Testing strategy

New backend behavior (reverse lookup) gets real corpus-backed tests, per
this project's existing convention (no mocks). On the frontend: given that
every real bug found in Plan D's actual UI — the citation off-by-one, the
`LineageGraph` mount-timing bug, the Base UI `Select`-renders-while-closed
quirk — was caught only by driving the real, built app with Playwright, not
by unit tests, this redesign treats a live end-to-end walkthrough as a
required step for every mode, not an afterthought. A **plugin-conformance
test suite** (render a locator; round-trip a click back to a locator) is
required for every source-kind plugin, so adding a new format stays cheap
and safe rather than ad hoc.

## Known gaps carried into this design (not fixed by it)

- **German/XSD-side provenance only covers globally-named constructs**
  (138 of 377 real documented subjects) — a scope limit from the original
  Plan C Task 18, not something this redesign fixes. Synced Panes and Living
  Text must both render this honestly ("not tied to one place in this
  source" for a locally-scoped subject's German text), not silently.
- **Proposing a new correction has no UI in Plan D at all** — only
  approve/reject exist. This design adds it (inline, in Living Text), but
  flagging it here as a real, previously-unaddressed gap this spec closes,
  not one it introduces.
- **Added post-merge-review, 2026-09-18 — real, tracked follow-up work,
  not silently dropped:** three pieces of this design's own
  "interconnected, interlinked" vision didn't make this first cut, each for
  the same reason (a genuine feature needing its own design/task, not a
  shortfall in how a scheduled task was executed — the original 16-task
  plan never scheduled a task for any of the three):
  - **Synced Panes' derived → source direction** (see the implementation
    note in that section above) — only source → derived shipped.
  - **Graph mode has no hover-brushing** — `HoverFocusProvider` exists and
    is mounted, but no component (Graph's Cytoscape nodes in particular)
    actually calls `useHoverFocus()` yet, so the "hover lights up related
    elements everywhere on screen" interaction rule from Research grounding
    is unimplemented outside Living Text's own hover-preview popover.
  - **Living Text and Synced Panes don't yet react to the shared focus
    model** when it's set from elsewhere (e.g. focusing a subject in Graph
    mode doesn't scroll Living Text to that entry or pre-select the
    matching source/locator in Synced Panes) — Graph mode is currently the
    only one of the three that reads `useFocus()`'s `subject`.
  These are additive: the interfaces this design introduced
  (`SourcePlugin`, `useFocus`, `HoverFocusProvider`) were built to make
  each of these an incremental addition later, not a rework.

## Non-goals

- A third source-format plugin (beyond PDF/XSD) — the abstraction supports
  it, implementing one is not part of this spec.
- Exact pixel-level visual design — colors, spacing, and precise layout are
  implementation-time decisions within the shadcn/Base UI system already in
  place, not fixed here.
- Real-time multi-user collaboration (live cursors, presence) — out of
  scope; the maker-checker model (propose/approve/reject) already handles
  multi-reviewer correctness without it.

## Definition of Done

- All three modes (Graph, Living Text, Synced Panes) are implemented,
  reachable from a persistent mode switcher, and share one focus model.
- Structure and Audit no longer exist as separate tabs — their content is
  reachable via Graph mode's zoom levels and filters.
- Corrections has no separate worklist page — proposing, approving, and
  rejecting all happen inline in Living Text.
- The reverse-lookup endpoint is real, tested against the real corpus, and
  used by Synced Panes' source→derived direction.
- The `SourceLocator`/plugin abstraction has two real implementations (PDF,
  XSD) and a passing plugin-conformance test suite, including a click
  round-trip assertion per plugin (render a locator's whole view, click it,
  assert the resulting locator matches).
- A live Playwright walkthrough exercises hover-preview, click-to-pin,
  mode-switching-preserves-focus, and Synced Panes' source→derived
  syncing, against the actual built-and-served app. (Derived→source
  syncing is not yet implemented — see "Known gaps" above — so it is not
  part of this Definition of Done's walkthrough.)

## Implementation sequencing

Built as a single implementation plan, not split across multiple plans the
way Plans A-D were (explicit direction: this design is one coherent,
interlocking vision, and its pieces — the focus model, the locator
abstraction, the three modes — don't stand alone as independently valuable
increments the way Plans A-D each did). The plan's own task ordering still
follows the natural dependency chain:

1. **Foundation** — client-side routing, the shared focus model, the
   `SourceLocator` type and plugin registry (backend + frontend), the
   reverse-lookup endpoint. No new visible UI yet beyond the mode switcher
   shell.
2. **Graph mode** — the one-glance overview, absorbing Structure and Audit.
3. **Living Text mode** — hover-transclusion, the Inspector panel, inline
   corrections (including the new propose-correction UI).
4. **Synced Panes mode** — the PDF and XSD plugins on the generic
   abstraction, bidirectional sync.

Executed via this project's existing Subagent-Driven Development workflow.
