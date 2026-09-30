from pathlib import Path

from rdflib import Graph

from alignment.institutional_ontology import load_institutional_ontology
from alignment.sssom import load_sssom_mappings
from alignment.validate import validate_mappings
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.alignment.fixtures import requires_real_institutional_ontology
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_MAPPING_FILE = Path("alignments/mikadiv-fm-to-institutional-ontology.sssom.tsv")
REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)


def test_the_real_committed_file_loads_to_exactly_one_mapping():
    mappings = load_sssom_mappings(REAL_MAPPING_FILE)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.subject_id == (
        "https://openfaster.org/ns/generator#MiKaDiv-FM%20Personentypen/PersonentypenFields/Vorname"
    )
    assert mapping.object_id == "https://purl.openfaster.org/io/IO_0000001"
    assert mapping.predicate_id == "http://www.w3.org/2004/02/skos/core#exactMatch"
    assert mapping.confidence == 0.95


@requires_real_corpus
@requires_real_institutional_ontology
def test_the_real_committed_mapping_validates_against_real_graphs():
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    generator_graph = Graph()
    annotate_xpath(
        generator_graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )

    mappings = load_sssom_mappings(REAL_MAPPING_FILE)

    validate_mappings(
        mappings, generator_graph=generator_graph, institutional_graph=load_institutional_ontology(),
    )
