"""Resolves a family name to its current real file, using the real
ontologies-repo convention: a plain-text _current pointer naming the
current snapshot version, and a per-snapshot _manifest.json mapping every
family to its real filename (relative to that snapshot's own directory).
No filename parsing anywhere. See
docs/specs/2026-09-23-staleness-sweep-design.md and
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from reference_model.model import ResolutionOutcome, Status


class CorpusIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class FamilyLocation:
    family: str
    version: str
    retrieval_uri: str


def _load_current_manifest(module_root: str) -> tuple[Path, dict[str, str], str] | None:
    module_root_path = Path(module_root)
    current_path = module_root_path / "_current"
    if not current_path.exists():
        return None

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

    return snapshot_dir, manifest, snapshot


def _resolve_family_path(snapshot_dir: Path, snapshot: str, family: str, manifest: dict[str, str]) -> str:
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
    return str(resolved_path)


def resolve_current_location(module_root: str, family: str) -> ResolutionOutcome:
    result = _load_current_manifest(module_root)
    if result is None:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    snapshot_dir, manifest, snapshot = result
    if family not in manifest:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    resolved_path = _resolve_family_path(snapshot_dir, snapshot, family, manifest)
    return ResolutionOutcome(status=Status.RESOLVED, raw_content=resolved_path)


def list_current_locations(module_root: str) -> list[FamilyLocation]:
    result = _load_current_manifest(module_root)
    if result is None:
        return []
    snapshot_dir, manifest, snapshot = result
    return [
        FamilyLocation(
            family=family,
            version=snapshot,
            retrieval_uri=_resolve_family_path(snapshot_dir, snapshot, family, manifest),
        )
        for family in sorted(manifest.keys())
    ]


def list_current_families(module_root: str) -> list[str]:
    # Deliberately does not resolve any family's file path (unlike
    # list_current_locations()) -- a caller that needs to enumerate family
    # names without one broken manifest entry (a missing file, an escaping
    # path) taking down the whole listing should use this instead, then
    # resolve each family individually via resolve_family_location().
    result = _load_current_manifest(module_root)
    if result is None:
        return []
    _snapshot_dir, manifest, _snapshot = result
    return sorted(manifest.keys())


def resolve_family_location(module_root: str, family: str) -> FamilyLocation | None:
    # Resolves exactly one family, so a broken manifest entry for some
    # OTHER family never prevents citing or listing this one -- unlike
    # list_current_locations(), which resolves every family eagerly and
    # therefore fails as a whole if any single entry is broken.
    result = _load_current_manifest(module_root)
    if result is None:
        return None
    snapshot_dir, manifest, snapshot = result
    if family not in manifest:
        return None
    return FamilyLocation(
        family=family,
        version=snapshot,
        retrieval_uri=_resolve_family_path(snapshot_dir, snapshot, family, manifest),
    )
