# Review Recording — Design

## Context

This is the fourth sub-project from the reference model's own Roadmap
(`docs/specs/2026-09-23-source-reference-model-design.md`, §3): "what
happens once a reviewer makes a call on a flagged entry." That roadmap
entry assumed a new "Fact"/"Revision" data model would be needed — this
document takes a different, simpler path, settled during brainstorming: a
reviewer's decision doesn't need a new type at all. It becomes **another
real, citable document**, handled by the exact same `Reference`/`cite()`
machinery already built for XSDs and PDFs. The only genuinely new piece
this requires is a selector for a source format this project hasn't
needed yet: JSON.

## Non-Goals

- **Not** a "Fact" or "Revision" data model. This project has never
  modeled a fact's *value* — only citations to real source spans — and
  this sub-project doesn't start now. A review record's job is to *exist*
  as a citable document, nothing more.
- **Not** an interaction layer. Nothing here decides *when* a human
  reviews something, prompts them, or collects their input from a UI.
  `record_review()` takes the reviewer's decision as plain arguments;
  producing those arguments is a later, separate concern.
- **Not** automated re-baselining. Recording a review does not itself
  change what a future `sweep()` flags — it produces a new, independent,
  citable fact about a past decision. Whether/how a later sweep should
  consult past reviews to avoid re-flagging the same drift is a real,
  natural next question, explicitly left to the Roadmap below.
- **Not** staleness-checking for review records themselves. Each one is
  permanent and immutable once written — no snapshot, no `_current`
  pointer, no manifest. It's cited by its own fixed path, like any other
  one-off document.

## `JsonSelector`

`reference_model/selectors/json_selector.py`, sibling to `xpath_selector.py`
and `svg_selector.py`. Addresses a value inside a JSON document via a real
standard: **RFC 6901 JSON Pointer** (e.g. `/verdict`, `/reasoning`) — the
JSON analogue of XPath.

```python
@dataclass(frozen=True)
class JsonSelector:
    type: str
    pointer: str  # RFC 6901 JSON Pointer, e.g. "/verdict" or "" for the whole document

    @staticmethod
    def create(pointer: str) -> "JsonSelector":
        return JsonSelector(type="JsonSelector", pointer=pointer)
```

Unlike XPath, a JSON Pointer always addresses exactly zero or one
location — there is no "matches multiple" case. So this selector's
`resolve()` only ever returns `Status.RESOLVED` or `Status.NOT_FOUND`;
`AMBIGUOUS`/`UNCITABLE` are unreachable for this selector type, the same
way `AMBIGUOUS` is unreachable for `SvgSelector`. Missing file, malformed
JSON, and a pointer that doesn't resolve (a missing object key, an
out-of-range array index, indexing into a scalar) all map to `NOT_FOUND`
— mirroring `XPathSelector`'s own missing-file/malformed-document handling.

```python
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


def canonicalize_and_hash(raw_content: object) -> str:
    # JCS-inspired (RFC 8785's real idea: sorted object keys, no incidental
    # whitespace), not byte-exact RFC 8785 -- JCS also mandates
    # ECMAScript-compatible number formatting, which plain json.dumps
    # doesn't replicate for edge cases like whole-number floats. Review-
    # result documents are all strings, so this doesn't matter in
    # practice -- noted here for the same reason XPathSelector's own
    # C14N-1.0-not-1.1 gap is noted: an honest, deliberate simplification.
    canonical = json.dumps(raw_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_pointer(document: object, pointer: str) -> object:
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


register("JsonSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
```

## Review-result document shape and location

One plain JSON file per review decision, in `ontologies/mikadiv-fm/reviews/`
(a new directory, sibling to `sources/`, same real git-tracked-history
convention as everything else in that repo):

```json
{
  "fact_key": "fact-1",
  "family": "MiKaDiv_FM_Meldeart23",
  "drift_kind": "CONTENT",
  "reviewer": "julian.nalenz@divizend.com",
  "reviewed_at": "2026-09-23T14:00:00+00:00",
  "verdict": "approved",
  "reasoning": "Confirmed with BZSt: non-substantive schema clarification."
}
```

Filename is `{review_id}.json`, where `review_id` is a fresh `uuid.uuid4()`
string — no coordination needed, and no meaning is attached to the ID
beyond uniqueness. Each file is immutable and permanent once written.

## `record_review()`

New small module, `review_recording/record.py`.

```python
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

Writes the document above to `{reviews_dir}/{review_id}.json` (creating
`reviews_dir` if it doesn't exist yet — the first review ever written is a
real, expected case, not a special one), then calls `cite()` with
`SubjectDocument(family=f"review-{review_id}", version="1", retrieval_uri=<the file path>)`
and `JsonSelector.create("")` (the whole document, not a specific field —
a review decision is one atomic unit of meaning, not several independently
citable facts), returning the resulting `Leaf`. `family` is prefixed
`review-` so a review's own family never collides with a real schema
family in a combined sweep or citation list. `version` is the constant
`"1"` — there's only ever one version of a specific review record, by
definition of it being immutable.

## Testing strategy

`JsonSelector` is tested directly against hand-written real JSON fixtures
covering the JSON Pointer edge cases the implementation must get right:
a pointer resolving to a nested object field, an array index, a value
that is `null`/`false`/`0` (falsy-but-present -- must not be
misclassified as `NOT_FOUND` by a truthiness bug), and a pointer
containing RFC 6901's own escape sequences (`~0` for `~`, `~1` for `/`).

`record_review()` is tested by actually calling it and then citing and
re-checking its own real output — dogfooding, not synthetic fixtures: the
JSON file `record_review()` produces is a genuine artifact of this system,
so there's no need for a separate "real vs. synthetic" split the way
`staleness_sweep`'s tests needed one for the MiKaDiv-FM corpus. Covers:
the returned `Leaf` actually resolves and hashes; the written file's
content matches every argument passed in; `reviews_dir` gets created when
it doesn't already exist; and re-`check_leaf`-ing the same file reports
`RESOLVED` with `hash_changed=False` (an unmodified review record is
correctly seen as unchanged, not accidentally flagged).

## Roadmap: what this enables next

The real, natural next question — should a later `sweep()`/review pass
consult existing review records to avoid re-flagging a drift someone
already approved — now has a real, concrete candidate mechanism to build
against (cite the review record's `fact_key`/`family` fields, compare
against the current sweep's own flagged entries), but is not designed
here. Also still open: the interaction layer that actually calls
`record_review()` with a real human's decision, and whether/how review
records themselves ever need to be searched or listed (today, citing one
requires already knowing its file path).

## Definition of Done

- `JsonSelector` is implemented with the semantics above and registered
  in the selector-type registry.
- `record_review()` and `Verdict` are implemented with the semantics above.
- All tests listed above pass.
- Calling `record_review()` for a real flagged entry produces a real JSON
  file in `ontologies/mikadiv-fm/reviews/`, and the returned `Leaf`
  successfully re-resolves via `check_leaf()` with `hash_changed=False`.
