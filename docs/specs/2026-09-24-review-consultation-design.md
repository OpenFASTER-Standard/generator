# Review Consultation — Design

## Context

This is the last still-open item from `review_recording`'s own Roadmap
(`docs/specs/2026-09-23-review-recording-design.md`): "should a later
`sweep()`/review pass consult existing review records to avoid re-flagging
a drift someone already approved." Grounded in real, converging prior art
researched before this design was drafted:

- **SARIF `partialFingerprints` / GitHub code-scanning alert dismissal** —
  a finding is matched across scans by a content fingerprint, not by
  rule/location identity alone; a dismissal only stays applied while that
  fingerprint keeps matching.
- **`git rerere`** — a conflict resolution is recorded and replayed keyed
  by a hash of the normalized conflict content itself; a different
  conflict (even in the same file/location) gets a different hash and is
  treated as unresolved.
- **SonarQube's issue lifecycle** — `Confirmed` ("yes, this is real") keeps
  an issue open/visible; only `Resolved`/`Won't Fix`/`False Positive` close
  it, and a closed issue that reappears unchanged is automatically
  `Reopened`.
- **Grype/Trivy's structured ignore files** — the more rigorous suppression
  formats scope an ignore to the exact package+version; "ignore this ID
  everywhere forever" is the weaker, legacy form.

All four independently converge on the same two rules this design applies:
suppression is scoped to a **fingerprint of the specific state reviewed**,
never to fact identity alone, and only an **accepted verdict suppresses** —
a confirmed real problem stays visible until it's actually fixed.

## Non-Goals

- **Not** a change to what a fresh `sweep()` reports. `sweep()` and
  `summarize_for_review()` still report every real drift; consultation
  only changes what a human is shown *afterward*.
- **Not** a way to review a `family_resolution_failure`/`excluded_key`.
  Consultation only ever concerns a specific `FlaggedLeaf`, the same scope
  `review_recording` already committed to.
- **Not** attaching past-review context (reasoning, reviewer, timestamp)
  to entries that remain visible after consultation. A suppressed entry
  disappears entirely; a visible entry is shown exactly as
  `summarize_for_review()` already produces it. Surfacing "this was
  already reviewed and rejected, here's why" alongside a still-visible
  entry is a real, natural enhancement, left to the Roadmap below.
- **Not** an interaction layer or a persistence/scheduling concern, same
  as every prior sub-project in this line.

## Extending `LeafCheckResult` and `FlaggedLeaf` with a fingerprint

`reference_model/cite.py`'s `check_leaf()` already computes the new
content's hash to decide `hash_changed`, but throws it away. Exposing it
avoids a second, duplicate `canonicalize_and_hash()` call later and avoids
`review_surfacing` needing its own resolver lookup:

```python
@dataclass(frozen=True)
class LeafCheckResult:
    leaf: Leaf
    outcome: ResolutionOutcome
    hash_changed: bool | None  # None unless outcome.status is RESOLVED
    new_content_hash: str | None  # None unless outcome.status is RESOLVED


def check_leaf(leaf: Leaf, retrieval_uri: str | None = None) -> LeafCheckResult:
    resolver = get_resolver(leaf.selector.type)
    uri = retrieval_uri if retrieval_uri is not None else leaf.subject_document.retrieval_uri
    outcome = resolver.resolve(leaf.selector, uri)
    if outcome.status != Status.RESOLVED:
        return LeafCheckResult(leaf=leaf, outcome=outcome, hash_changed=None, new_content_hash=None)
    new_digest = resolver.canonicalize_and_hash(outcome.raw_content)
    return LeafCheckResult(
        leaf=leaf,
        outcome=outcome,
        hash_changed=new_digest != leaf.content_hash.digest,
        new_content_hash=new_digest,
    )
```

`review_surfacing.summarize.FlaggedLeaf` gains one field, `fingerprint:
str` — the value a review's own `reviewed_fingerprint` must match to
suppress this exact state. For `CONTENT` drift it's `new_content_hash`;
for `STRUCTURAL` drift there is no content to hash, so it's the new
`Status`'s name (e.g. `"NOT_FOUND"`):

```python
@dataclass(frozen=True)
class FlaggedLeaf:
    leaf: Leaf
    outcome: ResolutionOutcome
    drift_kind: DriftKind
    fingerprint: str


def _classify(result: LeafCheckResult) -> FlaggedLeaf | None:
    if result.outcome.status == Status.RESOLVED:
        if result.hash_changed:
            return FlaggedLeaf(result.leaf, result.outcome, DriftKind.CONTENT, result.new_content_hash)
        return None
    return FlaggedLeaf(result.leaf, result.outcome, DriftKind.STRUCTURAL, result.outcome.status.name)
```

One field, one type (`str`), so nothing downstream ever branches on
`drift_kind` just to compare fingerprints.

## Simplifying `record_review()`

Every `FlaggedLeaf.leaf` is a single `Leaf`, never a `Union` —
`check_reference()` already flattens those into one `LeafCheckResult` per
leaf — so `family` and `drift_kind` are fully derivable from the
`FlaggedLeaf` itself. Taking the `FlaggedLeaf` directly instead of two
separately-threaded fields removes a way for a caller to pass a
`family`/`drift_kind` that doesn't actually match what was reviewed, and
captures the new `fingerprint` automatically:

```python
def record_review(
    reviews_dir: str,
    fact_key: str,
    flagged: FlaggedLeaf,
    reviewer: str,
    verdict: Verdict,
    reasoning: str,
) -> Leaf:
    Path(reviews_dir).mkdir(parents=True, exist_ok=True)
    review_id = str(uuid.uuid4())
    document = {
        "fact_key": fact_key,
        "family": flagged.leaf.subject_document.family,
        "drift_kind": flagged.drift_kind.value,
        "reviewed_fingerprint": flagged.fingerprint,
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

The written document gains the one new field, `reviewed_fingerprint`.

## New module: `review_consultation`

`review_consultation/consult.py`, a new top-level package depending on
`review_surfacing` and `review_recording` (and, transitively,
`reference_model`) — the natural integration point tying the review
pipeline's read side (`review_surfacing`) to its write side
(`review_recording`).

```python
@dataclass(frozen=True)
class ReviewRecord:
    fact_key: str
    family: str
    drift_kind: DriftKind
    reviewed_fingerprint: str
    reviewer: str
    reviewed_at: str
    verdict: Verdict
    reasoning: str


class ReviewLoadError(Exception):
    pass


_REQUIRED_FIELDS = (
    "fact_key", "family", "drift_kind", "reviewed_fingerprint",
    "reviewer", "reviewed_at", "verdict", "reasoning",
)


def load_reviews(reviews_dir: str) -> list[ReviewRecord]:
    records = []
    for path in sorted(Path(reviews_dir).glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ReviewLoadError(f"{path}: not valid JSON") from e
        if not isinstance(raw, dict):
            raise ReviewLoadError(f"{path}: expected a JSON object")
        missing = [f for f in _REQUIRED_FIELDS if f not in raw]
        if missing:
            raise ReviewLoadError(f"{path}: missing field(s) {missing}")
        try:
            drift_kind = DriftKind(raw["drift_kind"])
            verdict = Verdict(raw["verdict"])
        except ValueError as e:
            raise ReviewLoadError(f"{path}: invalid drift_kind/verdict value") from e
        records.append(ReviewRecord(
            fact_key=raw["fact_key"],
            family=raw["family"],
            drift_kind=drift_kind,
            reviewed_fingerprint=raw["reviewed_fingerprint"],
            reviewer=raw["reviewer"],
            reviewed_at=raw["reviewed_at"],
            verdict=verdict,
            reasoning=raw["reasoning"],
        ))
    return records


def apply_reviews(summary: ReviewSummary, reviews: list[ReviewRecord]) -> ReviewSummary:
    approved = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.APPROVED
    }
    rejected = {
        (r.fact_key, r.drift_kind, r.reviewed_fingerprint)
        for r in reviews if r.verdict == Verdict.REJECTED
    }

    flagged: dict[str, tuple[FlaggedLeaf, ...]] = {}
    for fact_key, entries in summary.flagged.items():
        kept = tuple(
            fl for fl in entries
            if (fact_key, fl.drift_kind, fl.fingerprint) not in approved
            or (fact_key, fl.drift_kind, fl.fingerprint) in rejected
        )
        if kept:
            flagged[fact_key] = kept

    return ReviewSummary(
        flagged=flagged,
        unresolved_families=summary.unresolved_families,
        excluded_keys=summary.excluded_keys,
    )
```

`load_reviews()` on a `reviews_dir` that doesn't exist yet (no review has
ever been written) returns `[]` — `Path.glob()` on a missing directory is
empty, not an error, matching every other "first one ever" case in this
project being treated as normal, not special.

**Malformed review files fail loud.** These are files this system itself
generates, not adversarial external input, so a file that isn't valid
JSON, isn't a JSON object, is missing a required field, or has an invalid
`drift_kind`/`verdict` value raises `ReviewLoadError` rather than being
silently skipped — silently dropping a real review would risk treating
genuinely-reviewed drift as never having been looked at, or (worse) mask
a corruption bug in `record_review()` itself.

**Tie-break rule**: if both an `APPROVED` and a `REJECTED` record exist
for the exact same `(fact_key, drift_kind, reviewed_fingerprint)`,
`REJECTED` wins and the entry stays visible — a contradictory review
history should never cause a real problem to be hidden.

## Testing strategy

Dogfooded end-to-end, the same way `review_recording` tested itself:
build a real `ReviewSummary` from an actual `sweep()` over a synthetic
snapshot with deliberate mutations, call the real `record_review()`
against a `tmp_path` reviews directory, then call the real `load_reviews()`
+ `apply_reviews()` and check what comes out.

- A `CONTENT`-flagged entry disappears from `flagged` after an `APPROVED`
  review recorded against that exact `FlaggedLeaf`.
- The same fact, mutated *again* to a different value after that approval
  (a second real snapshot mutation, different from the first), still
  appears — a new, unreviewed fingerprint is not covered by the old
  approval.
- A `STRUCTURAL`-flagged entry (a real renamed/removed element) disappears
  after an `APPROVED` review recorded against it.
- A `REJECTED` review does not suppress its entry — it remains in `flagged`
  unchanged.
- Both an `APPROVED` and a `REJECTED` review recorded against the same
  `FlaggedLeaf` (same fingerprint): the entry remains visible.
- A fact with two problematic leaves (a real `Union`) where only one is
  approved: the key remains present in `flagged`, containing only the
  still-unreviewed leaf.
- A fact whose every problematic leaf gets approved: the key is dropped
  from `flagged` entirely, not left present with an empty tuple.
- `unresolved_families` and `excluded_keys` on the output `ReviewSummary`
  are unchanged from the input.
- `load_reviews()` against a reviews directory that doesn't exist yet
  returns `[]`.
- `load_reviews()` raises `ReviewLoadError` on: malformed JSON, a JSON
  array/scalar instead of an object, a missing required field, and an
  invalid `drift_kind`/`verdict` value.

## Roadmap: what this enables next

The review pipeline this line of sub-projects has been building
(`staleness_sweep` → `review_surfacing` → `review_recording` →
`review_consultation`) is now closed end-to-end: a sweep's drift can be
classified, shown, decided on, recorded, and consulted so the same
decision doesn't need to be re-made on every future sweep. Still open,
named but not designed here:

- **The interaction layer** that actually drives a human through
  `summarize_for_review()`'s output, collects their verdict, and calls
  `record_review()` — every sub-project in this line has deferred this.
- **Surfacing past-review context on entries that remain visible**
  (a `REJECTED` review's own reasoning, or a superseded `APPROVED`
  review's fingerprint, shown alongside a still-flagged entry) — named as
  a Non-Goal above, a real enhancement once there's a real consumer.
- **Listing/searching review records** for purposes other than
  consultation (an audit view, "show me everything Julian has approved") —
  `load_reviews()` provides the raw material but has no filtering/query
  API beyond "load everything in this directory."

## Definition of Done

- `LeafCheckResult` gains `new_content_hash`; `FlaggedLeaf` gains
  `fingerprint`; `record_review()` takes a `FlaggedLeaf` instead of
  separate `family`/`drift_kind` arguments — all with the semantics above.
- `ReviewRecord`, `ReviewLoadError`, `load_reviews()`, and `apply_reviews()`
  are implemented with the semantics above in a new `review_consultation`
  package.
- All tests listed above pass, built from real `sweep()`/`record_review()`
  calls against real synthetic snapshots and a real `tmp_path` reviews
  directory, not hand-constructed report/record objects.
