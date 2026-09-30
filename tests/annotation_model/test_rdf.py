from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.namespaces import GEN, OA
from annotation_model.rdf import annotate_xpath

SOURCE_URI = "file:///work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotate(graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape", property_name="value"):
    return annotate_xpath(
        graph,
        standard=standard,
        shape_name=shape_name,
        property_name=property_name,
        xpath=XPATH,
        source_uri=SOURCE_URI,
        content_hash="sha256:" + "a" * 64,
    )


def test_produces_a_valid_shacl_shape():
    import pyshacl

    graph = Graph()
    _annotate(graph)

    conforms, _, results_text = pyshacl.validate(Graph(), shacl_graph=graph, meta_shacl=True)
    assert conforms, results_text


def test_node_shape_and_property_shape_are_linked():
    graph = Graph()
    property_shape_iri = _annotate(graph)

    node_shape_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape"]
    assert (node_shape_iri, RDF.type, SH.NodeShape) in graph
    assert (node_shape_iri, SH.property, property_shape_iri) in graph
    assert (property_shape_iri, RDF.type, SH.PropertyShape) in graph


def test_property_shape_carries_provenance_and_hash():
    graph = Graph()
    property_shape_iri = _annotate(graph)

    annotation_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape/value/annotation"]
    assert (property_shape_iri, PROV.wasDerivedFrom, annotation_iri) in graph
    assert (property_shape_iri, GEN.contentHash, Literal("sha256:" + "a" * 64)) in graph
    assert (annotation_iri, RDF.type, OA.Annotation) in graph


def test_annotation_target_has_the_source_and_an_xpath_selector():
    graph = Graph()
    _annotate(graph)

    annotation_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape/value/annotation"]
    targets = list(graph.objects(annotation_iri, OA.hasTarget))
    assert len(targets) == 1
    target = targets[0]
    assert (target, OA.hasSource, URIRef(SOURCE_URI)) in graph

    selectors = list(graph.objects(target, OA.hasSelector))
    assert len(selectors) == 1
    selector = selectors[0]
    assert (selector, RDF.type, OA.XPathSelector) in graph
    assert (selector, RDF.value, Literal(XPATH)) in graph


def test_two_standards_with_the_same_property_name_do_not_collide():
    graph = Graph()
    shape_a = _annotate(graph, standard="MiKaDiv-FM Meldeart23", property_name="value")
    shape_b = _annotate(graph, standard="KaFE", property_name="value")

    assert shape_a != shape_b
    assert (shape_a, RDF.type, SH.PropertyShape) in graph
    assert (shape_b, RDF.type, SH.PropertyShape) in graph


def test_reannotating_the_same_shape_does_not_duplicate_the_node_shape():
    graph = Graph()
    _annotate(graph, property_name="value")
    _annotate(graph, property_name="other")

    node_shape_iri = GEN["MiKaDiv-FM Meldeart23/AOrdNrShape"]
    assert list(graph.triples((node_shape_iri, RDF.type, SH.NodeShape))) == [
        (node_shape_iri, RDF.type, SH.NodeShape)
    ]
    assert len(list(graph.objects(node_shape_iri, SH.property))) == 2
