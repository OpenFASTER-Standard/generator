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

import re
from dataclasses import dataclass, field

import pdfplumber
from rdflib import Graph, Literal, Namespace

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_MARGIN_X = 70.0  # real section headings start at x0~=60; "Used by"
                   # back-reference entries are indented to x0~=137 --
                   # confirmed live against MiKaDiv_FM_1.02's real
                   # DLMeldepflichtig/MeldungListe45cType page.
_COLUMN_X_TOLERANCE = 5.0

# Real, confirmed page-footer artifact (Fix 2, final whole-branch review):
# every one of this PDF's 262 real pages (792pt tall) has a lone page-number
# line in its footer, a single word matching \d{1,3}, at top~=736.0 -- with a
# hard, exception-free gap against real body content, whose lowest real line
# was confirmed (by inspecting every page's own word positions directly) to
# never exceed top=710.5. Before this fix, TRAILING_DOC's own accumulation
# didn't recognize this line and appended the page number straight onto the
# current heading's documentation text (e.g. "Official serial number. 196"
# for AOrdNr) -- corrupting 13 real names' attached English text, and
# fabricating false ambiguity for at least 4 more names whose real
# occurrences were otherwise byte-identical except for a trailing page
# number (e.g. Adresse, Anschrift).
_PAGE_FOOTER_TOP_THRESHOLD = 720.0
_PAGE_FOOTER_PATTERN = re.compile(r"\d{1,3}")


def _is_page_footer_line(texts: list[str], top: float) -> bool:
    return (
        len(texts) == 1
        and bool(_PAGE_FOOTER_PATTERN.fullmatch(texts[0]))
        and top > _PAGE_FOOTER_TOP_THRESHOLD
    )


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
    "element", "complexType", "simpleType",
}

# The 5 real column keywords of a real Attributes table header ("Name Type
# Use Default Documentation"). Real, confirmed real-PDF rendering artifact,
# same species as the already-known "Documentation"->"Documentatio"+"n"
# split but hitting different words on different pages, at varying
# truncation depths: "Use"->"Us"+"e", "Default"->"Defa"/"Defaul"+"ult"/"t",
# "Documentation"->"Documentat"/"Documentati"/"Documentatio"+"ion"/"on"/"n"
# -- confirmed on at least 17 real pages (170, 172, 187, 191, 202, 218, 226,
# 240, 242, 245, 257, 258, 259 among them). A bare "Type"+"Use" literal
# check is defeated by this the same way a bare "Documentation" literal
# check would be -- see _complete_split_header_words, which reconstructs
# these column words generally rather than special-casing each observed
# split point.
_ATTRIBUTES_HEADER_KEYWORDS = ("Name", "Type", "Use", "Default", "Documentation")


def _complete_split_header_words(
    columns: list[tuple[float, str]], candidate_line: list[dict]
) -> tuple[list[tuple[float, str]], bool]:
    """Try to complete this header's own column words against a nearby
    line's words at the exact same x0 column position. Only ever completes
    a column into one of the 5 real Attributes-header keywords -- a
    genuine first attribute row happens to share the Name column's own x0
    (that's how the table's columns line up), but its own real text never
    happens to *equal* one of these 5 keywords once concatenated, so this
    can't misread a real row as more header text.
    """
    completed = False
    new_columns = list(columns)
    for word in candidate_line:
        for i, (col_x0, col_text) in enumerate(new_columns):
            if abs(word["x0"] - col_x0) >= _COLUMN_X_TOLERANCE:
                continue
            candidate_full = col_text + word["text"]
            if candidate_full != col_text and candidate_full in _ATTRIBUTES_HEADER_KEYWORDS:
                new_columns[i] = (col_x0, candidate_full)
                completed = True
    return new_columns, completed


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

                if _is_page_footer_line(texts, top):
                    # Skip a lone page-number footer line entirely -- it
                    # must never be accumulated into TRAILING_DOC's or
                    # ATTRIBUTES' row-continuation text (see this module's
                    # own _is_page_footer_line docstring/comment above).
                    idx += 1
                    continue

                # "simpleType" is a real, common heading-start keyword too (44
                # real headings, pages 63-75/155-156/205/215/259-260) --
                # omitting it here (found live via Task 8's own plausibility
                # audit, see translation_plausibility.py) let a simpleType
                # section's own heading+doc silently fall through into the
                # TRAILING_DOC branch below and get appended onto the *prior*
                # heading's documentation instead of starting fresh, corrupting
                # names like "Ergebnis" and "Zugang" with several unrelated
                # simpleType sections' worth of concatenated text. A simpleType
                # section never has its own Attributes table in this PDF's own
                # format, so no ATTRIBUTES-state handling is needed for it --
                # it only ever needs its own trailing documentation, same as
                # an element/complexType section without an Attributes table.
                if (
                    texts[0] in ("element", "complexType", "simpleType")
                    and line[0]["x0"] < _MARGIN_X
                ):
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
                if texts[0] == "Name":
                    # Reconstruct this candidate header's own column words
                    # before checking them: a real Attributes table header
                    # ("Name Type Use Default Documentation") can have any of
                    # its later column words split across the very next
                    # visual line by this PDF's own rendering (see
                    # _complete_split_header_words); a real Identity-
                    # constraints table header ("Name Refer Selector
                    # Field(s) Documentation" -- confirmed real on pages
                    # 15/163/177/213) never reconstructs into the 5 real
                    # Attributes keywords no matter what follows it, so it's
                    # correctly excluded regardless.
                    columns = [(w["x0"], w["text"]) for w in line]
                    consumed = 0
                    peek = idx + 1
                    if peek < len(tops) and [w["text"] for w in lines[tops[peek]]] == [
                        "Attributes"
                    ]:
                        consumed += 1
                        peek += 1
                    if peek < len(tops):
                        columns, completed = _complete_split_header_words(
                            columns, lines[tops[peek]]
                        )
                        if completed:
                            consumed += 1
                    header_texts = [text for _, text in columns]
                    if (
                        "Type" in header_texts
                        and "Use" in header_texts
                        and "Documentation" in header_texts
                    ):
                        flush_row()
                        name_x = columns[0][0]
                        doc_x = next(x0 for x0, text in columns if text == "Documentation")
                        state = "ATTRIBUTES"
                        idx += 1 + consumed
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
                    # Real artifact, confirmed on pages 173/226/243 (real
                    # attribute "HinterlegungsscheineGesamtzahl"): a row's own
                    # Name (and Type) column value can itself be split across
                    # two lines, same species of bug as the header-word splits
                    # above -- "HinterlegungsscheineGesamtz" + "ahl". A
                    # lowercase-starting fragment landing in the Name column
                    # before any documentation has started for the row
                    # currently being built can only be this artifact: every
                    # real name in this corpus starts uppercase except the one
                    # confirmed exception, "eMail" -- which never triggers this,
                    # since at each of its 7 real occurrences the preceding
                    # row's own documentation has already started (row_doc_parts
                    # is never still empty by the time "eMail" appears).
                    is_split_name_continuation = (
                        name_word is not None
                        and current_row_name is not None
                        and not row_doc_parts
                        and name_word["text"][:1].islower()
                    )
                    if is_split_name_continuation:
                        current_row_name += name_word["text"]
                        if doc_text:
                            row_doc_parts.append(doc_text)
                    elif name_word is not None:
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


@dataclass(frozen=True)
class TextOccurrence:
    text: str
    page_number: int
    bbox: tuple[float, float, float, float]


def _bbox_of(words: list[dict]) -> tuple[float, float, float, float]:
    return (
        min(w["x0"] for w in words),
        min(w["top"] for w in words),
        max(w["x1"] for w in words),
        max(w["bottom"] for w in words),
    )


def extract_name_occurrences_with_pages(pdf_path: str) -> dict[str, list[TextOccurrence]]:
    """Same state machine as extract_name_occurrences (kept byte-identical
    on purpose -- see this function's own regression test), but tracking
    the real page number and word bounding boxes behind each occurrence,
    for real inline PDF citations. A citation's bbox can legitimately
    span a wide vertical range when its text was assembled from several
    visually separate lines -- a real characteristic of this PDF's table
    layout, not a bug.
    """
    occurrences: dict[str, list[TextOccurrence]] = {}

    state = "NONE"
    current_heading: str | None = None
    heading_doc_words: list[dict] = []
    heading_page_number: int | None = None
    current_row_name: str | None = None
    row_doc_words: list[dict] = []
    row_page_number: int | None = None
    name_x = doc_x = None

    def flush_heading_doc() -> None:
        nonlocal heading_doc_words
        if current_heading is not None and heading_doc_words:
            name = _heading_trailing_name(current_heading)
            text = " ".join(w["text"] for w in heading_doc_words).strip()
            occurrences.setdefault(name, []).append(
                TextOccurrence(text=text, page_number=heading_page_number, bbox=_bbox_of(heading_doc_words))
            )
        heading_doc_words = []

    def flush_row() -> None:
        nonlocal current_row_name, row_doc_words
        if current_row_name is not None and row_doc_words:
            text = " ".join(w["text"] for w in row_doc_words).strip()
            occurrences.setdefault(current_row_name, []).append(
                TextOccurrence(text=text, page_number=row_page_number, bbox=_bbox_of(row_doc_words))
            )
        current_row_name = None
        row_doc_words = []

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

                if _is_page_footer_line(texts, top):
                    idx += 1
                    continue

                if texts[0] in ("element", "complexType", "simpleType") and line[0]["x0"] < _MARGIN_X:
                    flush_row()
                    flush_heading_doc()
                    heading_texts = list(texts)
                    if idx + 1 < len(tops):
                        next_line = lines[tops[idx + 1]]
                        next_texts = [w["text"] for w in next_line]
                        if next_line[0]["x0"] < _MARGIN_X and next_texts[0] not in _SECTION_KEYWORDS:
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
                if texts[0] == "Name":
                    columns = [(w["x0"], w["text"]) for w in line]
                    consumed = 0
                    peek = idx + 1
                    if peek < len(tops) and [w["text"] for w in lines[tops[peek]]] == ["Attributes"]:
                        consumed += 1
                        peek += 1
                    if peek < len(tops):
                        columns, completed = _complete_split_header_words(columns, lines[tops[peek]])
                        if completed:
                            consumed += 1
                    header_texts = [text for _, text in columns]
                    if "Type" in header_texts and "Use" in header_texts and "Documentation" in header_texts:
                        flush_row()
                        name_x = columns[0][0]
                        doc_x = next(x0 for x0, text in columns if text == "Documentation")
                        state = "ATTRIBUTES"
                        idx += 1 + consumed
                        continue
                if joined in ("Documentation", "Documentatio"):
                    flush_row()
                    state = "TRAILING_DOC"
                    idx += 1
                    continue

                if state == "ATTRIBUTES":
                    name_word = next((w for w in line if abs(w["x0"] - name_x) < _COLUMN_X_TOLERANCE), None)
                    doc_words_here = [w for w in line if w["x0"] >= doc_x - _COLUMN_X_TOLERANCE]
                    is_split_name_continuation = (
                        name_word is not None
                        and current_row_name is not None
                        and not row_doc_words
                        and name_word["text"][:1].islower()
                    )
                    if is_split_name_continuation:
                        current_row_name += name_word["text"]
                        if doc_words_here:
                            row_doc_words.extend(doc_words_here)
                    elif name_word is not None:
                        flush_row()
                        current_row_name = name_word["text"]
                        row_page_number = page.page_number
                        if doc_words_here:
                            row_doc_words.extend(doc_words_here)
                    elif doc_words_here:
                        row_doc_words.extend(doc_words_here)
                elif state == "TRAILING_DOC":
                    if texts != ["n"]:
                        if not heading_doc_words:
                            heading_page_number = page.page_number
                        heading_doc_words.extend(line)
                idx += 1

        flush_row()
        flush_heading_doc()

    return occurrences
