import pytest
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.hints import annotate_display_hint
from annotation_model.namespaces import DASH, GEN
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotated_graph() -> tuple[Graph, URIRef]:
    outcome = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", xpath=AORDNR_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )
    return graph, property_shape_iri


@requires_real_corpus
def test_hint_does_not_destroy_the_citation_it_is_layered_onto():
    graph, property_shape_iri = _annotated_graph()
    original_path = set(graph.objects(property_shape_iri, SH.path))
    original_hash = set(graph.objects(property_shape_iri, GEN.contentHash))
    original_annotation = set(graph.objects(property_shape_iri, PROV.wasDerivedFrom))

    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="AOrdNr",
    )

    assert set(graph.objects(property_shape_iri, SH.path)) == original_path
    assert set(graph.objects(property_shape_iri, GEN.contentHash)) == original_hash
    assert set(graph.objects(property_shape_iri, PROV.wasDerivedFrom)) == original_annotation
    assert (property_shape_iri, RDF.type, SH.PropertyShape) in graph


@requires_real_corpus
def test_hint_adds_only_the_predicates_given():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", order=3,
    )
    assert list(graph.objects(property_shape_iri, SH.order)) == [Literal(3)]
    assert list(graph.objects(property_shape_iri, SH.name)) == []
    assert list(graph.objects(property_shape_iri, DASH.editor)) == []


@requires_real_corpus
def test_calling_annotate_display_hint_twice_replaces_the_label():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="A",
    )
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="B",
    )
    assert list(graph.objects(property_shape_iri, SH.name)) == [Literal("B")]


@requires_real_corpus
def test_all_three_hints_together():
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="AOrdNr", order=1, editor=DASH.TextFieldEditor,
    )
    assert list(graph.objects(property_shape_iri, SH.name)) == [Literal("AOrdNr")]
    assert list(graph.objects(property_shape_iri, SH.order)) == [Literal(1)]
    assert list(graph.objects(property_shape_iri, DASH.editor)) == [DASH.TextFieldEditor]


@requires_real_corpus
def test_hint_on_a_nonexistent_property_shape_raises_instead_of_creating_an_orphan():
    # I3: the spec says this function only adds to an EXISTING property
    # shape and never creates one -- a typo'd (standard, shape_name,
    # property_name) must not silently create a hint-only subject with
    # no sh:path/prov:wasDerivedFrom, which would look like a real
    # citation gained a label but never actually render anywhere.
    from annotation_model.hints import PropertyShapeNotFoundError

    graph, _ = _annotated_graph()
    with pytest.raises(PropertyShapeNotFoundError):
        annotate_display_hint(
            graph, standard="MiKaDiv-FM Meldeart23", shape_name="NoSuchShape",
            property_name="value", label="Oops",
        )


@requires_real_corpus
def test_omitting_a_hint_on_a_later_call_leaves_the_earlier_one_alone():
    # I4: annotate_display_hint's three graph.remove() calls were
    # unconditional, so a later call supplying only `label` silently
    # deleted a previously-set `order`/`editor` it was never asked to
    # touch -- directly contradicting this module's own reason for
    # existing (never destroy hint data the caller didn't ask to change).
    graph, property_shape_iri = _annotated_graph()
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="A", order=1, editor=DASH.TextFieldEditor,
    )
    annotate_display_hint(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape",
        property_name="value", label="B",
    )
    assert list(graph.objects(property_shape_iri, SH.name)) == [Literal("B")]
    assert list(graph.objects(property_shape_iri, SH.order)) == [Literal(1)]
    assert list(graph.objects(property_shape_iri, DASH.editor)) == [DASH.TextFieldEditor]
