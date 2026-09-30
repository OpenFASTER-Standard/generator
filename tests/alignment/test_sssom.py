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
