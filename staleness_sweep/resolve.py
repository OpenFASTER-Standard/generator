"""Resolves a family name to its current real file, using the real
ontologies-repo convention: a plain-text _current pointer naming the
current snapshot version, and a per-snapshot _manifest.json mapping every
family to its real filename (relative to that snapshot's own directory).
No filename parsing anywhere. See
docs/specs/2026-09-23-staleness-sweep-design.md.
"""
from __future__ import annotations

import json
from pathlib import Path

from reference_model.model import ResolutionOutcome, Status


class CorpusIntegrityError(Exception):
    pass


def resolve_current_location(module_root: str, family: str) -> ResolutionOutcome:
    current_path = Path(module_root) / "_current"
    if not current_path.exists():
        return ResolutionOutcome(status=Status.NOT_FOUND)

    snapshot = current_path.read_text().strip()
    snapshot_dir = Path(module_root) / snapshot
    manifest_path = snapshot_dir / "_manifest.json"
    if not manifest_path.exists():
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r} but {manifest_path} does not exist"
        )

    manifest = json.loads(manifest_path.read_text())
    if family not in manifest:
        return ResolutionOutcome(status=Status.NOT_FOUND)

    resolved_snapshot_dir = snapshot_dir.resolve()
    resolved_path = (snapshot_dir / manifest[family]).resolve()
    if not resolved_path.is_relative_to(resolved_snapshot_dir):
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, which escapes the snapshot directory {snapshot_dir}"
        )
    if not resolved_path.exists():
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, but {resolved_path} does not exist"
        )

    return ResolutionOutcome(status=Status.RESOLVED, raw_content=str(resolved_path))
