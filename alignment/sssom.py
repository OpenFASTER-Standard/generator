"""Parses real SSSOM (Simple Standard for Sharing Ontology Mappings) TSV
files into RDF triples -- no sssom-py (see this task's own design spec
for why: its pandas/linkml dependency chain is disproportionate to
reading a handful of TSV rows, and its schema validation checks SSSOM's
shape, not whether subject_id/object_id resolve to anything real).

Uses plain str.split("\t") rather than the csv module: this loses
support for a field containing a literal embedded tab (SSSOM
labels/CURIEs/justifications never do), in exchange for genuinely real
per-line error locations and a strict row/header column-count check that
csv.DictReader's restval/restkey behavior would otherwise paper over
silently (a short row gets None-filled, a long row's extra fields are
silently dropped).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, URIRef

# SSSOM's own built-in prefixes -- verified live against the real
# sssom-schema package's context.jsonld (mapping-commons/sssom-schema
# 1.1.0a5), not guessed: a real externally-authored SSSOM file is
# entitled to use these without declaring them in its own curie_map.
# Spread last (wins over anything a file's own curie_map declares),
# matching sssom-py's own real behavior (its `ensure_converter` chains
# a file's prefix map *behind* the built-in one specifically so a file
# can never override what these mean).
_BUILTIN_PREFIXES = {
    "sssom": "https://w3id.org/sssom/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
}

# Per the real SSSOM schema (verified live: only predicate_id and
# mapping_justification carry `required: true`) plus the practical
# minimum for a mapping to mean anything at all -- subject_id/object_id
# have no data without a real value either, even though the schema
# itself doesn't flag them required.
_REQUIRED_COLUMNS = ("subject_id", "predicate_id", "object_id", "mapping_justification")
_OPTIONAL_COLUMNS = ("subject_label", "object_label", "confidence", "author_id")


class SssomParseError(ValueError):
    """Raised when a SSSOM TSV file is malformed -- a CURIE whose prefix
    isn't declared (in the file's own curie_map or SSSOM's real
    built-ins), a row whose column count doesn't match its own header, an
    unparseable confidence value, or a file with no recognizable SSSOM
    column header at all. Always names the file and the real line number
    so a curator sees exactly what to fix, never a bare
    csv/KeyError/ValueError/TypeError traceback."""


@dataclass(frozen=True, kw_only=True)
class Mapping:
    subject_id: str
    predicate_id: str
    object_id: str
    mapping_justification: str
    subject_label: str | None = None
    object_label: str | None = None
    confidence: float | None = None
    author_id: str | None = None


def _parse_curie_map(header_lines: list[str], *, path: Path) -> dict[str, str]:
    curie_map: dict[str, str] = {}
    in_curie_map_block = False
    for line in header_lines:
        stripped = line[1:] if line.startswith("#") else line
        if stripped.rstrip("\n") == "curie_map:":
            in_curie_map_block = True
            continue
        if in_curie_map_block and stripped.startswith("  "):
            prefix, sep, iri = stripped.strip().partition(":")
            if not sep or not iri.strip():
                raise SssomParseError(
                    f"{path}: malformed curie_map entry {stripped.strip()!r} -- "
                    "expected 'prefix: iri'"
                )
            prefix = prefix.strip()
            if prefix in curie_map:
                raise SssomParseError(
                    f"{path}: curie_map declares prefix {prefix!r} more than once"
                )
            curie_map[prefix] = iri.strip()
            continue
        in_curie_map_block = False
    return curie_map


def load_sssom_header(path: Path | str) -> dict[str, str]:
    """Returns the SSSOM header's flat #key: value metadata lines
    (mapping_set_id, license, ...) -- read for provenance, previously
    parsed out and discarded entirely by load_sssom_mappings()."""
    path = Path(path)
    header_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")]
    metadata: dict[str, str] = {}
    in_curie_map_block = False
    for line in header_lines:
        stripped = line[1:]
        if stripped.rstrip("\n") == "curie_map:":
            in_curie_map_block = True
            continue
        if in_curie_map_block and stripped.startswith("  "):
            continue
        in_curie_map_block = False
        key, sep, value = stripped.partition(":")
        if sep:
            metadata[key.strip()] = value.strip()
    return metadata


def _expand(curie: str, curie_map: dict[str, str], *, path: Path, line_num: int, raw_line: str) -> str:
    prefix, sep, local = curie.partition(":")
    if not sep or prefix not in curie_map:
        raise SssomParseError(
            f"{path}:{line_num}: row {raw_line!r} uses an unrecognized CURIE prefix {curie!r} "
            f"-- not declared in this file's own curie_map header, and not one of SSSOM's "
            f"built-in prefixes ({', '.join(sorted(_BUILTIN_PREFIXES))})"
        )
    return curie_map[prefix] + local


def _parse_confidence(raw: str | None, *, path: Path, line_num: int, raw_line: str) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise SssomParseError(
            f"{path}:{line_num}: row {raw_line!r} has an unparseable confidence value {raw!r}: {exc}"
        ) from exc


def load_sssom_mappings(path: Path | str) -> list[Mapping]:
    path = Path(path)
    all_lines = path.read_text(encoding="utf-8").splitlines()
    header_lines = [line for line in all_lines if line.startswith("#")]
    curie_map = _parse_curie_map(header_lines, path=path)
    curie_map.update(_BUILTIN_PREFIXES)

    body = [(line_num, line) for line_num, line in enumerate(all_lines, start=1) if not line.startswith("#")]
    if not body:
        raise SssomParseError(f"{path}: no SSSOM column header row found (file has no non-comment lines)")

    header_line_num, header_line = body[0]
    column_header = header_line.split("\t")
    if "subject_id" not in column_header:
        raise SssomParseError(
            f"{path}:{header_line_num}: no 'subject_id' column in header row {column_header!r} "
            "-- is this really a SSSOM TSV, or is the column header row missing/commented out?"
        )

    mappings = []
    for line_num, raw_line in body[1:]:
        if not raw_line.strip():
            continue
        fields = raw_line.split("\t")
        if len(fields) != len(column_header):
            raise SssomParseError(
                f"{path}:{line_num}: row {raw_line!r} has {len(fields)} column(s), "
                f"expected {len(column_header)} to match the header {column_header!r}"
            )
        row = dict(zip(column_header, fields))

        try:
            required = {col: row[col] for col in _REQUIRED_COLUMNS}
        except KeyError as exc:
            raise SssomParseError(
                f"{path}:{line_num}: row {raw_line!r} is missing a required SSSOM column: {exc}"
            ) from exc

        mappings.append(
            Mapping(
                subject_id=_expand(required["subject_id"], curie_map, path=path, line_num=line_num, raw_line=raw_line),
                predicate_id=_expand(
                    required["predicate_id"], curie_map, path=path, line_num=line_num, raw_line=raw_line
                ),
                object_id=_expand(required["object_id"], curie_map, path=path, line_num=line_num, raw_line=raw_line),
                mapping_justification=_expand(
                    required["mapping_justification"], curie_map, path=path, line_num=line_num, raw_line=raw_line
                ),
                subject_label=row.get("subject_label") or None,
                object_label=row.get("object_label") or None,
                confidence=_parse_confidence(row.get("confidence"), path=path, line_num=line_num, raw_line=raw_line),
                author_id=row.get("author_id") or None,
            )
        )
    return mappings


def mappings_to_graph(mappings: list[Mapping]) -> Graph:
    graph = Graph()
    for mapping in mappings:
        graph.add((URIRef(mapping.subject_id), URIRef(mapping.predicate_id), URIRef(mapping.object_id)))
    return graph
