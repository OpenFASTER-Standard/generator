"""Tests for URI minting: real, stable URIs for named/global XSD
components, and collision-free scoped URIs for local/anonymous ones
that have no global identity of their own.
"""
from rdflib import URIRef

from extraction.uris import child_uri, global_uri, type_uri


class _FakeXsdType:
    def __init__(self, name, target_namespace, local_name, is_global):
        self.name = name
        self.target_namespace = target_namespace
        self.local_name = local_name
        self._is_global = is_global

    def is_global(self):
        return self._is_global


def test_global_uri_joins_namespace_and_local_name_with_hash():
    assert global_uri("http://example.org/ns", "Foo") == URIRef(
        "http://example.org/ns#Foo"
    )


def test_child_uri_appends_a_dotted_segment_to_the_parent():
    parent = URIRef("http://example.org/ns#Foo")
    assert child_uri(parent, "Bar") == URIRef("http://example.org/ns#Foo.Bar")


def test_child_uri_can_be_chained_for_deep_nesting():
    root = global_uri("http://example.org/ns", "Meldeart13")
    konto_liste = child_uri(root, "KontoListe")
    konto = child_uri(konto_liste, "Konto")
    attribute = child_uri(konto, "@Kontonummer")
    assert attribute == URIRef(
        "http://example.org/ns#Meldeart13.KontoListe.Konto.@Kontonummer"
    )


def test_type_uri_of_a_named_type_is_its_own_global_uri():
    named = _FakeXsdType(
        name="{http://example.org/ns}GeburtsdatumType",
        target_namespace="http://example.org/ns",
        local_name="GeburtsdatumType",
        is_global=True,
    )
    owner = global_uri("http://example.org/ns", "Geburtsdatum")
    assert type_uri(named, owner) == URIRef(
        "http://example.org/ns#GeburtsdatumType"
    )


def test_type_uri_of_an_anonymous_type_is_scoped_under_its_owner():
    anonymous = _FakeXsdType(
        name=None,
        target_namespace="http://example.org/ns",
        local_name=None,
        is_global=False,
    )
    owner = global_uri("http://example.org/ns", "Name")
    assert type_uri(anonymous, owner) == URIRef("http://example.org/ns#Name.Type")
