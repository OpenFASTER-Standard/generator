"""Opens the single embedded, persistent, transactional Oxigraph store
this whole platform reads and writes -- one file on disk, analogous to
opening a SQLite database, via the real rdflib.Dataset API (oxrdflib
backs it with a real Oxigraph store; no separate server process).
"""
from __future__ import annotations

import os

import pyoxigraph
from oxrdflib import OxigraphStore
from rdflib import Dataset


def open_store(path: str, create: bool = False, read_only: bool = False) -> Dataset:
    """Open the embedded Oxigraph store at ``path``.

    ``read_only=True`` opens a genuine read-only instance, backed by
    ``pyoxigraph.Store.read_only`` -- verified live to allow a second
    process to open the same store path concurrently with a writer, and to
    raise ``RuntimeError`` on any attempted write (confirmed:
    "Transaction are only possible on read-write instances"). This goes
    through ``oxrdflib.OxigraphStore(store=...)`` directly rather than
    ``Dataset.open()``, because ``oxrdflib``'s own ``open()`` always
    constructs a read-write ``pyoxigraph.Store(path)`` with no way to pass
    a read-only flag through it.

    Caveat for read-only callers, verified live: ``Dataset.graph(uri)``
    unconditionally calls ``self.store.add_graph(...)`` even just to fetch
    a handle to an existing graph, which is itself a write and raises the
    same ``RuntimeError`` against a read-only store. Read-only callers must
    fetch a graph handle via ``dataset.get_context(uri)`` instead (which
    does not call ``add_graph``), or query via ``dataset.query(...)``
    directly -- both confirmed to work read-only.
    """
    if read_only and create:
        raise ValueError("read_only and create cannot both be True")

    # Check if store exists when create=False
    if not create and not os.path.exists(path):
        raise FileNotFoundError(f"Store does not exist at {path} and create=False")

    if read_only:
        ox_store = pyoxigraph.Store.read_only(path)
        dataset = Dataset(store=OxigraphStore(store=ox_store))
        return dataset

    dataset = Dataset(store="Oxigraph")
    dataset.open(path, create=create)
    return dataset
