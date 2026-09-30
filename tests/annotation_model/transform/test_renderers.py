from openpyxl import Workbook

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation, register
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus
from rdflib import Graph

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

TEMPLATE = """{% for row in rows %}{{ row.property.split('/')[-1] }}: {{ row.hash }}
{% endfor %}"""


def _two_field_graph() -> Graph:
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


@requires_real_corpus
def test_jinja_text_renderer_produces_real_rendered_bikeshed_like_text():
    register(Transformation(name="bikeshed-fields-1", query=FIELD_QUERY, renderer=jinja_text_renderer(TEMPLATE)))
    rendered = apply_transformation(_two_field_graph(), "bikeshed-fields-1")

    assert "AOrdNr: sha256:" in rendered
    assert "AbgefKapitalertragsteuer: sha256:" in rendered


@requires_real_corpus
def test_a_plain_openpyxl_function_works_as_a_renderer_with_no_framework_code():
    def _workbook_renderer(rows: list[dict]) -> Workbook:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["property", "hash"])
        for row in rows:
            sheet.append([str(row["property"]).split("/")[-1], str(row["hash"])])
        return workbook

    register(Transformation(name="excel-fields-1", query=FIELD_QUERY, renderer=_workbook_renderer))
    workbook = apply_transformation(_two_field_graph(), "excel-fields-1")

    sheet = workbook.active
    rows = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
    assert rows[0] == ("property", "hash")
    names = sorted(r[0] for r in rows[1:])
    assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])
    assert all(str(r[1]).startswith("sha256:") for r in rows[1:])
