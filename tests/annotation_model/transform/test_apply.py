import pytest
from rdflib import Graph

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import TransformationError, apply_transformation
from annotation_model.transform.registry import Transformation, register, unregister
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?shape ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

PROVENANCE_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
SELECT ?shape ?property ?hash ?annotation ?source WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
  ?property prov:wasDerivedFrom ?annotation .
  ?annotation oa:hasTarget ?target .
  ?target oa:hasSource ?source .
}
ORDER BY ?property
"""


def _two_field_graph() -> Graph:
    graph = Graph()
    for name, xpath in [
        ("AOrdNr", "//xs:element[@name='AOrdNr']"),
        ("AbgefKapitalertragsteuer", "//xs:element[@name='AbgefKapitalertragsteuer']"),
    ]:
        outcome = resolve_xpath(REAL_XSD, xpath)
        content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
        annotate_xpath(
            graph, standard="MiKaDiv-FM Meldeart23", shape_name="Meldeart23Fields",
            property_name=name, xpath=xpath, source_uri=f"file://{REAL_XSD}",
            content_hash=content_hash,
        )
    return graph


@requires_real_corpus
def test_returns_real_rows_from_a_real_graph():
    try:
        register(Transformation(name="fields-1", query=FIELD_QUERY, renderer=lambda rows: rows))
        rows = apply_transformation(_two_field_graph(), "fields-1")
        assert len(rows) == 2
        names = sorted(str(row["property"]).split("/")[-1] for row in rows)
        assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])
    finally:
        unregister("fields-1")


@requires_real_corpus
def test_provenance_columns_are_never_stripped():
    try:
        register(Transformation(name="fields-with-provenance-1", query=PROVENANCE_QUERY, renderer=lambda rows: rows))
        rows = apply_transformation(_two_field_graph(), "fields-with-provenance-1")
        assert len(rows) == 2
        for row in rows:
            assert str(row["source"]) == f"file://{REAL_XSD}"
            assert "/annotation" in str(row["annotation"])
    finally:
        unregister("fields-with-provenance-1")


def test_invalid_sparql_raises_transformation_error_naming_the_transformation():
    try:
        register(Transformation(name="broken-query-1", query="SELECT ?x WHERE not valid sparql", renderer=lambda rows: rows))
        with pytest.raises(TransformationError, match="broken-query-1"):
            apply_transformation(Graph(), "broken-query-1")
    finally:
        unregister("broken-query-1")


def test_fewer_than_min_rows_raises_by_default():
    try:
        register(Transformation(
            name="empty-by-default-1",
            query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
            renderer=lambda rows: rows,
        ))
        with pytest.raises(TransformationError, match="returned 0 row"):
            apply_transformation(Graph(), "empty-by-default-1")
    finally:
        unregister("empty-by-default-1")


def test_fewer_than_min_rows_does_not_raise_when_min_rows_is_zero():
    try:
        register(Transformation(
            name="empty-allowed-1",
            query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
            renderer=lambda rows: rows,
            min_rows=0,
        ))
        assert apply_transformation(Graph(), "empty-allowed-1") == []
    finally:
        unregister("empty-allowed-1")


def test_renderer_failure_raises_transformation_error_naming_the_renderer_stage():
    def _broken_renderer(rows):
        raise ValueError("boom")

    try:
        register(Transformation(
            name="broken-renderer-1",
            query="SELECT ?x WHERE { BIND(1 AS ?x) }",
            renderer=_broken_renderer,
        ))
        with pytest.raises(TransformationError, match="broken-renderer-1"):
            apply_transformation(Graph(), "broken-renderer-1")
    finally:
        unregister("broken-renderer-1")


def test_a_min_rows_violation_and_a_renderer_failure_have_distinguishable_messages():
    def _broken_renderer(rows):
        raise ValueError("boom")

    try:
        register(Transformation(
            name="empty-by-default-2",
            query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
            renderer=lambda rows: rows,
        ))
        register(Transformation(name="broken-renderer-2", query="SELECT ?x WHERE { BIND(1 AS ?x) }", renderer=_broken_renderer))

        min_rows_message = ""
        try:
            apply_transformation(Graph(), "empty-by-default-2")
        except TransformationError as exc:
            min_rows_message = str(exc)

        renderer_message = ""
        try:
            apply_transformation(Graph(), "broken-renderer-2")
        except TransformationError as exc:
            renderer_message = str(exc)

        assert min_rows_message != renderer_message
        assert "row" in min_rows_message.lower()
        assert "render" in renderer_message.lower()
    finally:
        unregister("empty-by-default-2")
        unregister("broken-renderer-2")


def test_a_runtime_query_failure_after_parsing_still_raises_transformation_error():
    # I1: rdflib's SPARQL evaluation is lazy -- graph.query() only parses;
    # the query actually runs when the result is iterated. A query that
    # parses fine but fails during evaluation (e.g. an unreachable SERVICE
    # clause) must still be caught, not leak a bare library exception.
    try:
        register(Transformation(
            name="service-failure-1",
            query="SELECT ?x WHERE { SERVICE <http://127.0.0.1:1/sparql> { ?x ?p ?o } }",
            renderer=lambda rows: rows,
        ))
        with pytest.raises(TransformationError, match="service-failure-1"):
            apply_transformation(Graph(), "service-failure-1")
    finally:
        unregister("service-failure-1")


def test_a_non_select_query_raises_a_clear_transformation_error():
    # I2: this layer's queries are always SELECT (see spec) -- an ASK/
    # CONSTRUCT/DESCRIBE query is a predictable mistake (CONSTRUCT
    # especially, since the spec spends a paragraph explaining it belongs
    # to a different, later layer) and must fail clearly, not with a bare
    # AttributeError on a result object that has no .asdict().
    try:
        register(Transformation(name="ask-query-1", query="ASK { ?s ?p ?o }", renderer=lambda rows: rows))
        with pytest.raises(TransformationError, match="SELECT"):
            apply_transformation(Graph(), "ask-query-1")
    finally:
        unregister("ask-query-1")


def test_renderer_failure_message_includes_the_exception_type():
    def _broken_renderer(rows):
        raise KeyError("hash")

    try:
        register(Transformation(name="typed-failure-1", query="SELECT ?x WHERE { BIND(1 AS ?x) }", renderer=_broken_renderer))
        with pytest.raises(TransformationError, match="KeyError"):
            apply_transformation(Graph(), "typed-failure-1")
    finally:
        unregister("typed-failure-1")
