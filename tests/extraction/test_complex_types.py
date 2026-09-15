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
from extraction.uris import child_uri, global_uri

EX = Namespace("https://example.org/test/")
FACHTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Fachtypen_1.02.xsd"
PERSONENTYPEN = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
MELDEART13 = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd"
MELDEART11 = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart11_1.02.xsd"
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


def test_named_complex_type_gets_its_own_name_and_documentation():
    # Fix 3 (final review, Important gap): a complex type's own real
    # xs:documentation was never extracted at all -- only elements/
    # attributes got xsdo:documentation. Also needed: xsdo:name on the
    # type itself, both for its own sake and so annex_pdf's name-based
    # English-documentation matching can reach type-level subjects too.
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonBasisType"]
    uri = EX.PersonBasisType
    graph = Graph()

    extract_complex_type(graph, t, uri)

    assert str(graph.value(uri, XSDO.name)) == "PersonBasisType"
    docs = list(graph.objects(uri, XSDO.documentation))
    assert len(docs) == 1
    assert docs[0].language is None
    assert str(docs[0]) == str(t.annotation.documentation[0].text).strip()


def test_extension_adding_only_attributes_does_not_duplicate_inherited_elements():
    # Regression test for Fix 1 (final whole-branch review, Critical bug):
    # PersonNatDatenType extends PersonBasisType adding ONLY attributes (no
    # own <xs:sequence>). PersonBasisType has one real element particle,
    # Anschrift. xmlschema's own xsd_type.content.iter_model() is confirmed
    # to fall back to returning the BASE type's own particle objects
    # (identity-equal, not just equal) in this situation -- unlike
    # Paymentline45BBasisType/PaymentlineBasisType above, whose base has no
    # element content at all, so this dedup path was never actually
    # exercised by that test. Before the fix, extract_complex_type on
    # PersonNatDatenType incorrectly re-extracted and re-minted Anschrift
    # under PersonNatDatenType's own URI too.
    schema = xmlschema.XMLSchema(PERSONENTYPEN)
    base = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonBasisType"]
    ext = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}PersonNatDatenType"]
    base_uri, ext_uri = EX.PersonBasisType, EX.PersonNatDatenType
    graph = Graph()

    extract_complex_type(graph, base, base_uri)
    extract_complex_type(graph, ext, ext_uri)

    # The base keeps its own real Anschrift particle.
    base_content = graph.value(base_uri, XSDO.contentModel)
    base_particles = list(graph.objects(base_content, XSDO.hasParticle))
    assert len(base_particles) == 1
    anschrift_uri = graph.value(base_particles[0], XSDO["term"])
    assert str(graph.value(anschrift_uri, XSDO.name)) == "Anschrift"

    # The extending type adds no element content of its own -- its content
    # model must be empty, not a duplicate of the base's.
    ext_content = graph.value(ext_uri, XSDO.contentModel)
    ext_particles = list(graph.objects(ext_content, XSDO.hasParticle))
    assert ext_particles == []

    # And Anschrift must never be re-minted/re-extracted under the
    # extending type's own scoped URI.
    duplicate_uri = child_uri(ext_uri, "Anschrift")
    assert (duplicate_uri, RDF.type, XSDO.ElementDeclaration) not in graph


def test_genuinely_empty_extension_does_not_duplicate_the_bases_entire_subtree():
    # Regression test for Fix 1: Meldeart11 is a genuinely EMPTY xs:extension
    # of SelbststaendigeMeldungMitOrdnungsnummerType (no own attributes or
    # elements at all). Before the fix, the base's entire
    # Verwahrkette/Kontopersonen/KontoListe subtree -- including the real
    # identity constraint EindeutigesKonto nested under KontoListe/Konto --
    # got duplicated under Meldeart11's own URI too.
    schema = xmlschema.XMLSchema(MELDEART11)
    t = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa11/1.02}Meldeart11"]
    uri = EX.Meldeart11
    graph = Graph()

    extract_complex_type(graph, t, uri)

    content = graph.value(uri, XSDO.contentModel)
    particles = list(graph.objects(content, XSDO.hasParticle))
    assert particles == []

    for local_name in ("Verwahrkette", "Kontopersonen", "KontoListe"):
        assert (child_uri(uri, local_name), RDF.type, XSDO.ElementDeclaration) not in graph


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
