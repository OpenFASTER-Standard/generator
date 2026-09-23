# Review Surfacing — Design

## Context

This is the third sub-project from the reference model's own Roadmap
(`docs/specs/2026-09-23-source-reference-model-design.md`, §2, restated in
`docs/specs/2026-09-23-staleness-sweep-design.md`'s own roadmap section):
"how a `SweepReport`'s flagged entries get shown to a human reviewer."

Deliberately scoped narrower than that framing suggests: this document
does not pick a medium (no CLI, no web UI, no generated document format).
It defines only the presentation-agnostic transformation from a
`SweepReport` — a flat pile of per-leaf outcomes — into a shape organized
around the one real question a reviewer actually asks first: *what needs
my attention, and what kind of problem is it*. Rendering that shape into
something a human looks at (text, HTML, a terminal report, whatever) is
left to a later, separate sub-project, deliberately.

## Non-Goals

- **Not** a rendering layer. No output format, no CLI, no web UI. This
  produces data structures a later medium-specific piece consumes.
- **Not** re-resolving content for display. `Reference` stores no
  snippet by design (see the reference-model spec); deciding how much
  re-resolved context to show, and how to render it, is a rendering-layer
  concern, not a classification concern.
- **Not** a per-key mapping from an excluded key to the specific family
  that excluded it. `SweepReport` retains `family_resolution_failures`
  and `excluded_keys` as two separate lists; reconstructing which
  excluded which would require either re-walking the original
  `references` dict (which `SweepReport` doesn't retain) or extending
  `SweepReport`'s own shape again. Deliberately deferred until a real
  consumer needs it — both lists are still real, useful information on
  their own.
- **Not** a persistence layer, a scheduler, or anything that decides
  *when* a sweep runs. Takes a `SweepReport` as a plain input value.

## The `CONTENT`/`STRUCTURAL` distinction

The one substantively new idea this sub-project adds: every problematic
`LeafCheckResult` gets classified into exactly one of two kinds, because
they mean materially different things to a reviewer:

- **`STRUCTURAL`** — `outcome.status` is `NOT_FOUND`, `AMBIGUOUS`, or
  `UNCITABLE`. The citation itself no longer cleanly resolves — something
  was renamed, removed, or became ambiguous. The reviewer's first question
  is "is this still the same thing, moved or renamed, or genuinely gone?"
- **`CONTENT`** — `outcome.status` is `RESOLVED` but `hash_changed` is
  `True`. The citation still resolves to exactly one clean target; only
  what's there changed. The reviewer's first question is "did the meaning
  change, or was this a cosmetic edit?"

A `LeafCheckResult` with `RESOLVED` and `hash_changed=False` is healthy
and never appears in the output at all.

## Data model

```python
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
```

`ReviewSummary` is `frozen=True`, but `flagged` is a plain `dict` -- a
conscious, partial immutability: the dataclass itself can't be
reassigned field-by-field, but `flagged` can still be mutated in place
(`summary.flagged["x"] = (...)`) and `hash(summary)` still raises
`TypeError`. A caller that needs either guarantee in full (e.g. to use a
`ReviewSummary` as a dict/set key, or to hand it to code that assumes
true immutability) needs its own copy, not an assumption this type
enforces one. Not changed to `MappingProxyType` or a tuple-of-pairs here,
since nothing yet needs it and either would visibly complicate every
call site that builds or reads `flagged` as a plain dict for no current
benefit -- but a future consumer (the rendering layer this enables next)
should not assume it can rely on `frozen=True` meaning fully immutable.

```python
def summarize_for_review(report: SweepReport) -> ReviewSummary:
    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for key, results in report.results_by_key.items():
        problematic = []
        for result in results:
            if result.outcome.status == Status.RESOLVED:
                if result.hash_changed:
                    problematic.append(FlaggedLeaf(result.leaf, result.outcome, DriftKind.CONTENT))
                # RESOLVED + hash_changed False (or None, unreachable here
                # since Status.RESOLVED always sets hash_changed) is healthy.
            else:
                problematic.append(FlaggedLeaf(result.leaf, result.outcome, DriftKind.STRUCTURAL))
        if problematic:
            flagged[key] = tuple(problematic)

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=report.family_resolution_failures,
        excluded_keys=report.excluded_keys,
    )
```

`flagged` only ever contains keys with at least one problematic leaf — a
key with every leaf healthy is absent entirely, not present with an empty
tuple, so a caller can check "is this fact clean" with a plain `key not in
summary.flagged` rather than checking for emptiness.

`unresolved_families` and `excluded_keys` are verbatim pass-throughs from
the `SweepReport` — this function adds no new information about them,
only about the per-leaf drift classification.

## New module

`review_surfacing/` — a new top-level package, sibling to `reference_model/`
and `staleness_sweep/`, depending only on the latter (and, transitively,
`reference_model`). No new third-party dependencies.

## Testing strategy

Built from a real `SweepReport`, produced by actually calling `sweep()`
against the real, restructured corpus plus a `tmp_path`-based synthetic
snapshot with deliberate changes — the same pattern already established
in `staleness_sweep`'s own tests — rather than hand-constructing
`SweepReport`/`LeafCheckResult` objects directly, so the classification
logic is proven against real `Status`/`hash_changed` combinations the
rest of the system actually produces.

- A healthy leaf (`RESOLVED`, `hash_changed=False`) does not appear in
  `flagged` at all.
- A content-drifted leaf (`RESOLVED`, `hash_changed=True`, from a real
  mutated synthetic snapshot) is classified `DriftKind.CONTENT`.
- A structurally-broken leaf (`NOT_FOUND`, from a real renamed element in
  a synthetic snapshot) is classified `DriftKind.STRUCTURAL`.
- A fact with one healthy leaf and one problematic leaf (a real `Union`)
  appears in `flagged` with only the problematic leaf, not the healthy one.
- `unresolved_families` and `excluded_keys` on the resulting
  `ReviewSummary` exactly match the input `SweepReport`'s own values.

## Roadmap: what this enables next

The still-undecided rendering medium (CLI, generated document, web UI) now
has a real, presentation-agnostic `ReviewSummary` to consume instead of a
raw `SweepReport` or nothing at all. The **correction/revision workflow**
(what happens once a reviewer makes a call on a flagged entry) still has
no input to consume from this sub-project — that's a decision a rendering
layer or a reviewer's own tooling makes, not something `ReviewSummary`
itself needs to anticipate. Neither is designed here.

## Definition of Done

- `DriftKind`, `FlaggedLeaf`, `ReviewSummary`, and `summarize_for_review()`
  are implemented with the semantics above.
- All tests listed above pass, built from real `sweep()` calls against the
  real corpus plus synthetic snapshots, not hand-constructed report objects.
- A `SweepReport` with a mix of healthy, content-drifted, structurally-broken,
  and excluded entries produces a `ReviewSummary` whose `flagged` dict
  contains exactly the problematic keys, each correctly classified.
