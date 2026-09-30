"""An explicit, required git-backed target for annotation output --
never a default, so a public regulation and a bank's own private
process are indistinguishable to this code.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from rdflib import RDF, Graph
from rdflib.namespace import SH

from annotation_model.rdf import clear_property_shape


class TargetStoreError(RuntimeError):
    """A git operation against a target store failed -- carries git's own
    stderr, so a caller never sees a bare non-zero exit code with no
    explanation (a missing user.email, a rejecting hook, a path that
    isn't a repo, ...)."""


def _slugify(value: str) -> str:
    # The readable part alone is not injective -- "MiKaDiv_FM"/"MiKaDiv-FM"
    # and "Größe"/"Gr e" collapse to the same string, which would silently
    # overwrite one standard's committed shape with another's. Appending a
    # short hash of the *original* value makes every distinct input map to
    # a distinct slug, and guarantees a non-empty result even when the
    # readable part is empty (e.g. "§§", which has no ASCII alphanumerics).
    base = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}" if base else digest


class TargetStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(["git", *args], cwd=self._path, capture_output=True)
        if result.returncode != 0:
            raise TargetStoreError(
                f"git {' '.join(args)} failed in {self._path}: "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
        return result

    def open(self) -> None:
        if self._path.is_file():
            raise TargetStoreError(f"{self._path} is an existing file, not a directory")
        if (self._path / ".git").is_dir():
            return
        self._path.mkdir(parents=True, exist_ok=True)
        self._run_git("init")

    def _shape_path(self, *, standard: str, shape_name: str) -> Path:
        return self._path / "shapes" / _slugify(standard) / f"{_slugify(shape_name)}.ttl"

    def write_shape(self, graph: Graph, *, standard: str, shape_name: str) -> Path:
        shape_path = self._shape_path(standard=standard, shape_name=shape_name)
        shape_path.parent.mkdir(parents=True, exist_ok=True)

        merged = Graph()
        if shape_path.is_file():
            merged.parse(str(shape_path), format="turtle")

        # Upsert: for every property shape the incoming graph asserts,
        # clear any previous version already on disk before merging in
        # the new one -- otherwise a corrected hash/selector would sit
        # alongside the stale one it was meant to replace.
        for property_shape_iri in graph.subjects(RDF.type, SH.PropertyShape):
            clear_property_shape(merged, property_shape_iri)
        for triple in graph:
            merged.add(triple)

        turtle = merged.serialize(format="turtle")
        shape_path.write_text(turtle, encoding="utf-8")

        relative = str(shape_path.relative_to(self._path))
        self._run_git("add", relative)

        # `git diff --quiet` exits 1 if there IS a difference, 0 if none --
        # skip the commit entirely when nothing changed (re-writing an
        # unchanged shape is a normal, idempotent operation: a drift sweep
        # that re-verifies and re-commits, a retry after a partial
        # failure), rather than letting `git commit` crash on "nothing to
        # commit". `-- relative` also limits both the diff check and the
        # commit to this one path, so unrelated files a caller happens to
        # have staged in the same repo are never swept into this commit.
        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", relative], cwd=self._path
        )
        if diff_check.returncode != 0:
            self._run_git("commit", "-m", f"annotate: {standard}/{shape_name}", "--", relative)
        return shape_path

    def read_shape(self, *, standard: str, shape_name: str) -> Graph:
        shape_path = self._shape_path(standard=standard, shape_name=shape_name)
        if not shape_path.is_file():
            raise FileNotFoundError(f"no shape at {shape_path}")
        graph = Graph()
        graph.parse(str(shape_path), format="turtle")
        return graph
