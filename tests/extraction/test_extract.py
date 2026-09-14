"""End-to-end tests for extract(xsd_path) against the real, official
MiKaDiv-FM package -- one real construct per spec test case, all
sharing one real parse via a module-scoped fixture.
"""
import pytest
from rdflib import RDF, Namespace

from extraction.extract import extract
from extraction.uris import global_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
ROOT = "ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"

FM = "http://www.itzbund.de/MiKaDiv/FM/1.02"
FMSTD = "http://www.itzbund.de/MiKaDiv/FMStd/1.02"
FMPERS = "http://www.itzbund.de/MiKaDiv/FMPers/1.02"
FMFACH = "http://www.itzbund.de/MiKaDiv/FMFach/1.02"


@pytest.fixture(scope="module")
def graph():
    return extract(ROOT)


def test_abstract_base_and_extending_type_are_both_present(graph):
    base = global_uri(FMSTD, "NachrichtenType")
    ext = global_uri(FM, "DLZertifiziert")
    assert graph.value(base, XSDO.abstract).toPython() is True
    assert graph.value(ext, XSDO.extends) == base


def test_choice_affected_person_type_is_reachable(graph):
    person_type = global_uri(FMPERS, "PersonType")
    assert (person_type, RDF.type, XSDO.ComplexTypeDefinition) in graph
    outer = graph.value(person_type, XSDO.contentModel)
    particles = list(graph.objects(outer, XSDO.hasParticle))
    nested = graph.value(particles[0], XSDO["term"])
    assert (nested, RDF.type, XSDO.Choice) in graph


def test_union_type_is_reachable_with_all_three_members(graph):
    geburtsdatum = global_uri(FMSTD, "GeburtsdatumType")
    members = {str(m).rsplit("#", 1)[-1] for m in graph.objects(geburtsdatum, XSDO.hasUnionMember)}
    assert members == {"Datum0Type", "Datum1880Type", "Datum0000Type"}


def test_real_facet_set_is_reachable():
    schema_graph = extract(ROOT)
    wid_type = global_uri(FMSTD, "WIDType")
    assert int(schema_graph.value(wid_type, XSDO.length)) == 16
    patterns = {str(p) for p in schema_graph.objects(wid_type, XSDO.pattern)}
    assert patterns == {"DE[0-9]{14}"}


def test_composite_identity_constraint_is_reachable(graph):
    verwahrkette_type = global_uri(FMFACH, "VerwahrketteType")
    assert list(graph.objects(verwahrkette_type, XSDO.hasIdentityConstraint))


def test_required_and_optional_attribute_uses_are_both_present(graph):
    ext = global_uri(FMFACH, "Paymentline45BBasisType")
    required_names, optional_names = set(), set()
    for use in graph.objects(ext, XSDO.hasAttributeUse):
        term = graph.value(use, XSDO["term"])
        name = str(graph.value(term, XSDO.name))
        if graph.value(use, XSDO.required).toPython():
            required_names.add(name)
        else:
            optional_names.add(name)
    assert "COAF" in required_names
    assert "ArtDesWertpapieres" in optional_names


def test_default_and_fixed_values_are_reachable(graph):
    position = global_uri(FMFACH, "AuszahlendeStellePositionType.@Position")
    # Position is a local attribute of an anonymous type in this corpus;
    # locate it via the real declaring type's own attribute use instead.
    verwahrkette_type = global_uri(FMFACH, "VerwahrketteType")
    flag_uses = [
        u for u in graph.objects(verwahrkette_type, XSDO.hasAttributeUse)
        if str(graph.value(graph.value(u, XSDO["term"]), XSDO.name))
        == "AuszahlStelleIstDepotfuehrStelle"
    ]
    assert len(flag_uses) == 1
    flag_attr = graph.value(flag_uses[0], XSDO["term"])
    assert str(graph.value(flag_attr, XSDO.defaultValue)) == "false"


def test_untagged_german_documentation_is_reachable(graph):
    root_uri = global_uri(FM, "MiKaDivFMRoot")
    docs = list(graph.objects(root_uri, XSDO.documentation))
    assert len(docs) == 1
    assert docs[0].language is None
    assert str(docs[0]) == "Root-Element für die Nutzdaten."
