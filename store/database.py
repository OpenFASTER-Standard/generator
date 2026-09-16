"""Opens the single embedded, persistent, transactional Oxigraph store
this whole platform reads and writes -- one file on disk, analogous to
opening a SQLite database, via the real rdflib.Dataset API (oxrdflib
backs it with a real Oxigraph store; no separate server process).
"""
from __future__ import annotations

import os

from rdflib import Dataset


def open_store(path: str, create: bool = False) -> Dataset:
    # Check if store exists when create=False
    if not create and not os.path.exists(path):
        raise FileNotFoundError(f"Store does not exist at {path} and create=False")

    dataset = Dataset(store="Oxigraph")
    dataset.open(path, create=create)
    return dataset
