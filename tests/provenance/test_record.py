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


def test_attach_provenance_is_an_upsert():
    """Verify that attaching provenance twice replaces the old record (upsert behavior).

    This test catches the bug where multiple attach_provenance calls would leave
    multiple triples on the same quoted triple, causing get_provenance to return
    mismatched data from a cross product of old and new values.
    """
    dataset = _fresh_dataset()
    try:
        # First attach
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Property,
            predicate=EX.value,
            obj=Literal("test"),
            source_uri="citation:first",
            generated_at="2026-09-15T10:00:00Z",
        )

        # Second attach (should replace first)
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Property,
            predicate=EX.value,
            obj=Literal("test"),
            source_uri="citation:second",
            generated_at="2026-09-15T11:00:00Z",
        )

        # Should return the second (most recent) record, not a cross product
        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Property,
            predicate=EX.value,
            obj=Literal("test"),
        )

        assert record is not None
        assert record.source_uri == "citation:second"
        assert record.generated_at == "2026-09-15T11:00:00Z"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_attach_provenance_escapes_special_characters():
    """Verify that source_uri and generated_at with special characters are properly escaped.

    This test catches the bug where source_uri and generated_at were spliced raw into
    SPARQL queries without escaping. Raw string interpolation of quotes or backslashes
    in f-strings would break SPARQL syntax or introduce unintended escapes.
    """
    dataset = _fresh_dataset()
    try:
        # Use special characters that would break raw SPARQL interpolation:
        # - Quotes would terminate a raw Literal string literal
        # - Apostrophes and complex paths test URI escaping
        problematic_source = "urn:source/with'apostrophe&special"
        problematic_timestamp = '2026-09-15T14:00:00Z"with-quote'

        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Escaped,
            predicate=EX.property,
            obj=Literal("value"),
            source_uri=problematic_source,
            generated_at=problematic_timestamp,
        )

        # Should round-trip correctly despite special characters
        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Escaped,
            predicate=EX.property,
            obj=Literal("value"),
        )

        assert record is not None
        assert record.source_uri == problematic_source
        assert record.generated_at == problematic_timestamp
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
