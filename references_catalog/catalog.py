"""Reads and writes the references catalog file. See
docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class DuplicateFactKeyError(Exception):
    pass


class CatalogLoadError(Exception):
    pass


def load_catalog(catalog_path: str | Path) -> dict:
    path = Path(catalog_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"{path}: not valid JSON") from e
    if not isinstance(raw, dict):
        raise CatalogLoadError(f"{path}: expected a JSON object")
    return raw


def save_reference(catalog_path: str | Path, fact_key: str, reference: Reference) -> None:
    path = Path(catalog_path)
    catalog = load_catalog(path)
    if fact_key in catalog:
        raise DuplicateFactKeyError(f"{fact_key!r} already exists in {path}")
    catalog[fact_key] = to_json_dict(reference)

    # Write to a sibling temp file, then rename over the target -- os.replace()
    # is atomic on POSIX, so a process killed mid-write leaves the original
    # file untouched rather than truncated or partially written.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
