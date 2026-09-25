"""Reads and writes the references catalog: a page (fact_key) has an
ordered history of immutable revisions. See
docs/specs/2026-09-25-catalog-revision-history-design.md.
"""
from __future__ import annotations

import dataclasses
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from reference_model.model import Reference
from reference_model.serialize import to_json_dict


class CatalogLoadError(Exception):
    pass


@dataclass(frozen=True)
class Revision:
    revision_id: str
    reference: dict
    author: str
    comment: str
    is_correction: bool
    created_at: str


@dataclass(frozen=True)
class PageSummary:
    revision_count: int
    current: Revision


def _revision_from_dict(data: dict) -> Revision:
    try:
        return Revision(
            revision_id=data["revision_id"],
            reference=data["reference"],
            author=data["author"],
            comment=data["comment"],
            is_correction=data["is_correction"],
            created_at=data["created_at"],
        )
    except KeyError as e:
        raise CatalogLoadError(f"revision is missing field {e}") from e


def load_catalog(catalog_path: str | Path) -> dict:
    path = Path(catalog_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CatalogLoadError(f"{path}: not valid JSON") from e
    if not isinstance(raw, dict):
        raise CatalogLoadError(f"{path}: expected a JSON object")
    for fact_key, value in raw.items():
        if not isinstance(value, list):
            raise CatalogLoadError(
                f"{path}: {fact_key!r} is not a revision list "
                "(pre-revision-history catalog format?)"
            )
    return raw


def add_revision(
    catalog_path: str | Path,
    fact_key: str,
    reference: Reference,
    author: str,
    comment: str,
    is_correction: bool,
) -> Revision:
    path = Path(catalog_path)
    catalog = load_catalog(path)
    page = catalog.setdefault(fact_key, [])
    revision = Revision(
        revision_id=str(uuid.uuid4()),
        reference=to_json_dict(reference),
        author=author,
        comment=comment,
        is_correction=is_correction,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    page.append(dataclasses.asdict(revision))

    # Write to a sibling temp file, then rename over the target -- os.replace()
    # is atomic on POSIX, so a process killed mid-write leaves the original
    # file untouched rather than truncated or partially written. If the write
    # or rename itself fails, remove the temp file rather than leaving an
    # orphan behind in a directory (e.g. the real, git-tracked ontologies
    # checkout) that's supposed to stay clean.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return revision


def get_current_revision(catalog_path: str | Path, fact_key: str) -> Revision | None:
    page = load_catalog(catalog_path).get(fact_key)
    if not page:
        return None
    return _revision_from_dict(page[-1])


def get_history(catalog_path: str | Path, fact_key: str) -> list[Revision]:
    page = load_catalog(catalog_path).get(fact_key, [])
    return [_revision_from_dict(r) for r in page]


def list_pages(catalog_path: str | Path) -> dict[str, PageSummary]:
    catalog = load_catalog(catalog_path)
    return {
        fact_key: PageSummary(revision_count=len(revisions), current=_revision_from_dict(revisions[-1]))
        for fact_key, revisions in catalog.items()
        if revisions
    }
