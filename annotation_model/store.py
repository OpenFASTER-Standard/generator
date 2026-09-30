"""An explicit, required git-backed target for annotation output --
never a default, so a public regulation and a bank's own private
process are indistinguishable to this code.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rdflib import Graph


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug


class TargetStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def open(self) -> None:
        if (self._path / ".git").is_dir():
            return
        self._path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=self._path, check=True, capture_output=True)

    def _shape_path(self, *, standard: str, shape_name: str) -> Path:
        return self._path / "shapes" / _slugify(standard) / f"{_slugify(shape_name)}.ttl"

    def write_shape(self, graph: Graph, *, standard: str, shape_name: str) -> Path:
        shape_path = self._shape_path(standard=standard, shape_name=shape_name)
        shape_path.parent.mkdir(parents=True, exist_ok=True)
        turtle = graph.serialize(format="turtle")
        shape_path.write_text(turtle, encoding="utf-8")

        relative = shape_path.relative_to(self._path)
        subprocess.run(["git", "add", str(relative)], cwd=self._path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"annotate: {standard}/{shape_name}"],
            cwd=self._path,
            check=True,
            capture_output=True,
        )
        return shape_path

    def read_shape(self, *, standard: str, shape_name: str) -> Graph:
        shape_path = self._shape_path(standard=standard, shape_name=shape_name)
        if not shape_path.is_file():
            raise FileNotFoundError(f"no shape at {shape_path}")
        graph = Graph()
        graph.parse(str(shape_path), format="turtle")
        return graph
