from pathlib import Path

from rdflib import Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from alignment.institutional_ontology import (
    DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH,
    institutional_ontology_path,
    load_institutional_ontology,
)
from tests.alignment.fixtures import requires_real_institutional_ontology

IO_0000001 = URIRef("https://purl.openfaster.org/io/IO_0000001")


def test_default_path_with_no_env_var(monkeypatch):
    monkeypatch.delenv("INSTITUTIONAL_ONTOLOGY_PATH", raising=False)
    assert institutional_ontology_path() == Path(DEFAULT_INSTITUTIONAL_ONTOLOGY_PATH)


def test_env_var_override_is_read_at_call_time_not_import_time(monkeypatch):
    monkeypatch.setenv("INSTITUTIONAL_ONTOLOGY_PATH", "/tmp/first.owl")
    assert institutional_ontology_path() == Path("/tmp/first.owl")

    monkeypatch.setenv("INSTITUTIONAL_ONTOLOGY_PATH", "/tmp/second.owl")
    assert institutional_ontology_path() == Path("/tmp/second.owl")


@requires_real_institutional_ontology
def test_loads_real_ontology_with_the_real_given_name_concept():
    graph = load_institutional_ontology()

    assert len(graph) > 0
    assert (IO_0000001, RDF.type, OWL.Class) in graph
    labels = list(graph.objects(IO_0000001, RDFS.label))
    assert labels == [Literal("All given names", lang="en")]
