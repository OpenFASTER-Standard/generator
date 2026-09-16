import shutil

from rdflib import Literal, Namespace

from provenance.record import attach_provenance, get_provenance
from store.database import open_store

STORE_PATH = "/tmp/test_provenance_store_task4"
EX = Namespace("https://example.org/test#")


def _fresh_dataset():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    return open_store(STORE_PATH, create=True)


def test_attach_and_get_provenance_round_trips_via_rdf_star():
    dataset = _fresh_dataset()
    try:
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
            source_uri="citation:xsd/frag-1",
            generated_at="2026-09-15T14:00:00Z",
        )

        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
        )

        assert record is not None
        assert record.source_uri == "citation:xsd/frag-1"
        assert record.generated_at == "2026-09-15T14:00:00Z"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_provenance_returns_none_for_an_untracked_fact():
    dataset = _fresh_dataset()
    try:
        record = get_provenance(
            dataset, graph_uri="urn:test:prov",
            subject=EX.Nope, predicate=EX.documentation, obj=Literal("nothing"),
        )
        assert record is None
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
