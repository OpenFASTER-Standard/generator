"""Plausibility checks for attached (German, English) xsdo:documentation
pairs -- a different, complementary concern from Task 7's own
ambiguity-safety gate (which decides *whether* to attach at all). This
module audits whatever *did* get attached, and reports real coverage
across the whole corpus so gaps stay visible instead of silent.

Real heuristics, chosen because they're checkable without a
translation-quality oracle: non-empty, a length-ratio bound generous
enough for real DE/EN sentence-structure differences but tight enough
to catch truncation or a wrong-row attachment, a shared-token check
for the numeric/legal-reference tokens (paragraph numbers, acronyms)
real administrative prose repeats verbatim across languages, and a
structural-artifact check for literal PDF section-heading vocabulary
that should never appear in real translated prose.

The structural-artifact check is defense-in-depth, not a replacement
for fixing extraction bugs at the source: it exists so that some
*future*, still-undiscovered gap in extraction.annex_pdf's own
heading-boundary detection (the same species of bug fixed there for
"simpleType" -- see that module's own heading-detection comment) still
gets caught here even if the root cause isn't fixed in time. The token
set below is grounded in real corrupted text observed live during this
module's own development, when a "simpleType" heading-detection gap in
extraction.annex_pdf let several real simpleType sections' own heading
lines and documentation silently concatenate onto a neighboring name's
English text -- e.g. real (pre-fix) corrupted text for "Ergebnis"
started "Return value for verifying this person. simpleType
AuslandSteuerNr Namespace http://www.itzbund.de/... Type restriction
ofstd:NameType Attributes ...".

Two more checks added during the final whole-branch review:

- `extra_shared_token` (Fix 2): the exact reverse of
  `missing_shared_token` -- tokens present in the English text but
  absent from the German text. This is precisely the shape of the real
  page-footer bug fixed in extraction.annex_pdf (a stray trailing page
  number, e.g. "Official serial number. 196") and exists here as the
  same kind of defense-in-depth as the structural-artifact check, for
  any future gap of the same shape.
- `untranslated` (Fix 4): the German and English text are byte-identical
  after stripping -- a real, confirmed sign of an untranslated source
  entry in the official Annex PDF itself (e.g. `BruttoBescheinigteSteuern`,
  still German, just tagged `@en`). Exempted: a subject whose own
  `xsdo:name` is short and acronym-shaped (e.g. `COAF`), since this
  corpus's one real identical pair of that shape is genuinely correct --
  `COAF`'s own real German xs:documentation is already the English
  phrase "Corporate Action Event Reference.", an untranslated technical
  loanword, not a translation gap (see `_ACRONYM_NAME_PATTERN`'s own
  comment for the full real evidence).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rdflib import Graph, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_MIN_LENGTH_RATIO = 0.3
_MAX_LENGTH_RATIO = 3.0
_TOKEN_PATTERN = re.compile(r"\b[A-Z]{2,}[0-9]*\b|\b\d+[a-zA-Z]?\b")

# Literal PDF section-heading/table vocabulary that leaks into English
# documentation text only when a heading-boundary gap somewhere in
# extraction.annex_pdf lets one section's own structural markup fall
# through into a neighboring name's accumulated text -- confirmed real
# via the "simpleType" gap fixed in that module (see its own
# heading-detection comment). None of these ever appear in genuine
# translated administrative prose, so a literal, case-sensitive
# substring match is deliberately used instead of a fuzzier check.
_STRUCTURAL_ARTIFACT_TOKENS = ("simpleType", "complexType", "Namespace", "restriction of")

# Fix 4 (final whole-branch review): a subject's own real xsdo:name is
# used to decide the acronym exception, not the identical text itself --
# grounded in the one real case this corpus actually has. COAF's own real
# German xs:documentation is, verbatim, "Corporate Action Event
# Reference." (confirmed directly in MiKaDiv_FM_Fachtypen_1.02.xsd) --
# an English financial-industry initialism used as-is in the German
# source, with no separate translation needed or attempted, so its real
# English annex text is genuinely, correctly identical -- not an
# untranslated gap. That identical TEXT is a full sentence, not itself
# short/acronym-shaped, so the exception has to key off the *name* (short,
# all-uppercase/digits) instead. Checked against the real corpus: among
# the 20 real byte-identical (German, English) pairs found, COAF's name
# is the only one matching this shape -- every other one (e.g.
# BruttoBescheinigteSteuern) is a real untranslated gap that must still
# be flagged.
_ACRONYM_NAME_PATTERN = re.compile(r"[A-Z][A-Z0-9]{1,9}")


@dataclass(frozen=True)
class PlausibilityIssue:
    kind: str
    subject_name: str
    detail: str


@dataclass(frozen=True)
class CoverageReport:
    total_documented_subjects: int
    attached: int
    ambiguous: int
    unmatched: int


def _shared_tokens_missing(german: str, english: str) -> set[str]:
    german_tokens = set(_TOKEN_PATTERN.findall(german))
    english_tokens = set(_TOKEN_PATTERN.findall(english))
    return german_tokens - english_tokens


def _shared_tokens_extra(german: str, english: str) -> set[str]:
    # Symmetric, reverse-direction counterpart to _shared_tokens_missing
    # (Fix 2, final whole-branch review): tokens present in the ENGLISH
    # text but absent from the German text -- exactly the shape of the
    # real page-footer bug (extraction.annex_pdf's TRAILING_DOC state
    # appending a stray page-number line onto English documentation text,
    # e.g. "Official serial number. 196"). This check would have caught
    # that bug directly, as defense-in-depth alongside the source fix.
    german_tokens = set(_TOKEN_PATTERN.findall(german))
    english_tokens = set(_TOKEN_PATTERN.findall(english))
    return english_tokens - german_tokens


def _is_acronym_name(name: str) -> bool:
    return bool(_ACRONYM_NAME_PATTERN.fullmatch(name))


def check_translation_plausibility(graph: Graph) -> list[PlausibilityIssue]:
    issues: list[PlausibilityIssue] = []

    for subject in set(graph.subjects(XSDO.documentation, None)):
        docs = list(graph.objects(subject, XSDO.documentation))
        german = next((d for d in docs if d.language in (None, "de")), None)
        english = next((d for d in docs if d.language == "en"), None)
        if german is None or english is None:
            continue

        name = str(graph.value(subject, XSDO.name) or subject)
        german_text, english_text = str(german).strip(), str(english).strip()

        if not english_text:
            issues.append(PlausibilityIssue("empty", name, "English text is empty"))
            continue

        if german_text == english_text and not _is_acronym_name(name):
            issues.append(
                PlausibilityIssue(
                    "untranslated", name,
                    f"German and English text are byte-identical: {german_text!r}",
                )
            )

        ratio = len(english_text) / max(len(german_text), 1)
        if not (_MIN_LENGTH_RATIO <= ratio <= _MAX_LENGTH_RATIO):
            issues.append(
                PlausibilityIssue(
                    "length_ratio", name,
                    f"ratio={ratio:.2f} (german={len(german_text)} chars, "
                    f"english={len(english_text)} chars)",
                )
            )

        missing = _shared_tokens_missing(german_text, english_text)
        if missing:
            issues.append(
                PlausibilityIssue(
                    "missing_shared_token", name,
                    f"tokens in German but not English: {sorted(missing)}",
                )
            )

        extra = _shared_tokens_extra(german_text, english_text)
        if extra:
            issues.append(
                PlausibilityIssue(
                    "extra_shared_token", name,
                    f"tokens in English but not German: {sorted(extra)}",
                )
            )

        found_artifacts = [t for t in _STRUCTURAL_ARTIFACT_TOKENS if t in english_text]
        if found_artifacts:
            issues.append(
                PlausibilityIssue(
                    "structural_artifact", name,
                    f"English text contains PDF structural markup: {found_artifacts}",
                )
            )

    return issues


def check_translation_coverage(graph: Graph, occurrences: dict[str, list[str]]) -> CoverageReport:
    documented_subjects = set(graph.subjects(XSDO.documentation, None))
    attached = ambiguous = unmatched = 0

    for subject in documented_subjects:
        name = str(graph.value(subject, XSDO.name))
        texts = occurrences.get(name)
        if not texts:
            unmatched += 1
        elif len(set(texts)) > 1:
            ambiguous += 1
        else:
            attached += 1

    return CoverageReport(
        total_documented_subjects=len(documented_subjects),
        attached=attached,
        ambiguous=ambiguous,
        unmatched=unmatched,
    )
