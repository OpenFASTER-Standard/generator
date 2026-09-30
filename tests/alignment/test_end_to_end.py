from pathlib import Path

from openpyxl import Workbook
from rdflib import Graph

from alignment.institutional_ontology import load_institutional_ontology
from alignment.sssom import mappings_to_graph
from alignment.validate import load_and_validate_mappings
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation, register, unregister
from tests.alignment.fixtures import requires_real_institutional_ontology
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Personentypen_1.02.xsd"
VORNAME_XPATH = (
    "/xs:schema/xs:complexType[@name='PersonNatDatenType']"
    "/xs:complexContent/xs:extension/xs:attribute[@name='Vorname']"
)
# Derived from this test file's own location, not cwd -- a cwd-relative
# path broke when pytest was invoked from a directory other than the
# repo root (Important #7).
REAL_MAPPING_FILE = Path(__file__).resolve().parents[2] / "alignments" / "mikadiv-fm-to-institutional-ontology.sssom.tsv"

ALIGNED_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
  ?property skos:exactMatch <https://purl.openfaster.org/io/IO_0000001> .
}
"""


def _workbook_renderer(rows: list[dict]) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["hash"])
    for row in rows:
        sheet.append([str(row["hash"])])
    return workbook


@requires_real_corpus
@requires_real_institutional_ontology
def test_two_different_renderers_resolve_the_same_fact_through_the_alignment():
    outcome = resolve_xpath(REAL_XSD, VORNAME_XPATH)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    data_graph = Graph()
    annotate_xpath(
        data_graph, standard="MiKaDiv-FM Personentypen", shape_name="PersonentypenFields",
        property_name="Vorname", xpath=VORNAME_XPATH, source_uri=f"file://{REAL_XSD}",
        content_hash=content_hash,
    )

    # load -> validate -> graph, matching the real designed pipeline
    # (Important #6) rather than skipping validation entirely.
    mappings = load_and_validate_mappings(
        REAL_MAPPING_FILE, generator_graph=data_graph, institutional_graph=load_institutional_ontology(),
    )
    alignment_graph = mappings_to_graph(mappings)
    combined_graph = data_graph + alignment_graph

    try:
        register(Transformation(
            name="aligned-bikeshed-1", query=ALIGNED_QUERY,
            renderer=jinja_text_renderer("{% for row in rows %}{{ row['hash'] }}{% endfor %}"),
        ))
        register(Transformation(name="aligned-excel-1", query=ALIGNED_QUERY, renderer=_workbook_renderer))

        text_result = apply_transformation(combined_graph, "aligned-bikeshed-1")
        workbook_result = apply_transformation(combined_graph, "aligned-excel-1")

        assert text_result == content_hash
        sheet = workbook_result.active
        rows = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
        assert rows == [("hash",), (content_hash,)]
    finally:
        unregister("aligned-bikeshed-1")
        unregister("aligned-excel-1")
