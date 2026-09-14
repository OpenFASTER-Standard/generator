"""Tests for xs:key/xs:unique/xs:keyref extraction. xs:unique is
tested against the real Meldeart13.xsd; xs:key/xs:keyref are tested
via a hand-built synthetic fixture since neither is confirmed present
in any real file on disk (see the extraction design spec's corrected
census) -- they stay supported anyway as part of the same closed,
standard identity-constraint kind set as xs:unique.
"""
import os

import pytest
from rdflib import RDF, Graph, Namespace
import xmlschema

from extraction.identity_constraints import XSDO, extract_identity_constraints

EX = Namespace("https://example.org/test/")
FIXTURE = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart13_1.02.xsd"

_SYNTHETIC_KEYREF_XSD = """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:test:keyref" xmlns:tns="urn:test:keyref"
           elementFormDefault="qualified">
  <xs:element name="Root">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Item" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType><xs:attribute name="id" type="xs:string"/></xs:complexType>
        </xs:element>
        <xs:element name="Ref" minOccurs="0" maxOccurs="unbounded">
          <xs:complexType><xs:attribute name="itemId" type="xs:string"/></xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
    <xs:key name="ItemKey">
      <xs:selector xpath="tns:Item"/>
      <xs:field xpath="@id"/>
    </xs:key>
    <xs:keyref name="RefToItem" refer="tns:ItemKey">
      <xs:selector xpath="tns:Ref"/>
      <xs:field xpath="@itemId"/>
    </xs:keyref>
  </xs:element>
</xs:schema>
"""


def test_real_composite_unique_constraint_extracts_all_fields():
    schema = xmlschema.XMLSchema(FIXTURE)
    meldeart13 = schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMMa13/1.02}Meldeart13"]
    konto_liste = next(
        p for p in meldeart13.content.iter_model() if p.local_name == "KontoListe"
    )
    graph = Graph()

    extract_identity_constraints(graph, konto_liste, EX.KontoListeType)

    constraints = list(graph.objects(EX.KontoListeType, XSDO.hasIdentityConstraint))
    assert len(constraints) == 1
    constraint = constraints[0]
    assert (constraint, RDF.type, XSDO.Unique) in graph
    assert str(graph.value(constraint, XSDO.selector)) == "fmma13:Konto"
    fields = {str(f) for f in graph.objects(constraint, XSDO.field)}
    assert fields == {"@ArtDesDepotkontos", "@Kontonummer"}


def test_synthetic_key_and_keyref_extract_kind_and_refer(tmp_path):
    xsd_path = tmp_path / "keyref.xsd"
    xsd_path.write_text(_SYNTHETIC_KEYREF_XSD)
    schema = xmlschema.XMLSchema(str(xsd_path))
    root = schema.maps.elements["{urn:test:keyref}Root"]
    graph = Graph()

    extract_identity_constraints(graph, root, EX.RootType)

    kinds = {
        str(graph.value(c, RDF.type))
        for c in graph.objects(EX.RootType, XSDO.hasIdentityConstraint)
    }
    assert kinds == {str(XSDO.Key), str(XSDO.KeyRef)}

    keyref = next(
        c
        for c in graph.objects(EX.RootType, XSDO.hasIdentityConstraint)
        if (c, RDF.type, XSDO.KeyRef) in graph
    )
    assert str(graph.value(keyref, XSDO.refer)) == "ItemKey"
