"""English documentation extraction from BZSt's official Annex PDF
(khb_mikadiv_fm_anlage_en_v3.pdf), matched by real element/attribute/
type name against an already-extracted xsdo: graph, attached as a
second, @en-tagged xsdo:documentation value alongside the XSD's own
untagged German text. In scope for this sub-project per explicit
instruction (see the extraction design spec) -- not deferred.

pdfplumber's own extract_tables() garbles this PDF's nested Attributes
sub-tables (verified directly -- see this plan's Task 7 Step 1);
word-position clustering via extract_words() is the real,
verified-working alternative used here -- but only once scoped per
real section block via the state machine below. An earlier, page-wide
version of this same clustering approach was tried and found to
silently corrupt many real names' text (heading/"Used by" text
leaking into attribute rows, and separate real occurrences of the same
name being concatenated together) -- see this task's own Interfaces
section for the four specific, confirmed failure modes this state
machine exists to avoid.

Real, confirmed risk this module treats as a hard safety rule, not an
edge case: ~15 of this corpus's real local names (e.g. Bezeichnung,
Kontonummer, Position) genuinely mean different things -- with
genuinely different real English text -- in different real type
contexts. attach_english_documentation refuses to attach when a name's
occurrences disagree, rather than silently picking one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pdfplumber
from rdflib import Graph, Literal, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_MARGIN_X = 70.0  # real section headings start at x0~=60; "Used by"
                   # back-reference entries are indented to x0~=137 --
                   # confirmed live against MiKaDiv_FM_1.02's real
                   # DLMeldepflichtig/MeldungListe45cType page.
_COLUMN_X_TOLERANCE = 5.0

# Real artifact, confirmed on pages 213-214: a long element path
# occasionally doesn't fit on its own heading line and wraps onto the
# very next visual line at the same left margin instead (e.g. "element"
# alone, then "SelbststaendigeMeldungMitOrdnungsnummerType/KontoListe/
# BescheinigteSteuern" on the next line) -- these keywords are the
# real section-label lines that can otherwise appear at that same
# margin, used to tell a genuine wrapped-heading continuation apart
# from the next real structural line.
_SECTION_KEYWORDS = {
    "Diagram", "Namespace", "Type", "Children", "Name", "Used",
    "Documentation", "Documentatio", "Attributes", "Identity",
    "element", "complexType",
}


@dataclass(frozen=True)
class AttachmentReport:
    attached: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def _line_groups(words: list[dict]) -> dict[float, list[dict]]:
    lines: dict[float, list[dict]] = {}
    for word in words:
        lines.setdefault(round(word["top"], 1), []).append(word)
    return {top: sorted(ws, key=lambda w: w["x0"]) for top, ws in lines.items()}


def _heading_trailing_name(heading: str) -> str:
    # "element MiKaDivFMRoot/MiKaDiv_FM_45b" -> "MiKaDiv_FM_45b";
    # "complexType AntwortListeType" -> "AntwortListeType".
    path = heading.split(" ", 1)[1]
    return path.rsplit("/", 1)[-1]


def extract_name_occurrences(pdf_path: str) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}

    state = "NONE"
    current_heading: str | None = None
    heading_doc_parts: list[str] = []
    current_row_name: str | None = None
    row_doc_parts: list[str] = []
    name_x = doc_x = None

    def flush_heading_doc() -> None:
        nonlocal heading_doc_parts
        if current_heading is not None and heading_doc_parts:
            name = _heading_trailing_name(current_heading)
            occurrences.setdefault(name, []).append(" ".join(heading_doc_parts).strip())
        heading_doc_parts = []

    def flush_row() -> None:
        nonlocal current_row_name, row_doc_parts
        if current_row_name is not None and row_doc_parts:
            occurrences.setdefault(current_row_name, []).append(" ".join(row_doc_parts).strip())
        current_row_name = None
        row_doc_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = _line_groups(page.extract_words())
            tops = sorted(lines)
            idx = 0
            while idx < len(tops):
                top = tops[idx]
                line = lines[top]
                texts = [w["text"] for w in line]
                joined = "".join(texts)

                if texts[0] in ("element", "complexType") and line[0]["x0"] < _MARGIN_X:
                    flush_row()
                    flush_heading_doc()
                    heading_texts = list(texts)
                    if idx + 1 < len(tops):
                        next_line = lines[tops[idx + 1]]
                        next_texts = [w["text"] for w in next_line]
                        if (
                            next_line[0]["x0"] < _MARGIN_X
                            and next_texts[0] not in _SECTION_KEYWORDS
                        ):
                            heading_texts.extend(next_texts)
                            idx += 1
                    current_heading = " ".join(heading_texts)
                    state = "NONE"
                    idx += 1
                    continue
                if texts[0] == "Used" and len(texts) >= 2 and texts[1] == "by":
                    flush_row()
                    state = "USED_BY"
                    idx += 1
                    continue
                # Must also require "Type" and "Use": a real Identity-constraints
                # table has its own, differently-shaped header line ("Name Refer
                # Selector Field(s) Documentation" -- confirmed real on pages
                # 163/177/213) that otherwise satisfies a bare "Name" + "Documentation"
                # check just as well as a real Attributes table header does, and
                # would wrongly flip state into ATTRIBUTES for that unrelated table.
                if (
                    texts[0] == "Name"
                    and "Type" in texts
                    and "Use" in texts
                    and "Documentation" in texts
                ):
                    flush_row()
                    name_x = line[0]["x0"]
                    doc_x = next(w["x0"] for w in line if w["text"] == "Documentation")
                    state = "ATTRIBUTES"
                    idx += 1
                    continue
                if joined in ("Documentation", "Documentatio"):
                    flush_row()
                    state = "TRAILING_DOC"
                    idx += 1
                    continue

                if state == "ATTRIBUTES":
                    name_word = next(
                        (w for w in line if abs(w["x0"] - name_x) < _COLUMN_X_TOLERANCE), None
                    )
                    doc_words = [w for w in line if w["x0"] >= doc_x - _COLUMN_X_TOLERANCE]
                    doc_text = " ".join(w["text"] for w in doc_words)
                    if name_word is not None:
                        flush_row()
                        current_row_name = name_word["text"]
                        if doc_text:
                            row_doc_parts.append(doc_text)
                    elif doc_text:
                        row_doc_parts.append(doc_text)
                elif state == "TRAILING_DOC":
                    if texts != ["n"]:  # real split-word "Documentation" artifact suffix
                        heading_doc_parts.append(" ".join(texts))
                # USED_BY and NONE states: this line is real, but out of
                # scope for name->documentation extraction (a back-reference
                # entry, or a Diagram/Namespace/Type/Children/Identity-
                # constraints line).
                idx += 1

        flush_row()
        flush_heading_doc()

    return occurrences


def attach_english_documentation(graph: Graph, pdf_path: str) -> AttachmentReport:
    occurrences = extract_name_occurrences(pdf_path)
    report = AttachmentReport()

    for subject in set(graph.subjects(XSDO.name, None)):
        name = str(graph.value(subject, XSDO.name))
        texts = occurrences.get(name)
        if not texts:
            report.unmatched.append(name)
            continue
        distinct_texts = set(texts)
        if len(distinct_texts) > 1:
            report.ambiguous.append(name)
            continue
        graph.add((subject, XSDO.documentation, Literal(next(iter(distinct_texts)), lang="en")))
        report.attached.append(name)

    return report
