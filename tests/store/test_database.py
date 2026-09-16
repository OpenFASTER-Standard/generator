import shutil

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
