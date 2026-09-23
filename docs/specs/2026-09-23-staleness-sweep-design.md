# Staleness Sweep — Design

## Context

This is the second sub-project from the source reference model's own
Roadmap (`docs/specs/2026-09-23-source-reference-model-design.md`, §1):
"a process that takes an existing `Reference`, re-resolves its selector(s)
against the *current* version of the subject document's `family`... and
collects the resulting outcome(s)." That spec deliberately stopped short
of defining what "current version" means or how many `Reference`s get
checked at once — this document answers both, and nothing else.

Two real constraints shaped this design, both discovered by checking the
actual repo rather than assuming:

1. `/work/ontologies` (the repo holding the real MiKaDiv-FM source files)
   is a real git repository (`github.com/OpenFASTER-Standard/ontologies`).
   Git itself is the version history and the update mechanism — someone
   re-fetches from BZSt and commits, exactly as `mikadiv-fm/sources/
   README.md` already documents. There is no separate persistence or
   fetch problem for this sub-project to solve.
2. The real files' names embed a version (`MiKaDiv_FM_Meldeart23_1.02.xsd`,
   `khb_mikadiv_fm_de_v9.pdf`), in two different, incompatible formats.
   "The current version of this family" is therefore not a fixed path, and
   is not something to derive by parsing either filename convention.

## Non-Goals

- **Not** a live-fetch mechanism against BZSt's real download page.
  Re-fetching and committing a new snapshot stays a human, git-committed
  action, per `mikadiv-fm/sources/README.md`'s own existing instructions.
- **Not** a general persistence layer for `Reference`s. This sub-project
  only defines how to find *the current source files*; where a corpus of
  already-cited `Reference`s themselves lives is the caller's concern
  (most likely: committed as files in a git repo too, once the extraction
  pipeline sub-project exists to produce them).
- **Not** review surfacing or a correction/revision workflow. This
  sub-project's output is a `SweepReport`; what happens with a flagged
  entry is a separate, later sub-project.
- **Not** a smart version-comparison mechanism. Resolving "current"
  never parses or compares version strings — see "Directory layout"
  below.

## Directory layout

`mikadiv-fm/sources/` is restructured from a flat, version-in-filename
layout into one subdirectory per whole-module snapshot, versioned by the
real MiKaDiv-FM schema release version — not a fetch date. Confirmed live:
every `MiKaDiv_FM_*.xsd` file already shares the exact same version
suffix, `1.02` (`ls mikadiv-fm/sources/xsd/ | grep -oE '_[0-9]+\.[0-9]+\.xsd$' | sort -u` → one distinct value). That version is the real, meaningful
identifier for one coherent fetch — BZSt publishes the whole XSD package
and the KHB/guidance PDFs together, per the existing README's own framing
("current as of the `xsd_mikadiv_fm.zip` v8 / `khb_mikadiv_fm.pdf` v9
release fetched 2026-09-14").

```
mikadiv-fm/sources/
  _current                    # plain text, one line: "1.02"
  1.02/
    xsd/MiKaDiv_FM_Meldeart23_1.02.xsd   # original real filenames, untouched
    xsd/din-norm-91379-datatypes.xsd
    khb/khb_mikadiv_fm_de_v9.pdf
    _manifest.json           # written once at fetch time, never edited after
  1.03/                       # a later re-fetch, whenever one happens --
    xsd/...                  # the old 1.02/ directory stays, nothing deleted
    khb/...
    _manifest.json
```

`_manifest.json` maps every family in that snapshot to its real filename,
as a path relative to the snapshot directory (covering both `xsd/` and
`khb/` in one file, so a caller never needs to separately know which
subdirectory a family lives in):

```json
{
  "MiKaDiv_FM_Meldeart23": "xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
  "din-norm-91379-datatypes": "xsd/din-norm-91379-datatypes.xsd",
  "khb_mikadiv_fm_de": "khb/khb_mikadiv_fm_de_v9.pdf"
}
```

Old snapshots are kept permanently — a real, browsable local archive, not
just something recoverable via `git log`. `_current` is the only file
that ever gets edited across a re-fetch; everything under a version
directory, once written, is immutable.

## `resolve_current_location`

```
resolve_current_location(module_root: str, family: str) -> ResolutionOutcome
```

Reuses `reference_model.model.ResolutionOutcome`/`Status` directly (no new
outcome vocabulary needed) — `raw_content` holds the resolved absolute
path when `RESOLVED`.

1. Read `{module_root}/_current`. Missing → `Status.NOT_FOUND` (this
   module hasn't adopted the snapshot convention, or genuinely has no
   current version — a legitimate case, not a bug).
2. Read `{module_root}/{snapshot}/_manifest.json`. **Missing → raise
   `CorpusIntegrityError`**, not a status: `_current` naming a snapshot
   with no manifest means the corpus itself is inconsistent, the same
   class of problem as an `XPathSelector` resolving to something
   uncanonicalizable — not something a sweep exists to report gracefully.
3. Look up `family` in the manifest. Missing → `Status.NOT_FOUND` (the
   family isn't tracked in this snapshot, or was intentionally dropped).
4. Resolve the manifest's relative path against the snapshot directory.
   **Path doesn't exist on disk, or resolves outside that snapshot
   directory (a `../`-escaping manifest entry, whether malicious or a
   hand-editing mistake) → raise `CorpusIntegrityError`** (same reasoning
   as step 2 — the manifest lied, or lied dangerously).
5. Otherwise → `Status.RESOLVED` with the resolved absolute path.

## `sweep()` and `SweepReport`

```python
@dataclass(frozen=True)
class FamilyResolutionFailure:
    family: str
    status: Status  # always NOT_FOUND here

@dataclass(frozen=True)
class SweepReport:
    results_by_key: dict[str, list[LeafCheckResult]]
    family_resolution_failures: tuple[FamilyResolutionFailure, ...]
    excluded_keys: tuple[str, ...]  # caller keys omitted from results_by_key, and why


def _collect_families(reference: Reference) -> set[str]:
    if isinstance(reference, Leaf):
        return {reference.subject_document.family}
    return set().union(*(_collect_families(part) for part in reference.parts))


def sweep(references: dict[str, Reference], module_root: str) -> SweepReport:
    all_families = set().union(*(_collect_families(ref) for ref in references.values()))

    overrides: dict[str, str] = {}
    failures: list[FamilyResolutionFailure] = []
    for family in all_families:
        outcome = resolve_current_location(module_root, family)
        if outcome.status == Status.RESOLVED:
            overrides[family] = outcome.raw_content
        else:
            failures.append(FamilyResolutionFailure(family=family, status=outcome.status))

    failed_families = {f.family for f in failures}
    results_by_key = {
        key: check_reference(ref, retrieval_overrides=overrides)
        for key, ref in references.items()
        if not (_collect_families(ref) & failed_families)
    }
    return SweepReport(results_by_key=results_by_key, family_resolution_failures=tuple(failures))
```

`references` is keyed by whatever identifier the caller uses for each
fact (a URI, a database key, anything) — `sweep()` doesn't invent a "Fact"
concept; it just needs a way to report results back against the caller's
own identifiers. `sweep()` operates against exactly one `module_root` per
call; a corpus spanning multiple modules (e.g. some facts citing
`mikadiv-fm/sources/`, others citing a future `kafe/sources/`) needs one
`sweep()` call per module, not a single call mixing both.

It recursively collects every distinct `family` across every `Leaf` in
every given `Reference` (walking `Union.parts`), resolves each exactly
once via `resolve_current_location`, and only builds a
`retrieval_overrides` entry (consumed by the already-built
`check_reference()`) for families that resolved.

For a family that failed to resolve, `sweep()` deliberately does not call
`check_reference()`/`check_leaf()` with that family absent from the
override map. `check_leaf()`'s own default — check against the `Leaf`'s
originally-stored `retrieval_uri` when no override is given — is exactly
right for its own primary use case (an ad hoc "did this one citation's
source change" call with no notion of "current" at all). It's simply the
wrong tool for the sweep's use case: silently falling back to the
original path here could report a misleading "unchanged" for a family the
corpus itself no longer tracks. So `sweep()` excludes any `Reference`
touching an unresolved family from `results_by_key` entirely — it only
ever shows up via `family_resolution_failures`, never through a per-leaf
outcome that looks like a normal check. That exclusion is silent unless
named somewhere, though, and "which facts went unchecked" is exactly the
question a reader of a large report would ask — so every excluded key is
also listed in `excluded_keys`, letting a caller enumerate what a sweep
*couldn't* tell them without re-walking every `Reference`'s families
against `family_resolution_failures` by hand.

Iteration order matters for reproducibility: `family_resolution_failures`
is built from a sorted family list, not raw `set` iteration order (which
varies run to run under Python's string-hash randomization) — a report
that can't be diffed or snapshot-compared defeats its own purpose as an
artifact for a later review-surfacing sub-project to consume.

## Testing strategy

Resolution happy-path tests run against the real, restructured
`mikadiv-fm/sources/` (once migrated per this spec) — real family names,
real snapshot `1.02`. Since only one real snapshot currently exists,
multi-snapshot behavior (a family resolving differently across two
snapshots, a stale `_current` pointer, a missing manifest, a manifest
naming a nonexistent file) is tested against a small synthetic directory
tree built in `tmp_path`, following the same real-data-first, synthetic-
only-for-genuinely-unavailable-cases pattern already used throughout
`reference_model`'s own tests.

- `resolve_current_location` against the real corpus: resolves a real
  family (e.g. `MiKaDiv_FM_Meldeart23`) to its real current path.
- A synthetic two-snapshot tree: `_current` pointing at the second
  snapshot resolves there, not the first.
- Missing `_current` → `NOT_FOUND`. Missing manifest for the pointed-at
  snapshot → `CorpusIntegrityError`. Family absent from a real manifest →
  `NOT_FOUND`. Manifest naming a nonexistent file → `CorpusIntegrityError`.
- `sweep()` over a batch of real `Reference`s (built via `cite()` against
  the real, restructured corpus): a family whose snapshot content changed
  reports through `results_by_key`; a family removed from the manifest
  reports through `family_resolution_failures` and is absent from
  `results_by_key` for every `Reference` that touched it.

## Roadmap: what this enables next

Same as the reference model's own roadmap, now one step closer: **review
surfacing** (how a `SweepReport`'s flagged entries get shown to a human
reviewer) and the **correction/revision workflow** both now have a real,
concrete input to consume (`SweepReport`) instead of a hypothetical one.
Neither is designed here.

## Definition of Done

- `mikadiv-fm/sources/` is restructured into the snapshot layout above,
  with a real `_current` and `_manifest.json` for the real `1.02`
  snapshot, covering all real families (verified by `resolve_current_location`
  resolving every one of them against the live corpus).
- `resolve_current_location` and `sweep()`/`SweepReport` are implemented
  with the semantics above.
- All tests listed above pass.
- Citing a real fact from the restructured corpus, then running `sweep()`
  against a `tmp_path`-based copy of that corpus with one deliberate change
  made to a second, synthetic snapshot (never the real repo — no fake
  version bump is ever committed to `mikadiv-fm/sources/` itself) and
  `_current` pointed at it, correctly reports that one change and nothing
  else as flagged.
