import subprocess

import pytest
from rdflib import Graph
from rdflib.namespace import RDF, SH

from annotation_model.store import TargetStore


def test_path_is_required():
    with pytest.raises(TypeError):
        TargetStore()


def test_open_initializes_a_fresh_directory_as_a_git_repo(tmp_path):
    store = TargetStore(str(tmp_path / "fresh"))
    store.open()
    assert (tmp_path / "fresh" / ".git").is_dir()


def test_open_does_not_reinitialize_an_existing_repo(tmp_path):
    repo_path = tmp_path / "existing"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    marker = repo_path / ".git" / "existing-marker"
    marker.write_text("was here")

    store = TargetStore(str(repo_path))
    store.open()
    assert marker.exists()


def _shape_graph(shape_iri_local="TestShape"):
    from annotation_model.rdf import annotate_xpath

    graph = Graph()
    annotate_xpath(
        graph,
        standard="TestStandard",
        shape_name=shape_iri_local,
        property_name="value",
        xpath="/xs:schema/xs:element",
        source_uri="file:///tmp/test.xsd",
        content_hash="sha256:" + "b" * 64,
    )
    return graph


def test_write_then_read_round_trips(tmp_path):
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    written_path = store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")

    assert written_path.exists()
    assert written_path == tmp_path / "store" / "shapes" / "teststandard" / "testshape.ttl"

    read_back = store.read_shape(standard="TestStandard", shape_name="TestShape")
    from annotation_model.namespaces import GEN

    assert (GEN["TestStandard/TestShape"], RDF.type, SH.NodeShape) in read_back


def test_read_missing_shape_raises_file_not_found(tmp_path):
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    with pytest.raises(FileNotFoundError):
        store.read_shape(standard="TestStandard", shape_name="NoSuchShape")


def test_true_multi_tenancy_two_stores_never_cross_contaminate(tmp_path):
    public_store = TargetStore(str(tmp_path / "public"))
    public_store.open()
    public_store.write_shape(_shape_graph(), standard="PublicStandard", shape_name="PublicShape")

    bank_store = TargetStore(str(tmp_path / "bank-private"))
    bank_store.open()
    bank_store.write_shape(_shape_graph(), standard="BankInternal", shape_name="BankShape")

    public_files = sorted(p.name for p in (tmp_path / "public" / "shapes").rglob("*.ttl"))
    bank_files = sorted(p.name for p in (tmp_path / "bank-private" / "shapes").rglob("*.ttl"))
    assert public_files == ["publicshape.ttl"]
    assert bank_files == ["bankshape.ttl"]
    assert not (tmp_path / "public" / "shapes" / "bankinternal").exists()
    assert not (tmp_path / "bank-private" / "shapes" / "publicstandard").exists()
