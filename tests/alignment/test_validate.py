from pathlib import Path

import pytest
from rdflib import Graph, RDF, URIRef
from rdflib.namespace import OWL, SKOS

from alignment.institutional_ontology import load_institutional_ontology
from alignment.sssom import Mapping
from alignment.validate import UnresolvedObjectError, UnresolvedSubjectError, validate_mappings
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.alignment.fixtures import requires_real_institutional_ontology
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)
VORNAME_IRI = "https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname"
IO_0000001 = "https://purl.openfaster.org/io/IO_0000001"
# Derived from this test file's own location, not cwd -- a cwd-relative
# path broke when pytest was invoked from a directory other than the
# repo root (Important #7).
REAL_MAPPING_FILE = Path(__file__).resolve().parents[2] / "alignments" / "mikadiv-fm-to-institutional-ontology.sssom.tsv"


def _cited_vorname_graph() -> Graph:
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    annotate_xpath(
        graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )
    return graph


def _valid_mapping() -> Mapping:
    return Mapping(
        subject_id=VORNAME_IRI, subject_label="Vorname",
        predicate_id=str(SKOS.exactMatch),
        object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )


@requires_real_corpus
@requires_real_institutional_ontology
def test_a_real_valid_mapping_does_not_raise():
    validate_mappings(
        [_valid_mapping()],
        generator_graph=_cited_vorname_graph(),
        institutional_graph=load_institutional_ontology(),
    )


@requires_real_institutional_ontology
def test_nonexistent_subject_raises_unresolved_subject_error():
    bad_mapping = Mapping(
        subject_id="https://openfaster.org/ns/generator#NoSuchStandard/NoSuchShape/NoSuchField",
        subject_label="Nope", predicate_id=str(SKOS.exactMatch),
        object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(UnresolvedSubjectError):
        validate_mappings(
            [bad_mapping], generator_graph=Graph(), institutional_graph=load_institutional_ontology(),
        )


def _non_empty_but_irrelevant_institutional_graph() -> Graph:
    # A real, populated ontology graph that just doesn't happen to
    # contain the concept under test -- distinct from a genuinely empty
    # Graph(), which now means "caller forgot to load anything"
    # (EmptyInstitutionalGraphError) rather than "this concept is
    # missing" (UnresolvedObjectError).
    graph = Graph()
    graph.add((URIRef("https://purl.openfaster.org/io/IO_0000002"), RDF.type, OWL.Class))
    return graph


@requires_real_corpus
def test_nonexistent_object_raises_unresolved_object_error():
    bad_mapping = Mapping(
        subject_id=VORNAME_IRI, subject_label="Vorname",
        predicate_id=str(SKOS.exactMatch),
        object_id="https://purl.openfaster.org/io/IO_9999999", object_label="Nope",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(UnresolvedObjectError):
        validate_mappings(
            [bad_mapping],
            generator_graph=_cited_vorname_graph(),
            institutional_graph=_non_empty_but_irrelevant_institutional_graph(),
        )


def test_multiple_bad_subjects_are_all_reported_not_just_the_first():
    # Minor #13: a curator fixing a many-row file needs every failure at
    # once, not a fix-one-rerun loop.
    bad_1 = Mapping(
        subject_id="https://openfaster.org/ns/generator#Bad/One", subject_label="Bad1",
        predicate_id=str(SKOS.exactMatch), object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    bad_2 = Mapping(
        subject_id="https://openfaster.org/ns/generator#Bad/Two", subject_label="Bad2",
        predicate_id=str(SKOS.exactMatch), object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(UnresolvedSubjectError) as exc_info:
        validate_mappings([bad_1, bad_2], generator_graph=Graph(), institutional_graph=Graph())
    assert "Bad/One" in str(exc_info.value)
    assert "Bad/Two" in str(exc_info.value)


@requires_real_corpus
@requires_real_institutional_ontology
def test_load_and_validate_mappings_composes_load_then_validate():
    # Important #6: the real end-to-end usage must not skip validation --
    # this is the one function a future task should copy, so it has to
    # be the pipeline the spec actually describes (load -> validate ->
    # graph), not load -> graph with validation forgotten.
    from alignment.validate import load_and_validate_mappings

    mappings = load_and_validate_mappings(
        REAL_MAPPING_FILE, generator_graph=_cited_vorname_graph(), institutional_graph=load_institutional_ontology(),
    )
    assert len(mappings) == 1
    assert mappings[0].subject_id == VORNAME_IRI


def test_empty_institutional_graph_raises_a_distinct_error_from_unresolved_object():
    # Minor #14: an institutional_graph with zero owl:Class/
    # owl:NamedIndividual triples at all looks exactly like "caller
    # forgot to load the real ontology" -- that deserves a distinct,
    # more actionable error than "this one concept wasn't found",
    # which would otherwise tell a caller their mappings are wrong when
    # really they just never loaded anything.
    from alignment.validate import EmptyInstitutionalGraphError

    bad_mapping = Mapping(
        subject_id=VORNAME_IRI, subject_label="Vorname",
        predicate_id=str(SKOS.exactMatch),
        object_id=IO_0000001, object_label="All given names",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95, author_id="test-author",
    )
    with pytest.raises(EmptyInstitutionalGraphError):
        validate_mappings(
            [bad_mapping], generator_graph=_cited_vorname_graph(), institutional_graph=Graph(),
        )
