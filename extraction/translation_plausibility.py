"""Plausibility checks for attached (German, English) xsdo:documentation
pairs -- a different, complementary concern from Task 7's own
ambiguity-safety gate (which decides *whether* to attach at all). This
module audits whatever *did* get attached, and reports real coverage
across the whole corpus so gaps stay visible instead of silent.

Real heuristics, chosen because they're checkable without a
translation-quality oracle: non-empty, a length-ratio bound generous
enough for real DE/EN sentence-structure differences but tight enough
to catch truncation or a wrong-row attachment, and a shared-token check
for the numeric/legal-reference tokens (paragraph numbers, acronyms)
real administrative prose repeats verbatim across languages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rdflib import Graph, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_MIN_LENGTH_RATIO = 0.3
_MAX_LENGTH_RATIO = 3.0
_TOKEN_PATTERN = re.compile(r"\b[A-Z]{2,}[0-9]*\b|\b\d+[a-zA-Z]?\b")


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
