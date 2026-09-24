"""Reads and writes the references catalog file. See
docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class DuplicateFactKeyError(Exception):
    pass


def load_catalog(catalog_path: str) -> dict:
    return json.loads(Path(catalog_path).read_text(encoding="utf-8"))


def save_reference(catalog_path: str, fact_key: str, reference: Reference) -> None:
    catalog = load_catalog(catalog_path)
    if fact_key in catalog:
        raise DuplicateFactKeyError(f"{fact_key!r} already exists in {catalog_path}")
    catalog[fact_key] = to_json_dict(reference)
    Path(catalog_path).write_text(
        json.dumps(catalog, indent=2, sort_keys=True), encoding="utf-8"
    )
