import pytest
from openpyxl import Workbook
from rdflib import Graph

from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from annotation_model.transform.apply import apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation, register, unregister
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"

FIELD_QUERY = """
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX gen: <https://openfaster.org/ns/generator#>
SELECT ?shape ?property ?hash WHERE {
  ?shape sh:property ?property .
  ?property gen:contentHash ?hash .
}
ORDER BY ?property
"""

# Item access (row['property']), not attribute access (row.property) --
# see test_a_property_named_like_a_dict_method_does_not_shadow_item_access
# below for why attribute access is an active trap on a real dict row.
TEMPLATE = """{% for row in rows %}{{ row['property'].split('/')[-1] }}: {{ row['hash'] }}
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
    try:
        register(Transformation(name="bikeshed-fields-1", query=FIELD_QUERY, renderer=jinja_text_renderer(TEMPLATE)))
        rendered = apply_transformation(_two_field_graph(), "bikeshed-fields-1")

        assert "AOrdNr: sha256:" in rendered
        assert "AbgefKapitalertragsteuer: sha256:" in rendered
    finally:
        unregister("bikeshed-fields-1")


@requires_real_corpus
def test_a_plain_openpyxl_function_works_as_a_renderer_with_no_framework_code():
    def _workbook_renderer(rows: list[dict]) -> Workbook:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["property", "hash"])
        for row in rows:
            sheet.append([str(row["property"]).split("/")[-1], str(row["hash"])])
        return workbook

    try:
        register(Transformation(name="excel-fields-1", query=FIELD_QUERY, renderer=_workbook_renderer))
        workbook = apply_transformation(_two_field_graph(), "excel-fields-1")

        sheet = workbook.active
        rows = [tuple(cell.value for cell in row) for row in sheet.iter_rows()]
        assert rows[0] == ("property", "hash")
        names = sorted(r[0] for r in rows[1:])
        assert names == sorted(["AOrdNr", "AbgefKapitalertragsteuer"])
        assert all(str(r[1]).startswith("sha256:") for r in rows[1:])
    finally:
        unregister("excel-fields-1")


def test_a_typo_d_template_column_raises_instead_of_rendering_silently_blank():
    render = jinja_text_renderer("{% for row in rows %}{{ row['hahs'] }}{% endfor %}")
    with pytest.raises(Exception):
        render([{"hash": "sha256:abc"}])


def test_a_property_named_like_a_dict_method_does_not_shadow_item_access():
    # I4: jinja's attribute lookup tries a real dict method (row.values,
    # row.items, row.keys, ...) before falling back to item access, so a
    # SPARQL variable named e.g. "values" -- a realistic name in this
    # domain, a code list's allowed values -- silently renders as
    # "<built-in method values of dict object at 0x...>" under attribute
    # access. Item access (row['values']) has no such shadowing.
    render = jinja_text_renderer("{{ rows[0]['values'] }}")
    assert render([{"values": "the-real-value"}]) == "the-real-value"


def test_dangerous_attribute_access_is_blocked_by_the_sandbox():
    # I15: a transformation is registered by calling register(...) from
    # Python, so today's author could already supply an arbitrary Python
    # callable -- sandboxing the *template* buys nothing against that
    # author. It matters the moment a template becomes third-party data
    # (the spec's own Open Questions contemplate a bank registering its
    # own private transformation, roadmap task 6) -- fixing it now, while
    # free, means task 6 never has to revisit this.
    render = jinja_text_renderer("{{ rows[0].__class__ }}")
    with pytest.raises(Exception):
        render([{"x": "y"}])
