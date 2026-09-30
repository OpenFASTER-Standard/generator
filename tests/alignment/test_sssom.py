from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SKOS

from alignment.sssom import Mapping, SssomParseError, load_sssom_mappings, mappings_to_graph

# Deliberately made-up prefixes ("madeup"/"concept"), not the real
# gen:/io: this plan's real data (Task 4) uses -- proves
# load_sssom_mappings() expands CURIEs via THIS file's own curie_map,
# not a hardcoded table of known prefixes.
VALID_TSV = """\
#curie_map:
#  madeup: https://example.org/madeup#
#  concept: https://example.org/concepts/
#  skos: http://www.w3.org/2004/02/skos/core#
#  semapv: https://w3id.org/semapv/vocab/
#mapping_set_id: https://openfaster.org/alignments/test-set
#license: https://creativecommons.org/publicdomain/zero/1.0/
subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id
madeup:Test/Shape/Field\tField\tskos:exactMatch\tconcept:0000099\tTest concept\tsemapv:ManualMappingCuration\t0.95\ttest-author
"""


def test_loads_one_real_mapping_with_curie_expansion(tmp_path: Path):
    tsv_path = tmp_path / "test.sssom.tsv"
    tsv_path.write_text(VALID_TSV, encoding="utf-8")

    mappings = load_sssom_mappings(tsv_path)

    assert mappings == [
        Mapping(
            subject_id="https://example.org/madeup#Test/Shape/Field",
            subject_label="Field",
            predicate_id="http://www.w3.org/2004/02/skos/core#exactMatch",
            object_id="https://example.org/concepts/0000099",
            object_label="Test concept",
            mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
            confidence=0.95,
            author_id="test-author",
        )
    ]


def test_missing_column_raises_named_error_identifying_the_file_and_row(tmp_path: Path):
    tsv_path = tmp_path / "bad.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\n"  # missing every other required column
        "gen:X\tskos:exactMatch\tgen:Y\n",
        encoding="utf-8",
    )

    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)

    assert str(tsv_path) in str(exc_info.value)
    assert "gen:X" in str(exc_info.value)


def test_mappings_to_graph_mints_one_real_triple():
    mapping = Mapping(
        subject_id="https://openfaster.org/ns/generator#Test/Shape/Field",
        subject_label="Field",
        predicate_id="http://www.w3.org/2004/02/skos/core#exactMatch",
        object_id="https://purl.openfaster.org/io/IO_0000099",
        object_label="Test concept",
        mapping_justification="https://w3id.org/semapv/vocab/ManualMappingCuration",
        confidence=0.95,
        author_id="test-author",
    )

    graph = mappings_to_graph([mapping])

    assert len(graph) == 1
    assert (
        URIRef("https://openfaster.org/ns/generator#Test/Shape/Field"),
        SKOS.exactMatch,
        URIRef("https://purl.openfaster.org/io/IO_0000099"),
    ) in graph


def test_unparseable_confidence_raises_named_error_with_file_and_line(tmp_path: Path):
    # Important #1: a bare ValueError with no file/row context is exactly
    # the "never a bare csv/KeyError traceback" failure the spec's Error
    # Handling section forbids, just via float() instead of a missing key.
    # skos/semapv are real SSSOM built-ins (see the built-in-prefixes test
    # below) but declaring them here too, explicitly, keeps this test
    # isolated to the confidence-parsing failure specifically -- it must
    # not accidentally pass because of an unrelated undeclared-prefix
    # error instead.
    tsv_path = tmp_path / "bad_confidence.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "#  io: https://purl.openfaster.org/io/IO_\n"
        "#  skos: http://www.w3.org/2004/02/skos/core#\n"
        "#  semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id\n"
        "gen:X\tX\tskos:exactMatch\tio:0000001\tY\tsemapv:ManualMappingCuration\tnot-a-float\tauthor\n",
        encoding="utf-8",
    )
    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)
    assert str(tsv_path) in str(exc_info.value)
    assert "not-a-float" in str(exc_info.value)


def test_short_row_raises_named_error_not_a_bare_type_error(tmp_path: Path):
    # Important #2: csv.DictReader fills a short row's missing columns
    # with None (restval), so row.get(col, "") still returns None and
    # "\t".join(...) dies with a bare TypeError -- never reaching
    # SssomParseError at all.
    tsv_path = tmp_path / "short_row.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id\n"
        "gen:X\tX\tskos:exactMatch\n",  # only 3 of 8 fields
        encoding="utf-8",
    )
    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)
    assert str(tsv_path) in str(exc_info.value)
    assert "gen:X" in str(exc_info.value)


def test_curie_map_entry_without_a_colon_raises_instead_of_minting_an_empty_prefix(tmp_path: Path):
    # Important #3: a typo'd header line ("#  broken" with no ": iri")
    # must not silently register curie_map["broken"] = "" -- that mints
    # relative, invalid IRIs with no warning.
    # skos/semapv declared explicitly (even though they're real SSSOM
    # built-ins, see below) so this test is isolated to the malformed
    # curie_map entry specifically -- it must not accidentally pass
    # because of an unrelated undeclared-prefix error instead.
    tsv_path = tmp_path / "bad_curie_map.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  broken\n#  skos: http://www.w3.org/2004/02/skos/core#\n"
        "#  semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id\n"
        "broken:X\tX\tskos:exactMatch\tbroken:Y\tY\tsemapv:ManualMappingCuration\t0.9\tauthor\n",
        encoding="utf-8",
    )
    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)
    assert "broken" in str(exc_info.value)


def test_sssom_built_in_prefixes_work_without_being_declared(tmp_path: Path):
    # Important #4 (half 1): skos/semapv/owl/rdf/rdfs/sssom are SSSOM's
    # real built-in prefixes (verified against the real sssom-schema
    # package's context.jsonld) -- a real externally-authored file
    # commonly omits them from its own curie_map, relying on the spec's
    # built-ins.
    tsv_path = tmp_path / "builtin_prefixes.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\n"
        "gen:X\tskos:exactMatch\tgen:Y\tsemapv:ManualMappingCuration\n",
        encoding="utf-8",
    )
    mappings = load_sssom_mappings(tsv_path)
    assert mappings[0].predicate_id == "http://www.w3.org/2004/02/skos/core#exactMatch"
    assert mappings[0].mapping_justification == "https://w3id.org/semapv/vocab/ManualMappingCuration"


def test_optional_columns_may_be_omitted(tmp_path: Path):
    # Important #4 (half 2): only subject_id/predicate_id/object_id/
    # mapping_justification are required by the real SSSOM schema;
    # subject_label/object_label/confidence/author_id are optional.
    tsv_path = tmp_path / "minimal.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\n"
        "gen:X\tskos:exactMatch\tgen:Y\tsemapv:ManualMappingCuration\n",
        encoding="utf-8",
    )
    mappings = load_sssom_mappings(tsv_path)
    assert mappings[0].subject_label is None
    assert mappings[0].object_label is None
    assert mappings[0].confidence is None
    assert mappings[0].author_id is None


def test_empty_file_raises_instead_of_silently_returning_no_mappings(tmp_path: Path):
    # Important #5: an empty file, a header-only file, or a file whose
    # column-header row is missing/commented-out must not silently
    # parse to [] -- that failure would surface later, opaquely, at
    # render time as "0 rows", pointing at the wrong place entirely.
    tsv_path = tmp_path / "empty.sssom.tsv"
    tsv_path.write_text("", encoding="utf-8")
    with pytest.raises(SssomParseError):
        load_sssom_mappings(tsv_path)


def test_header_only_file_raises_instead_of_silently_returning_no_mappings(tmp_path: Path):
    tsv_path = tmp_path / "header_only.sssom.tsv"
    tsv_path.write_text("#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n", encoding="utf-8")
    with pytest.raises(SssomParseError):
        load_sssom_mappings(tsv_path)


def test_missing_column_header_row_raises_instead_of_treating_the_first_data_row_as_header(tmp_path: Path):
    tsv_path = tmp_path / "no_column_header.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "gen:X\tX\tskos:exactMatch\tgen:Y\tY\tsemapv:ManualMappingCuration\t0.9\tauthor\n",
        encoding="utf-8",
    )
    with pytest.raises(SssomParseError):
        load_sssom_mappings(tsv_path)


def test_error_messages_include_the_real_file_line_number(tmp_path: Path):
    # Minor #10: a curator fixing a real, many-row file needs the actual
    # line number, not just a reconstructed row with no location.
    tsv_path = tmp_path / "line_number.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\tconfidence\tauthor_id\n"
        "gen:OK\tOK\tskos:exactMatch\tgen:OK2\tOK2\tsemapv:ManualMappingCuration\t0.9\tauthor\n"
        # line 5 (1-indexed: 2 curie_map lines + 1 header + 1 good row + this one): truncated
        "gen:BAD\tBAD\tskos:exactMatch\n",
        encoding="utf-8",
    )
    with pytest.raises(SssomParseError) as exc_info:
        load_sssom_mappings(tsv_path)
    assert ":5" in str(exc_info.value)


def test_extra_real_metadata_columns_beyond_the_eight_core_ones_are_preserved_not_rejected(tmp_path: Path):
    # Minor #11, other half: a real SSSOM file may legitimately have
    # MORE columns than the eight this project reads (e.g. "comment").
    # That must keep working -- only a row/header COUNT MISMATCH within
    # one file is an error, never "this file has extra real columns".
    tsv_path = tmp_path / "extra_column.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tcomment\n"
        "gen:X\tskos:exactMatch\tgen:Y\tsemapv:ManualMappingCuration\ta real extra column\n",
        encoding="utf-8",
    )
    mappings = load_sssom_mappings(tsv_path)
    assert len(mappings) == 1
    assert mappings[0].subject_id == "https://openfaster.org/ns/generator#X"


def test_load_sssom_header_exposes_mapping_set_id_and_license(tmp_path: Path):
    # Minor #12: mapping_set_id/license were parsed out of the header
    # and thrown away -- nothing could ever read them.
    from alignment.sssom import load_sssom_header

    tsv_path = tmp_path / "with_header_metadata.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "#mapping_set_id: https://example.org/my-set\n"
        "#license: https://creativecommons.org/publicdomain/zero/1.0/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\n"
        "gen:X\tskos:exactMatch\tgen:Y\tsemapv:ManualMappingCuration\n",
        encoding="utf-8",
    )
    header = load_sssom_header(tsv_path)
    assert header["mapping_set_id"] == "https://example.org/my-set"
    assert header["license"] == "https://creativecommons.org/publicdomain/zero/1.0/"


def test_load_sssom_mappings_accepts_a_plain_str_path(tmp_path: Path):
    # Minor #17: the annotation said Path but Path(path) already coerces
    # str fine -- widen the annotation to state the real contract.
    tsv_path = tmp_path / "str_path.sssom.tsv"
    tsv_path.write_text(
        "#curie_map:\n#  gen: https://openfaster.org/ns/generator#\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\n"
        "gen:X\tskos:exactMatch\tgen:Y\tsemapv:ManualMappingCuration\n",
        encoding="utf-8",
    )
    mappings = load_sssom_mappings(str(tsv_path))
    assert len(mappings) == 1
