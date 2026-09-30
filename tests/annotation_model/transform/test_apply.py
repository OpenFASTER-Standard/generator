import pytest
from rdflib import Graph

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import TransformationError, apply_transformation
from annotation_model.transform.registry import Transformation, register
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?property ?hash WHERE {
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
SELECT ?property ?hash ?annotation ?source WHERE {
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
    register(Transformation(name="fields-1", query=FIELD_QUERY, renderer=lambda rows: rows))
    rows = apply_transformation(_two_field_graph(), "fields-1")
    assert len(rows) == 2
    names = sorted(str(row["property"]).split("/")[-1] for row in rows)
    assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])


@requires_real_corpus
def test_provenance_columns_are_never_stripped():
    register(Transformation(name="fields-with-provenance-1", query=PROVENANCE_QUERY, renderer=lambda rows: rows))
    rows = apply_transformation(_two_field_graph(), "fields-with-provenance-1")
    assert len(rows) == 2
    for row in rows:
        assert str(row["source"]) == f"file://{REAL_XSD}"
        assert "/annotation" in str(row["annotation"])


def test_invalid_sparql_raises_transformation_error_naming_the_transformation():
    register(Transformation(name="broken-query-1", query="SELECT ?x WHERE not valid sparql", renderer=lambda rows: rows))
    with pytest.raises(TransformationError, match="broken-query-1"):
        apply_transformation(Graph(), "broken-query-1")


def test_fewer_than_min_rows_raises_by_default():
    register(Transformation(
        name="empty-by-default-1",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
    ))
    with pytest.raises(TransformationError, match="returned 0 row"):
        apply_transformation(Graph(), "empty-by-default-1")


def test_fewer_than_min_rows_does_not_raise_when_min_rows_is_zero():
    register(Transformation(
        name="empty-allowed-1",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
        min_rows=0,
    ))
    assert apply_transformation(Graph(), "empty-allowed-1") == []


def test_renderer_failure_raises_transformation_error_naming_the_renderer_stage():
    def _broken_renderer(rows):
        raise ValueError("boom")

    register(Transformation(
        name="broken-renderer-1",
        query="SELECT ?x WHERE { BIND(1 AS ?x) }",
        renderer=_broken_renderer,
    ))
    with pytest.raises(TransformationError, match="broken-renderer-1"):
        apply_transformation(Graph(), "broken-renderer-1")


def test_a_min_rows_violation_and_a_renderer_failure_have_distinguishable_messages():
    register(Transformation(
        name="empty-by-default-2",
        query="SELECT ?x WHERE { ?x <http://example.org/nosuchpredicate> ?y }",
        renderer=lambda rows: rows,
    ))

    def _broken_renderer(rows):
        raise ValueError("boom")

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
