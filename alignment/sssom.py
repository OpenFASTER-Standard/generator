"""Parses real SSSOM (Simple Standard for Sharing Ontology Mappings) TSV
files into RDF triples -- no sssom-py (see this task's own design spec
for why: its pandas/linkml dependency chain is disproportionate to
reading a handful of TSV rows, and its schema validation checks SSSOM's
shape, not whether subject_id/object_id resolve to anything real).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, URIRef


class SssomParseError(ValueError):
    """Raised when a SSSOM TSV file is malformed -- a CURIE whose prefix
    isn't declared in the file's own curie_map header, or a row missing
    a required column. Always names the file and the offending row so a
    curator sees exactly what to fix, never a bare csv/KeyError
    traceback."""


@dataclass(frozen=True)
class Mapping:
    subject_id: str
    subject_label: str
    predicate_id: str
    object_id: str
    object_label: str
    mapping_justification: str
    confidence: float
    author_id: str


def _parse_curie_map(header_lines: list[str]) -> dict[str, str]:
    curie_map: dict[str, str] = {}
    in_curie_map_block = False
    for line in header_lines:
        stripped = line[1:] if line.startswith("#") else line
        if stripped.rstrip("\n") == "curie_map:":
            in_curie_map_block = True
            continue
        if in_curie_map_block and stripped.startswith("  "):
            prefix, _, iri = stripped.strip().partition(":")
            curie_map[prefix.strip()] = iri.strip()
            continue
        in_curie_map_block = False
    return curie_map


def _expand(curie: str, curie_map: dict[str, str], *, path: Path, raw_row: str) -> str:
    prefix, sep, local = curie.partition(":")
    if not sep or prefix not in curie_map:
        raise SssomParseError(
            f"{path}: row {raw_row!r} uses an unrecognized CURIE prefix {curie!r} "
            f"-- not declared in this file's own curie_map header"
        )
    return curie_map[prefix] + local


def load_sssom_mappings(path: Path) -> list[Mapping]:
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    header_lines = [line for line in lines if line.startswith("#")]
    body_lines = [line for line in lines if not line.startswith("#")]
    curie_map = _parse_curie_map(header_lines)

    mappings = []
    reader = csv.DictReader(body_lines, delimiter="\t")
    for row in reader:
        raw_row = "\t".join(row.get(col, "") for col in reader.fieldnames or [])
        try:
            mappings.append(
                Mapping(
                    subject_id=_expand(row["subject_id"], curie_map, path=path, raw_row=raw_row),
                    subject_label=row["subject_label"],
                    predicate_id=_expand(row["predicate_id"], curie_map, path=path, raw_row=raw_row),
                    object_id=_expand(row["object_id"], curie_map, path=path, raw_row=raw_row),
                    object_label=row["object_label"],
                    mapping_justification=_expand(
                        row["mapping_justification"], curie_map, path=path, raw_row=raw_row
                    ),
                    confidence=float(row["confidence"]),
                    author_id=row["author_id"],
                )
            )
        except KeyError as exc:
            raise SssomParseError(
                f"{path}: row {raw_row!r} is missing a required SSSOM column: {exc}"
            ) from exc
    return mappings


def mappings_to_graph(mappings: list[Mapping]) -> Graph:
    graph = Graph()
    for mapping in mappings:
        graph.add((URIRef(mapping.subject_id), URIRef(mapping.predicate_id), URIRef(mapping.object_id)))
    return graph
