from citations.locator import (
    PdfLocator,
    XsdLocator,
    locator_lookup_key,
    locator_to_source_uri,
    source_uri_to_locator,
)


def test_pdf_locator_with_bbox_round_trips_through_source_uri():
    locator = PdfLocator(path="/a/b.pdf", page=196, bbox=(137.64, 610.179, 223.878, 619.179))
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:pdf?path=/a/b.pdf&page=196&x0=137.64&top=610.179&x1=223.878&bottom=619.179"
    assert source_uri_to_locator(source_uri) == locator


def test_pdf_locator_without_bbox_round_trips():
    locator = PdfLocator(path="/a/b.pdf", page=5)
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:pdf?path=/a/b.pdf&page=5"
    assert source_uri_to_locator(source_uri) == locator


def test_xsd_locator_round_trips():
    locator = XsdLocator(file="/a/b.xsd", component="{urn:ns}TypeName")
    source_uri = locator_to_source_uri(locator)
    assert source_uri == "citation:xsd?file=/a/b.xsd&component={urn:ns}TypeName"
    assert source_uri_to_locator(source_uri) == locator


def test_source_uri_to_locator_returns_none_for_an_unrecognized_scheme():
    assert source_uri_to_locator("https://example.org/something") is None


def test_pdf_locator_lookup_key_ignores_bbox():
    with_bbox = PdfLocator(path="/a/b.pdf", page=196, bbox=(1.0, 2.0, 3.0, 4.0))
    without_bbox = PdfLocator(path="/a/b.pdf", page=196)
    assert locator_lookup_key(with_bbox) == locator_lookup_key(without_bbox)
    assert locator_lookup_key(with_bbox) == "citation:pdf?path=/a/b.pdf&page=196"


def test_xsd_locator_lookup_key_is_the_full_source_uri():
    locator = XsdLocator(file="/a/b.xsd", component="{urn:ns}TypeName")
    assert locator_lookup_key(locator) == locator_to_source_uri(locator)
