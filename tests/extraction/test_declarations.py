"""Tests for ElementDeclaration/AttributeDeclaration extraction:
name/type/default/fixed/documentation, against real MiKaDiv-FM
declarations covering both real documentation forms (FM's own
untagged German, and the tagged form used elsewhere in this project).
"""
import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.declarations import XSDO, extract_attribute_declaration, extract_element_declaration
from extraction.uris import child_uri, global_uri

EX = Namespace("https://example.org/test/")
FACHTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd"


def test_attribute_with_fixed_value_and_named_type():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}AuszahlendeStellePositionType"]
    attr = t.attributes["Position"]
    uri = EX.Position
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    assert (uri, RDF.type, XSDO.AttributeDeclaration) in graph
    assert str(graph.value(uri, XSDO.name)) == "Position"
    assert str(graph.value(uri, XSDO.fixedValue)) == "1"
    assert graph.value(uri, XSDO.defaultValue) is None


def test_attribute_with_default_value():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}VerwahrketteType"]
    attr = t.attributes["AuszahlStelleIstDepotfuehrStelle"]
    uri = EX.Flag
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    assert str(graph.value(uri, XSDO.defaultValue)) == "false"


def test_attribute_with_anonymous_simple_type_extracts_its_facets():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonNatDatenType"]
    attr = t.attributes["Name"]
    uri = EX.NameAttr
    graph = Graph()

    extract_attribute_declaration(graph, attr, uri)

    type_uri_value = graph.value(uri, XSDO.type)
    assert type_uri_value == child_uri(EX.NameAttr, "Type")
    assert (type_uri_value, RDF.type, XSDO.SimpleTypeDefinition) in graph
    assert int(graph.value(type_uri_value, XSDO.minLength)) == 1


def test_element_with_default_type_reference_and_no_anonymous_complex_type():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FM/1.02}DLZertifiziert"]
    element = next(p for p in t.content.iter_model() if p.local_name == "ZertifizierteStelle")
    uri = EX.ZertifizierteStelle
    graph = Graph()

    extract_element_declaration(graph, element, uri)

    assert (uri, RDF.type, XSDO.ElementDeclaration) in graph
    assert str(graph.value(uri, XSDO.name)) == "ZertifizierteStelle"
    expected_type = global_uri(
        "http://www.itzbund.de/MiKaDiv/FMPers/1.02", "ZertifizierteStelleType"
    )
    assert graph.value(uri, XSDO.type) == expected_type
    docs = list(graph.objects(uri, XSDO.documentation))
    assert len(docs) == 1
    assert docs[0].language is None
    assert str(docs[0]) == "Das zertifizierte Institut."


def test_element_with_anonymous_complex_type_raises_without_a_callback():
    schema = xmlschema.XMLSchema("ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd")
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    konto_liste = next(p for p in t.content.iter_model() if p.local_name == "KontoListe")
    graph = Graph()

    with pytest.raises(NotImplementedError):
        extract_element_declaration(graph, konto_liste, EX.KontoListe)
