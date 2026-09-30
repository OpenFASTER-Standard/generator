from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import PROV, SH

from annotation_model.namespaces import GEN, OA
from annotation_model.rdf import _iri_segment, annotate_xpath

STANDARD_SEG = _iri_segment("MiKaDiv-FM Meldeart23")

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

    node_shape_iri = GEN[f"{STANDARD_SEG}/AOrdNrShape"]
    assert (node_shape_iri, RDF.type, SH.NodeShape) in graph
    assert (node_shape_iri, SH.property, property_shape_iri) in graph
    assert (property_shape_iri, RDF.type, SH.PropertyShape) in graph


def test_property_shape_carries_provenance_and_hash():
    graph = Graph()
    property_shape_iri = _annotate(graph)

    annotation_iri = GEN[f"{STANDARD_SEG}/AOrdNrShape/value/annotation"]
    assert (property_shape_iri, PROV.wasDerivedFrom, annotation_iri) in graph
    assert (property_shape_iri, GEN.contentHash, Literal("sha256:" + "a" * 64)) in graph
    assert (annotation_iri, RDF.type, OA.Annotation) in graph


def test_annotation_target_has_the_source_and_an_xpath_selector():
    graph = Graph()
    _annotate(graph)

    annotation_iri = GEN[f"{STANDARD_SEG}/AOrdNrShape/value/annotation"]
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

    node_shape_iri = GEN[f"{STANDARD_SEG}/AOrdNrShape"]
    assert list(graph.triples((node_shape_iri, RDF.type, SH.NodeShape))) == [
        (node_shape_iri, RDF.type, SH.NodeShape)
    ]
    assert len(list(graph.objects(node_shape_iri, SH.property))) == 2


def test_a_realistically_named_standard_serializes_without_crashing():
    # C1: real standard names contain spaces (and German regulation names
    # contain characters like section signs) -- an un-encoded IRI segment
    # makes rdflib's Turtle serializer raise, even though the in-memory
    # graph builds without error.
    graph = Graph()
    _annotate(graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape")
    graph.serialize(format="turtle")  # must not raise


def test_a_slash_inside_a_name_does_not_collide_with_a_different_split():
    # C1 (related): naive interpolation lets ("A", "B/C", "D") and
    # ("A", "B", "C/D") mint the identical property-shape IRI.
    graph = Graph()
    shape_a = _annotate(graph, standard="A", shape_name="B/C", property_name="D")
    shape_b = _annotate(graph, standard="A", shape_name="B", property_name="C/D")
    assert shape_a != shape_b


def test_reannotating_the_same_property_replaces_it_instead_of_accumulating():
    # I4: correcting a stale hash or a mis-typed XPath on an existing
    # property must not leave both the old and new versions in the
    # graph -- that made check_xpath_drift's choice of which hash/
    # selector to read nondeterministic.
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph, standard="S", shape_name="Sh", property_name="p",
        xpath="/xs:schema/xs:element[1]", source_uri="file:///a.xsd",
        content_hash="sha256:" + "1" * 64,
    )
    annotate_xpath(
        graph, standard="S", shape_name="Sh", property_name="p",
        xpath="/xs:schema/xs:element[2]", source_uri="file:///b.xsd",
        content_hash="sha256:" + "2" * 64,
    )

    hashes = list(graph.objects(property_shape_iri, GEN.contentHash))
    assert hashes == [Literal("sha256:" + "2" * 64)]

    annotation_iri = next(graph.objects(property_shape_iri, PROV.wasDerivedFrom))
    targets = list(graph.objects(annotation_iri, OA.hasTarget))
    assert len(targets) == 1
    assert (targets[0], OA.hasSource, URIRef("file:///b.xsd")) in graph
    selectors = list(graph.objects(targets[0], OA.hasSelector))
    assert len(selectors) == 1
    assert (selectors[0], RDF.value, Literal("/xs:schema/xs:element[2]")) in graph
