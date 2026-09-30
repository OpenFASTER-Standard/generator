"""Read-only access to the real, separately-governed institutional-ontology
repo (https://github.com/OpenFASTER-Standard/institutional-ontology),
checked out alongside this one. See this task's own design spec for why
generator depends on that repo's real concepts rather than inventing a
parallel vocabulary.
"""
from __future__ import annotations

import os
from pathlib import Path

from rdflib import Graph

DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH = "/work/institutional-ontology/institutional-ontology.owl"


def institutional_ontology_path() -> Path:
    # Read at call time, not import time -- matching webapp/app.py's
    # _corpus_root()/_catalog_path() convention exactly, so tests can
    # override it via INSTITUTIONAL_ONTOLOGY_PATH without a fresh
    # process per test.
    return Path(os.environ.get("INSTITUTIONAL_ONTOLOGY_PATH", DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH))


def load_institutional_ontology(path: Path | None = None) -> Graph:
    graph = Graph()
    graph.parse(path or institutional_ontology_path(), format="xml")
    return graph
