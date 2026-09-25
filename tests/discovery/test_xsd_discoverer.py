import glob

from lxml import etree

from discovery.xsd_discoverer import DiscoveryResult, discover_candidates

REAL_XSD_DIR = "/work/ontologies/mikadiv-fm/sources/1.02/xsd"
REAL_MELDEART23_XSD = f"{REAL_XSD_DIR}/MiKaDiv_FM_Meldeart23_1.02.xsd"
_XS_NS = "http://www.w3.org/2001/XMLSchema"

AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def test_discovers_ground_truth_element_candidates():
    result = discover_candidates(REAL_MELDEART23_XSD)
    xpaths_by_name = {c.name: c.xpath for c in result.candidates}
    assert xpaths_by_name["AOrdNr"] == AORDNR_XPATH
    assert xpaths_by_name["AbgefKapitalertragsteuer"] == ABGEF_XPATH


def test_discovers_complextype_candidates_too():
    result = discover_candidates(REAL_MELDEART23_XSD)
    complex_type_names = {c.name for c in result.candidates if c.tag == "complexType"}
    assert "Meldeart23" in complex_type_names
    assert "AmtlicheOrdnungsnummerMa23ListeType" in complex_type_names


def test_every_candidate_xpath_resolves_to_exactly_one_node():
    tree = etree.parse(REAL_MELDEART23_XSD)
    result = discover_candidates(REAL_MELDEART23_XSD)
    for candidate in result.candidates:
        matches = tree.xpath(candidate.xpath, namespaces={"xs": _XS_NS})
        assert len(matches) == 1, candidate


def test_no_duplicate_xpaths_among_candidates():
    result = discover_candidates(REAL_MELDEART23_XSD)
    xpaths = [c.xpath for c in result.candidates]
    assert len(xpaths) == len(set(xpaths))


def test_candidates_and_excluded_account_for_every_named_node():
    tree = etree.parse(REAL_MELDEART23_XSD)
    # Independent count, written directly here -- not by importing any
    # private helper from discovery.xsd_discoverer, so this test can't
    # pass merely because it shares a bug with the implementation.
    named_node_count = sum(
        1
        for node in tree.iter()
        if isinstance(node.tag, str)
        and node.tag.startswith(f"{{{_XS_NS}}}")
        and node.get("name") is not None
    )

    result = discover_candidates(REAL_MELDEART23_XSD)

    assert named_node_count > 0
    assert len(result.candidates) + len(result.excluded) == named_node_count


def test_discovers_candidates_across_the_full_real_corpus():
    xsd_files = sorted(glob.glob(f"{REAL_XSD_DIR}/*.xsd"))
    assert len(xsd_files) == 13
    for xsd_path in xsd_files:
        result = discover_candidates(xsd_path)
        assert isinstance(result, DiscoveryResult)
        assert len(result.candidates) >= 1, xsd_path


def test_deeply_nested_real_candidate_has_full_multilevel_xpath():
    result = discover_candidates(f"{REAL_XSD_DIR}/MiKaDiv_FM_Meldeart13_1.02.xsd")
    xpaths_by_name = {c.name: c.xpath for c in result.candidates}
    assert xpaths_by_name["Paymentlines"] == (
        "/xs:schema/xs:complexType[@name='Meldeart13']/xs:complexContent"
        "/xs:extension/xs:sequence/xs:element[@name='KontoListe']"
        "/xs:complexType/xs:sequence/xs:element[@name='Konto']"
        "/xs:complexType/xs:sequence/xs:element[@name='Paymentlines']"
    )
