import shutil
import urllib.parse

import pytest
from rdflib import BNode, Literal, Namespace

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
        # generated_at is now stored/read as an xsd:dateTime-typed literal
        # (Fix 5) -- confirmed live that Oxigraph canonicalizes the "Z" UTC
        # designator to an explicit "+00:00" offset on round-trip (same
        # instant, different but equivalent lexical form per the XSD
        # dateTime spec), so the read-back string differs from the exact
        # input string.
        assert record.generated_at == "2026-09-15T14:00:00+00:00"
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
        # See the "+00:00" canonicalization note above (Fix 5).
        assert record.generated_at == "2026-09-15T12:00:00+00:00"
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
        # See the "+00:00" canonicalization note in the round-trip test above (Fix 5).
        assert german_record.generated_at == "2026-09-15T10:00:00+00:00"

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
        assert english_record.generated_at == "2026-09-15T11:00:00+00:00"

        # Verify they're different records (not collided)
        assert german_record.source_uri != english_record.source_uri
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_same_fact_in_two_different_graphs_gets_independent_provenance_records():
    """Regression test for Fix 4: _record_uri used to hash only
    (subject, predicate, obj), not the graph_uri -- the same fact in two
    different run graphs collided to the identical record URI. This was
    harmless while get_provenance is graph-scoped (each graph's RDF-star
    link only ever points at its own graph's record), but the two graphs'
    provenance INSERT DATA calls without graph_uri baked into the record
    URI would have shared/overwritten a single record's INSERT DATA
    ordinary triples once directly compared, and any future cross-run
    lineage query would silently conflate the two runs. Confirm the same
    (subject, predicate, obj) fact attached in two different graph_uris
    each gets its own independently-correct provenance.
    """
    dataset = _fresh_dataset()
    try:
        attach_provenance(
            dataset,
            graph_uri="urn:test:graph-a",
            subject=EX.Shared,
            predicate=EX.value,
            obj=Literal("same fact"),
            source_uri="citation:from-graph-a",
            generated_at="2026-09-15T10:00:00Z",
        )
        attach_provenance(
            dataset,
            graph_uri="urn:test:graph-b",
            subject=EX.Shared,
            predicate=EX.value,
            obj=Literal("same fact"),
            source_uri="citation:from-graph-b",
            generated_at="2026-09-15T11:00:00Z",
        )

        record_a = get_provenance(
            dataset, graph_uri="urn:test:graph-a",
            subject=EX.Shared, predicate=EX.value, obj=Literal("same fact"),
        )
        record_b = get_provenance(
            dataset, graph_uri="urn:test:graph-b",
            subject=EX.Shared, predicate=EX.value, obj=Literal("same fact"),
        )

        assert record_a is not None and record_b is not None
        assert record_a.source_uri == "citation:from-graph-a"
        assert record_b.source_uri == "citation:from-graph-b"
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_generated_at_time_is_stored_as_xsd_datetime_literal():
    """Regression test for Fix 5: the spec's own data model specifies
    prov:generatedAtTime "..."^^xsd:dateTime, but the code stored plain
    untyped/string literals."""
    from rdflib.namespace import XSD

    from provenance.vocab import PROV

    dataset = _fresh_dataset()
    try:
        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.Typed,
            predicate=EX.value,
            obj=Literal("typed timestamp"),
            source_uri="citation:typed",
            generated_at="2026-09-15T10:00:00Z",
        )

        results = list(dataset.query(f"""
        PREFIX prov: <{PROV}>
        SELECT ?time WHERE {{
          GRAPH <urn:test:prov> {{
            << <{EX.Typed}> <{EX.value}> "typed timestamp" >> prov:hasProvenanceRecord ?record .
            ?record prov:generatedAtTime ?time .
          }}
        }}
        """))
        assert len(results) == 1
        assert results[0]["time"].datatype == XSD.dateTime
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_attach_provenance_with_a_source_uri_containing_a_space_round_trips():
    """Regression test for Fix 8: a source_uri containing a space or certain
    other characters (realistic for a citation URI built from a real file
    path) used to make URIRef(source_uri).n3() raise rdflib's own bare,
    unfriendly exception. Confirms attach+get round-trips correctly via
    percent-encoding instead of crashing.
    """
    dataset = _fresh_dataset()
    try:
        source_with_space = "file:///work/ontologies/mikadiv-fm/sources/khb/some file with spaces.pdf"

        attach_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.SpacedSource,
            predicate=EX.value,
            obj=Literal("evidenced value"),
            source_uri=source_with_space,
            generated_at="2026-09-15T10:00:00Z",
        )

        record = get_provenance(
            dataset,
            graph_uri="urn:test:prov",
            subject=EX.SpacedSource,
            predicate=EX.value,
            obj=Literal("evidenced value"),
        )

        assert record is not None
        # Stored as the percent-encoded, valid-URI form; decoding it back
        # recovers the original source_uri exactly.
        assert urllib.parse.unquote(record.source_uri) == source_with_space
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_attach_provenance_rejects_a_source_uri_that_is_never_a_valid_uri():
    """percent-encoding with urllib.parse.quote(safe=":/?=&#") escapes away
    every character rdflib's URIRef.n3() considers illegal (space and
    < > " { } | \\ backtick ^), so a merely-messy source_uri string always
    becomes constructible after encoding. What can still fail is quote()
    itself, e.g. given a non-string source_uri -- that underlying error
    must surface as a clear ValueError, not propagate raw.
    """
    dataset = _fresh_dataset()
    try:
        with pytest.raises(ValueError):
            attach_provenance(
                dataset,
                graph_uri="urn:test:prov",
                subject=EX.BadSource,
                predicate=EX.value,
                obj=Literal("x"),
                source_uri=None,  # not a string at all -- quote() raises
                generated_at="2026-09-15T10:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_attach_provenance_rejects_bnode_subject():
    """Regression test for Fix 9: a blank node embedded in a SPARQL text
    pattern (as this module builds its queries) is a non-distinguished
    variable, not a fixed value -- attach_provenance with a BNode subject
    used to silently match/attach against ANY fact instead of erroring.
    """
    dataset = _fresh_dataset()
    try:
        with pytest.raises(TypeError):
            attach_provenance(
                dataset,
                graph_uri="urn:test:prov",
                subject=BNode(),
                predicate=EX.value,
                obj=Literal("x"),
                source_uri="citation:x",
                generated_at="2026-09-15T10:00:00Z",
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_get_provenance_rejects_bnode_subject():
    """Same as above, for the read side: get_provenance with a BNode subject
    used to silently match ANY fact and return arbitrary/wrong provenance."""
    dataset = _fresh_dataset()
    try:
        with pytest.raises(TypeError):
            get_provenance(
                dataset,
                graph_uri="urn:test:prov",
                subject=BNode(),
                predicate=EX.value,
                obj=Literal("x"),
            )
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
