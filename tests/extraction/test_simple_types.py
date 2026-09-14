"""Tests for facet and xs:union extraction, against real MiKaDiv-FM
simple types -- the complete closed set of 12 standard facets, not
just the subset this project's own census happened to observe."""
from rdflib import RDF, Graph, Namespace, URIRef
import xmlschema

from extraction.simple_types import XSDO, extract_simple_type

FIXTURE = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Standardtypen_1.02.xsd"
EX = Namespace("https://example.org/test/")


def _schema():
    return xmlschema.XMLSchema(FIXTURE)


def test_enumeration_facet_is_extracted_as_a_literal_value_per_option():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}DepotverhaeltnisEnumType"]
    uri = EX.DepotverhaeltnisEnumType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    values = {
        str(graph.value(v, XSDO.literalValue))
        for v in graph.objects(uri, XSDO.hasEnumerationValue)
    }
    assert values == {"P", "N", "T"}


def test_length_and_pattern_facets_are_extracted_from_wid_type():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}WIDType"]
    uri = EX.WIDType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    assert (uri, RDF.type, XSDO.SimpleTypeDefinition) in graph
    assert int(graph.value(uri, XSDO.length)) == 16
    patterns = {str(p) for p in graph.objects(uri, XSDO.pattern)}
    assert patterns == {"DE[0-9]{14}"}


def test_union_member_types_are_linked_by_their_own_real_uri():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}GeburtsdatumType"]
    uri = EX.GeburtsdatumType
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    members = {str(m) for m in graph.objects(uri, XSDO.hasUnionMember)}
    assert members == {
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum0Type",
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum1880Type",
        "http://www.itzbund.de/MiKaDiv/FMStd/1.02#Datum0000Type",
    }


def test_type_with_no_facets_still_gets_the_definition_triple():
    schema = _schema()
    xsd_type = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMStd/1.02}Datum0Type"]
    uri = EX.Datum0Type
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    assert (uri, RDF.type, XSDO.SimpleTypeDefinition) in graph


def test_anonymous_union_members_get_distinct_uris_per_index():
    schema = _schema()
    # xs:namespaceList is a real built-in XSD type with 2 anonymous union members
    xsd_type = schema.maps.types["{http://www.w3.org/2001/XMLSchema}namespaceList"]
    uri = EX.namespaceList
    graph = Graph()

    extract_simple_type(graph, xsd_type, uri)

    members = list(graph.objects(uri, XSDO.hasUnionMember))
    assert len(members) == 2, f"Expected 2 union members, got {len(members)}"

    # Members should have distinct URIs (one for each index)
    member_uris = {str(m) for m in members}
    assert len(member_uris) == 2, f"Expected 2 distinct URIs but got {member_uris}"

    # Verify expected URIs: Member0 and Member1
    expected_uris = {
        "https://example.org/test/namespaceList.Member0",
        "https://example.org/test/namespaceList.Member1",
    }
    assert member_uris == expected_uris
