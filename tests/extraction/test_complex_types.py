"""Tests for complex-type extraction: extends/abstract, the recursive
Sequence/Choice content model (including nested groups and anonymous
complex types), and attribute uses -- against real MiKaDiv-FM types.
"""
import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.complex_types import (
    XSDO,
    extract_complex_type,
    extract_element_declaration_with_recursion,
)
from extraction.uris import global_uri

EX = Namespace("https://example.org/test/")
FACHTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd"
PERSONENTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
MELDEART13 = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd"
ROOT = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"


def test_plain_sequence_type_with_no_extension():
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonBasisType"]
    uri = EX.PersonBasisType
    graph = Graph()

    extract_complex_type(graph, t, uri)

    assert (uri, RDF.type, XSDO.ComplexTypeDefinition) in graph
    assert graph.value(uri, XSDO.abstract).toPython() is True
    assert graph.value(uri, XSDO.extends) is None
    content = graph.value(uri, XSDO.contentModel)
    assert (content, RDF.type, XSDO.Sequence) in graph
    particles = list(graph.objects(content, XSDO.hasParticle))
    assert len(particles) == 1


def test_extension_from_abstract_base_captures_only_own_particles():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    base = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}PaymentlineBasisType"]
    ext = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}Paymentline45BBasisType"]
    ext_uri, base_uri = EX.Ext, EX.Base
    graph = Graph()

    extract_complex_type(graph, base, base_uri)
    extract_complex_type(graph, ext, ext_uri)

    assert graph.value(base_uri, XSDO.abstract).toPython() is True
    # Paymentline45BBasisType is itself abstract="true" in the real XSD
    # source (MiKaDiv_FM_Fachtypen_1.02.xsd) -- confirmed directly on the
    # xmlschema object's own .abstract attribute, not just the graph.
    assert graph.value(ext_uri, XSDO.abstract).toPython() is True
    assert ext.abstract is True
    assert graph.value(ext_uri, XSDO.extends) == global_uri(
        "http://www.itzbund.de/MiKaDiv/FMFach/1.02", "PaymentlineBasisType"
    )
    content = graph.value(ext_uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    assert len(particles) == 1  # only AusschuettendeGesellschaft -- not ISIN/Zahlungstag


def test_extension_attribute_uses_exclude_inherited_attributes():
    schema = xmlschema.XMLSchema(FACHTYPEN)
    ext = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMFach/1.02}Paymentline45BBasisType"]
    uri = EX.Ext
    graph = Graph()

    extract_complex_type(graph, ext, uri)

    attribute_uses = list(graph.objects(uri, XSDO.hasAttributeUse))
    names = set()
    for use in attribute_uses:
        term = graph.value(use, XSDO["term"])
        names.add(str(graph.value(term, XSDO.name)))
    assert names == {"ArtDesWertpapieres", "COAF"}  # not ISIN/Zahlungstag (inherited)

    coaf_use = next(
        u for u in attribute_uses
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name)) == "COAF"
    )
    assert graph.value(coaf_use, XSDO.required).toPython() is True
    art_use = next(
        u for u in attribute_uses
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name)) == "ArtDesWertpapieres"
    )
    assert graph.value(art_use, XSDO.required).toPython() is False


def test_choice_nested_inside_sequence_is_extracted_recursively():
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonType"]
    uri = EX.PersonType
    graph = Graph()

    extract_complex_type(graph, t, uri)

    outer = graph.value(uri, XSDO.contentModel)
    assert (outer, RDF.type, XSDO.Sequence) in graph
    outer_particles = list(graph.objects(outer, XSDO.hasParticle))
    assert len(outer_particles) == 1
    nested = graph.value(outer_particles[0], XSDO["term"])
    assert (nested, RDF.type, XSDO.Choice) in graph
    nested_particles = list(graph.objects(nested, XSDO.hasParticle))
    assert len(nested_particles) == 2
    element_names = set()
    for particle in nested_particles:
        element_uri = graph.value(particle, XSDO["term"])
        element_names.add(str(graph.value(element_uri, XSDO.name)))
    assert element_names == {"EinzelPerson", "SonstigeGemeinschaft"}


def test_anonymous_complex_type_recurses_through_nested_levels():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    content = graph.value(uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    konto_liste_uri = next(
        graph.value(p, XSDO["term"])
        for p in particles
        if str(graph.value(graph.value(p, XSDO["term"]), XSDO.name)) == "KontoListe"
    )
    konto_liste_type_uri = graph.value(konto_liste_uri, XSDO.type)
    assert (konto_liste_type_uri, RDF.type, XSDO.ComplexTypeDefinition) in graph

    konto_content = graph.value(konto_liste_type_uri, XSDO.contentModel)
    konto_particle = next(iter(graph.objects(konto_content, XSDO.hasParticle)))
    konto_uri = graph.value(konto_particle, XSDO["term"])
    assert str(graph.value(konto_uri, XSDO.name)) == "Konto"

    konto_type_uri = graph.value(konto_uri, XSDO.type)
    attribute_uses = list(graph.objects(konto_type_uri, XSDO.hasAttributeUse))
    assert len(attribute_uses) == 2


def test_identity_constraint_attaches_to_the_elements_own_named_type():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    verwahrkette_type_uri = global_uri(
        "http://www.itzbund.de/MiKaDiv/FMFach/1.02", "VerwahrketteType"
    )
    constraints = list(graph.objects(verwahrkette_type_uri, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    assert str(graph.value(constraints[0], XSDO.selector)) == (
        "fmfach:Verwahrstelle | fmfach:DepotfuehrendeStelle"
    )
    # and NOT attached to Meldeart13 itself
    assert list(graph.objects(uri, XSDO.hasIdentityConstraint)) == []


def test_identity_constraint_attaches_to_an_anonymous_owning_type():
    schema = xmlschema.XMLSchema(MELDEART13)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    uri = EX.Meldeart13
    graph = Graph()

    extract_complex_type(graph, t, uri)

    content = graph.value(uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    konto_liste_uri = next(
        graph.value(p, XSDO["term"])
        for p in particles
        if str(graph.value(graph.value(p, XSDO["term"]), XSDO.name)) == "KontoListe"
    )
    konto_liste_type_uri = graph.value(konto_liste_uri, XSDO.type)

    constraints = list(graph.objects(konto_liste_type_uri, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    fields = {str(f) for f in graph.objects(constraints[0], XSDO.field)}
    assert fields == {"@ArtDesDepotkontos", "@Kontonummer"}


def test_all_content_model_raises_named_error():
    import tempfile, os
    xsd = """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:test:all" xmlns:tns="urn:test:all"
           elementFormDefault="qualified">
  <xs:complexType name="AllType">
    <xs:all>
      <xs:element name="A" type="xs:string"/>
    </xs:all>
  </xs:complexType>
</xs:schema>
"""
    fd, path = tempfile.mkstemp(suffix=".xsd")
    os.write(fd, xsd.encode())
    os.close(fd)
    schema = xmlschema.XMLSchema(path)
    t = schema.maps.types["{urn:test:all}AllType"]
    graph = Graph()

    with pytest.raises(NotImplementedError):
        extract_complex_type(graph, t, EX.AllType)


def test_element_declaration_with_recursion_extracts_the_root_elements_own_identity_constraints():
    schema = xmlschema.XMLSchema(ROOT)
    root_element = schema.maps.elements["{http://www.itzbund.de/MiKaDiv/FM/1.02}MiKaDivFMRoot"]
    uri = EX.MiKaDivFMRoot
    graph = Graph()

    extract_element_declaration_with_recursion(graph, root_element, uri)

    type_uri_value = graph.value(uri, XSDO.type)
    constraint_names = set()
    for c in graph.objects(type_uri_value, XSDO.hasIdentityConstraint):
        constraint_names.add(str(c).rsplit(".", 1)[-1])
    assert constraint_names == {"UUIDIstEindeutig", "ZulassungsnummerIstEindeutig"}
