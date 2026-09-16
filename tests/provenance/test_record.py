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
    """Verify that attaching provenance multiple times replaces the old record (upsert behavior).

    This test catches the bug where multiple attach_provenance calls would leave
    multiple triples on the same quoted triple, causing get_provenance to return
    mismatched data from a cross product of old and new values.

    Testing with 3 sequential attaches ensures the upsert is not just accidentally
    order-dependent and verifies that only the latest provenance is returned.
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

        # Third attach (should replace second)
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Property,
            predicate=EX.value,
            obj=Literal("test"),
            source_uri="citation:third",
            generated_at="2026-09-15T12:00:00Z",
        )

        # Should return the third (most recent) record, not a cross product
        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Property,
            predicate=EX.value,
            obj=Literal("test"),
        )

        assert record is not None
        assert record.source_uri == "citation:third"
        assert record.generated_at == "2026-09-15T12:00:00Z"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_attach_provenance_escapes_special_characters():
    """Verify that source_uri and generated_at with special characters are properly escaped.

    This test catches the bug where source_uri and generated_at were spliced raw into
    SPARQL queries without escaping. A bare `"{generated_at}"` f-string interpolation would
    be broken by any `"` character in the generated_at string (terminating the string
    literal prematurely and breaking SPARQL syntax).
    """
    dataset = _fresh_dataset()
    try:
        # Use special characters that would break raw SPARQL string interpolation:
        # - `"` in generated_at would close the "..." string literal prematurely
        # - These need proper escaping via URIRef().n3() and Literal().n3()
        problematic_source = "urn:source/some-value?param=x&other=y"
        problematic_timestamp = '2026-09-15T14:00:00Z"with"quotes'

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


def test_attach_provenance_distinguishes_language_variants():
    """Verify that provenance for the same text in different languages is kept separate.

    This is a regression test for the bug where _record_uri used str() instead of .n3(),
    which caused Literal("text", lang="en") and Literal("text", lang="de") to collide
    to the same record URI (since str() drops language tags), silently overwriting one
    language's provenance with the other's.

    The real-world scenario: attaching provenance to documentation that exists in
    multiple languages on the same (subject, predicate) — e.g., German and English
    versions of a field's documentation text.
    """
    dataset = _fresh_dataset()
    try:
        # Attach provenance to the same subject+predicate with German documentation
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
            source_uri="citation:german/spec",
            generated_at="2026-09-15T10:00:00Z",
        )

        # Attach provenance to the same subject+predicate with English documentation
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Short Business ID.", lang="en"),
            source_uri="citation:english/spec",
            generated_at="2026-09-15T11:00:00Z",
        )

        # Verify German provenance is still there (not overwritten)
        german_record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Kurze Wirtschafts-ID.", lang="de"),
        )
        assert german_record is not None
        assert german_record.source_uri == "citation:german/spec"
        assert german_record.generated_at == "2026-09-15T10:00:00Z"

        # Verify English provenance is there (not lost)
        english_record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.WIdNr,
            predicate=EX.documentation,
            obj=Literal("Short Business ID.", lang="en"),
        )
        assert english_record is not None
        assert english_record.source_uri == "citation:english/spec"
        assert english_record.generated_at == "2026-09-15T11:00:00Z"

        # Verify they're different records (not collided)
        assert german_record.source_uri != english_record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
