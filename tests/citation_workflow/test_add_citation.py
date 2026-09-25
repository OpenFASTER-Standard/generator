import pytest

from citation_workflow.add_citation import FamilyNotFoundError, add_citation
from reference_model.cite import CitationError, cite
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict
from references_catalog.catalog import get_history

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _empty_catalog(tmp_path) -> str:
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}", encoding="utf-8")
    return str(catalog_path)


def test_add_citation_creates_a_page_matching_a_direct_cite_call(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    revision = add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=AORDNR_XPATH,
        fact_key="fact-1", author="julian", comment="initial citation", is_correction=False,
    )

    expected_leaf = cite(
        SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD),
        XPathSelector.create(AORDNR_XPATH),
    )
    history = get_history(catalog_path, "fact-1")
    assert len(history) == 1
    assert history[0].revision_id == revision.revision_id
    assert history[0].reference["reference_id"] == to_json_dict(expected_leaf)["reference_id"]
    assert history[0].author == "julian"
    assert history[0].is_correction is False


def test_add_citation_raises_family_not_found_without_creating_a_page(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    with pytest.raises(FamilyNotFoundError):
        add_citation(
            REAL_MODULE_ROOT, catalog_path,
            family="NoSuchFamilyEver", xpath="/x",
            fact_key="fact-2", author="julian", comment="x", is_correction=False,
        )

    assert get_history(catalog_path, "fact-2") == []


def test_add_citation_twice_for_same_fact_key_appends_a_second_revision(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=AORDNR_XPATH,
        fact_key="fact-3", author="julian", comment="first version", is_correction=False,
    )
    revision_2 = add_citation(
        REAL_MODULE_ROOT, catalog_path,
        family="MiKaDiv_FM_Meldeart23", xpath=ABGEF_XPATH,
        fact_key="fact-3", author="julian", comment="corrected", is_correction=True,
    )

    history = get_history(catalog_path, "fact-3")
    assert len(history) == 2
    assert history[1].revision_id == revision_2.revision_id
    assert history[1].is_correction is True


def test_add_citation_with_an_xpath_that_does_not_resolve_raises_citation_error(tmp_path):
    catalog_path = _empty_catalog(tmp_path)

    with pytest.raises(CitationError):
        add_citation(
            REAL_MODULE_ROOT, catalog_path,
            family="MiKaDiv_FM_Meldeart23", xpath="/xs:schema/xs:complexType[@name='NoSuchThing']",
            fact_key="fact-4", author="julian", comment="x", is_correction=False,
        )

    assert get_history(catalog_path, "fact-4") == []
