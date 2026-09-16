import shutil

import pytest
from rdflib import Literal, URIRef

from store.database import open_store

STORE_PATH = "/tmp/test_provenance_store_task1"


def _fresh_path():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return STORE_PATH


def test_open_store_creates_a_new_store_and_persists_data_across_reopen():
    path = _fresh_path()
    try:
        dataset = open_store(path, create=True)
        graph = dataset.graph(URIRef("urn:test:g1"))
        graph.add((URIRef("urn:test:s"), URIRef("urn:test:p"), Literal("hello")))
        dataset.close()

        reopened = open_store(path, create=False)
        reopened_graph = reopened.graph(URIRef("urn:test:g1"))
        triples = list(reopened_graph.triples((None, None, None)))
        assert len(triples) == 1
        assert str(triples[0][2]) == "hello"
        reopened.close()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_open_store_without_create_on_a_missing_path_raises():
    path = _fresh_path()
    import pytest

    with pytest.raises(Exception):
        open_store(path, create=False)


def test_open_store_read_only_can_read_data_written_by_a_prior_writer():
    """Regression test for Fix 7: a second process (e.g. a live web server)
    could never open the same store path concurrently, even just for
    reading. This confirms a genuine read-only open (not a no-op flag) can
    read data a prior read-write open already wrote and closed, using
    get_context (not .graph(), which itself always calls add_graph -- a
    write -- even to fetch an existing graph's handle; see open_store's own
    docstring for that caveat)."""
    path = _fresh_path()
    try:
        writer = open_store(path, create=True)
        graph = writer.graph(URIRef("urn:test:g1"))
        graph.add((URIRef("urn:test:s"), URIRef("urn:test:p"), Literal("hello")))
        writer.close()

        reader = open_store(path, create=False, read_only=True)
        try:
            read_graph = reader.get_context(URIRef("urn:test:g1"))
            triples = list(read_graph.triples((None, None, None)))
            assert len(triples) == 1
            assert str(triples[0][2]) == "hello"
        finally:
            reader.close()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_open_store_read_only_rejects_writes():
    """A read-only store must genuinely refuse writes, not just silently
    accept and drop them -- confirms this isn't a no-op flag."""
    path = _fresh_path()
    try:
        writer = open_store(path, create=True)
        writer.graph(URIRef("urn:test:g1"))
        writer.close()

        reader = open_store(path, create=False, read_only=True)
        try:
            with pytest.raises(Exception):
                reader.update(
                    "INSERT DATA { GRAPH <urn:test:g1> { <urn:test:s2> <urn:test:p2> \"world\" } }"
                )
        finally:
            reader.close()
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_open_store_rejects_read_only_and_create_together():
    path = _fresh_path()
    try:
        with pytest.raises(ValueError):
            open_store(path, create=True, read_only=True)
    finally:
        shutil.rmtree(path, ignore_errors=True)
