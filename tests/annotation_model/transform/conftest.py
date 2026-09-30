"""Shared real-corpus fixtures for annotation_model.transform's tests --
previously duplicated verbatim between test_apply.py and
test_renderers.py.
"""
from __future__ import annotations

import pytest
from rdflib import Graph

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import REAL_CORPUS_ROOT

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

# Projects ?shape alongside ?property/?hash -- the only worked example a
# future transformation author has to copy from, so it demonstrates how
# to disambiguate a merged multi-shape graph rather than silently
# duplicating rows for identically-named properties from different
# shapes.
FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?shape ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

PROVENANCE_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX oa: <http://www.w3.org/ns/oa#>
SELECT ?shape ?property ?hash ?annotation ?source WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
  ?property prov:wasDerivedFrom ?annotation .
  ?annotation oa:hasTarget ?target .
  ?target oa:hasSource ?source .
}
ORDER BY ?property
"""


@pytest.fixture
def two_field_graph() -> Graph:
    graph = Graph()
    for name, xpath in [
        ("AOrdNr", "//xs:element[@name='AOrdNr']"),
        ("AbgefKapitalertragsteuer", "//xs:element[@name='AbgefKapitalertragsteuer']"),
    ]:
        outcome = resolve_xpath(REAL_XSD, xpath)
        content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
        annotate_xpath(
            graph, standard="MiKaDiv-FM Meldeart23", shape_name="Meldeart23Fields",
            property_name=name, xpath=xpath, source_uri=f"file://{REAL_XSD}",
            content_hash=content_hash,
        )
    return graph
