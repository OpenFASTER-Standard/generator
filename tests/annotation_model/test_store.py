import subprocess

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import RDF, SH

from annotation_model.store import TargetStore, _slugify


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
    assert written_path == (
        tmp_path / "store" / "shapes" / _slugify("TestStandard") / f"{_slugify('TestShape')}.ttl"
    )

    read_back = store.read_shape(standard="TestStandard", shape_name="TestShape")
    from annotation_model.namespaces import GEN

    assert (GEN["TestStandard/TestShape"], RDF.type, SH.NodeShape) in read_back


def test_write_shape_uses_readable_prefixes_not_rdflib_auto_generated_ones(tmp_path):
    # write_shape's own internal `merged = Graph()` starts with zero
    # namespace bindings, and copying triples via `merged.add(triple)`
    # does not copy the caller's own bindings either -- confirmed live
    # that every file this produced used rdflib's auto-generated ns1/ns2
    # instead of sh/gen/prov/oa/rdf, for every write this library has ever
    # made (every existing test only checks round-trip structure via
    # re-parsing, never the literal prefix strings, which is why this
    # went uncaught through this project's own first real committed
    # artifact).
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")

    written_path = tmp_path / "store" / "shapes" / _slugify("TestStandard") / f"{_slugify('TestShape')}.ttl"
    text = written_path.read_text(encoding="utf-8")
    assert "ns1:" not in text
    assert "ns2:" not in text
    assert "@prefix gen:" in text
    assert "@prefix oa:" in text


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
    assert public_files == [f"{_slugify('PublicShape')}.ttl"]
    assert bank_files == [f"{_slugify('BankShape')}.ttl"]
    assert not (tmp_path / "public" / "shapes" / _slugify("BankInternal")).exists()
    assert not (tmp_path / "bank-private" / "shapes" / _slugify("PublicStandard")).exists()


def test_slug_collisions_do_not_overwrite_a_different_standards_shape(tmp_path):
    # C3: "MiKaDiv_FM" and "MiKaDiv-FM" (and "Größe"/"Gr e", "§ X"/"§§ X")
    # all naively slugify to the same string -- confirming near-miss names
    # land in different files, inside the SAME store (not just across
    # separate stores, which the multi-tenancy test above already covers).
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    store.write_shape(_shape_graph(), standard="MiKaDiv_FM", shape_name="Sh")
    store.write_shape(_shape_graph(), standard="MiKaDiv-FM", shape_name="Sh")

    first = store.read_shape(standard="MiKaDiv_FM", shape_name="Sh")
    second = store.read_shape(standard="MiKaDiv-FM", shape_name="Sh")
    assert list(first.objects(None, SH.property)) == list(second.objects(None, SH.property))
    # If they'd collided on disk, one store.read_shape call's file wouldn't
    # exist as a distinct path at all -- assert the paths themselves differ.
    assert _slugify("MiKaDiv_FM") != _slugify("MiKaDiv-FM")


def test_a_name_with_no_ascii_alphanumerics_still_slugifies_to_something_nonempty():
    assert _slugify("§§") != ""
    assert _slugify("ÄÖÜ") != ""


def test_writing_a_second_property_does_not_destroy_the_first(tmp_path):
    # C2: write_shape overwrote the whole file with only the new graph's
    # content -- adding a second property to an already-committed shape
    # silently destroyed the first, with no error and no signal.
    from annotation_model.rdf import annotate_xpath
    from rdflib.namespace import PROV

    store = TargetStore(str(tmp_path / "store"))
    store.open()

    first_graph = Graph()
    annotate_xpath(
        first_graph, standard="TestStandard", shape_name="TestShape", property_name="value",
        xpath="/xs:schema/xs:element", source_uri="file:///a.xsd", content_hash="sha256:" + "a" * 64,
    )
    store.write_shape(first_graph, standard="TestStandard", shape_name="TestShape")

    second_graph = Graph()
    annotate_xpath(
        second_graph, standard="TestStandard", shape_name="TestShape", property_name="other",
        xpath="/xs:schema/xs:element[2]", source_uri="file:///b.xsd", content_hash="sha256:" + "b" * 64,
    )
    store.write_shape(second_graph, standard="TestStandard", shape_name="TestShape")

    read_back = store.read_shape(standard="TestStandard", shape_name="TestShape")
    from annotation_model.namespaces import GEN

    properties = sorted(str(o) for o in read_back.objects(GEN["TestStandard/TestShape"], SH.property))
    assert properties == [
        "https://openfaster.org/ns/generator#TestStandard/TestShape/other",
        "https://openfaster.org/ns/generator#TestStandard/TestShape/value",
    ]


def test_rewriting_an_updated_property_replaces_it_on_disk_not_just_in_memory(tmp_path):
    # C2 + I4 combined at the persistence layer: correcting an already-
    # committed property's hash/selector must not leave the stale version
    # sitting in the file alongside the new one.
    from annotation_model.rdf import annotate_xpath
    from annotation_model.namespaces import GEN

    store = TargetStore(str(tmp_path / "store"))
    store.open()

    g1 = Graph()
    annotate_xpath(
        g1, standard="TestStandard", shape_name="TestShape", property_name="value",
        xpath="/xs:schema/xs:element[1]", source_uri="file:///a.xsd", content_hash="sha256:" + "1" * 64,
    )
    store.write_shape(g1, standard="TestStandard", shape_name="TestShape")

    g2 = Graph()
    annotate_xpath(
        g2, standard="TestStandard", shape_name="TestShape", property_name="value",
        xpath="/xs:schema/xs:element[2]", source_uri="file:///b.xsd", content_hash="sha256:" + "2" * 64,
    )
    store.write_shape(g2, standard="TestStandard", shape_name="TestShape")

    read_back = store.read_shape(standard="TestStandard", shape_name="TestShape")
    property_shape_iri = GEN["TestStandard/TestShape/value"]
    assert list(read_back.objects(property_shape_iri, GEN.contentHash)) == [Literal("sha256:" + "2" * 64)]


def test_rewriting_an_unchanged_shape_does_not_crash(tmp_path):
    # I7: git commit exits non-zero when there's nothing to commit;
    # write_shape used check=True, turning a normal idempotent re-write
    # into a CalledProcessError.
    store = TargetStore(str(tmp_path / "store"))
    store.open()
    store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")
    store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")  # must not raise


def test_write_shape_never_commits_an_unrelated_staged_file(tmp_path):
    # I6: `git add <file>` + a bare `git commit` commits everything
    # staged, not just the shape file -- a human with unrelated work
    # staged in the same checkout would have it swept into the
    # annotation's commit, corrupting the provenance record.
    store = TargetStore(str(tmp_path / "store"))
    store.open()

    unrelated = tmp_path / "store" / "UNRELATED_WIP.txt"
    unrelated.write_text("someone else's in-progress work")
    subprocess.run(["git", "add", "UNRELATED_WIP.txt"], cwd=tmp_path / "store", check=True, capture_output=True)

    store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")

    committed_files = subprocess.run(
        ["git", "show", "--stat", "--format=", "HEAD"],
        cwd=tmp_path / "store", check=True, capture_output=True, text=True,
    ).stdout
    assert "UNRELATED_WIP.txt" not in committed_files
    # The unrelated file must still be staged, untouched, for its own
    # eventual commit -- not silently dropped either.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path / "store", check=True, capture_output=True, text=True,
    ).stdout
    assert "UNRELATED_WIP.txt" in status


def test_git_failures_raise_with_the_real_reason_not_an_opaque_exit_code(tmp_path):
    from annotation_model.store import TargetStoreError

    store = TargetStore(str(tmp_path / "not-a-repo"))
    (tmp_path / "not-a-repo").mkdir()
    with pytest.raises(TargetStoreError) as exc_info:
        store.write_shape(_shape_graph(), standard="TestStandard", shape_name="TestShape")
    assert "git add" in str(exc_info.value)


def test_open_on_an_existing_regular_file_raises_a_clear_error(tmp_path):
    from annotation_model.store import TargetStoreError

    afile = tmp_path / "afile"
    afile.write_text("not a directory")
    store = TargetStore(str(afile))
    with pytest.raises(TargetStoreError, match="existing file"):
        store.open()
