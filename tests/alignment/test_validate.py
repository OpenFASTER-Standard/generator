import pytest
from rdflib import Graph
from rdflib.namespace import SKOS

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
            [bad_mapping], generator_graph=_cited_vorname_graph(), institutional_graph=Graph(),
        )
