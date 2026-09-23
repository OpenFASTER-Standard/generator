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
    module_root_path = Path(module_root)
    current_path = module_root_path / "_current"
    if not current_path.exists():
        return ResolutionOutcome(status=Status.NOT_FOUND)

    snapshot = current_path.read_text().strip()
    resolved_module_root = module_root_path.resolve()
    snapshot_dir = (module_root_path / snapshot).resolve()
    if not snapshot_dir.is_relative_to(resolved_module_root):
        # _current is the one file this whole convention expects a human to
        # hand-edit on every re-fetch -- exactly the place a copy-paste
        # mistake (or a malicious edit) is most likely, and the manifest's
        # own escape check (below) can never catch it, since containment
        # there is only ever measured relative to whatever snapshot_dir
        # this bad pointer itself chose.
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r}, which escapes module_root {module_root!r}"
        )

    manifest_path = snapshot_dir / "_manifest.json"
    if not manifest_path.exists():
        raise CorpusIntegrityError(
            f"_current names snapshot {snapshot!r} but {manifest_path} does not exist"
        )

    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as exc:
        raise CorpusIntegrityError(f"{manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise CorpusIntegrityError(
            f"{manifest_path} must contain a JSON object, got {type(manifest).__name__}"
        )

    if family not in manifest:
        return ResolutionOutcome(status=Status.NOT_FOUND)

    resolved_path = (snapshot_dir / manifest[family]).resolve()
    if not resolved_path.is_relative_to(snapshot_dir):
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, which escapes the snapshot directory {snapshot_dir}"
        )
    if not resolved_path.is_file():
        raise CorpusIntegrityError(
            f"_manifest.json for snapshot {snapshot!r} names {manifest[family]!r} "
            f"for family {family!r}, but {resolved_path} is not a real file"
        )

    return ResolutionOutcome(status=Status.RESOLVED, raw_content=str(resolved_path))
