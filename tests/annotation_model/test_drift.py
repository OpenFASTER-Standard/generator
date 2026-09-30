from pathlib import Path

import pytest
from rdflib import Graph

from annotation_model.drift import check_drift, check_svg_drift, check_xpath_drift
from annotation_model.namespaces import GEN
from annotation_model.outcomes import Status
from annotation_model.rdf import annotate_xpath
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _annotated_graph(source_uri: str, xpath: str = AORDNR_XPATH):
    outcome = resolve_xpath(source_uri.removeprefix("file://"), xpath)
    content_hash = "sha256:" + canonicalize_and_hash_xml(outcome.raw_content)
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath=xpath,
        source_uri=source_uri,
        content_hash=content_hash,
    )
    return graph, property_shape_iri


@requires_real_corpus
def test_unchanged_source_reports_no_drift():
    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.changed is False
    assert result.current_status == Status.RESOLVED


@requires_real_corpus
def test_content_change_is_detected_as_drift(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('maxOccurs="3000"') == 1
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(original.replace('maxOccurs="3000"', 'maxOccurs="5000"'), encoding="utf-8")

    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=str(mutated_path))
    assert result.changed is True
    assert result.current_status == Status.RESOLVED


@requires_real_corpus
def test_rename_is_reported_as_not_found_not_a_silent_pass(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1
    mutated_path = tmp_path / "renamed.xsd"
    mutated_path.write_text(original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"'), encoding="utf-8")

    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=str(mutated_path))
    assert result.changed is True
    assert result.current_status == Status.NOT_FOUND


@requires_real_corpus
def test_newly_ambiguous_source_is_reported_not_coerced_to_a_bool():
    # annotate_xpath() is a pure RDF builder -- it trusts its caller
    # already resolved successfully and does not re-resolve internally
    # (see Task 3), so a placeholder hash is fine here: this test is
    # only exercising check_xpath_drift's handling of a re-resolution
    # that comes back AMBIGUOUS, not the original annotation's validity.
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath="//xs:element",
        source_uri=f"file://{REAL_XSD}",
        content_hash="sha256:" + "0" * 64,
    )
    # //xs:element matches multiple real nodes in the unmodified file --
    # confirms check_xpath_drift reports AMBIGUOUS distinctly rather than
    # only ever returning RESOLVED/NOT_FOUND.
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.current_status == Status.AMBIGUOUS


@requires_real_corpus
def test_newly_uncitable_resolution_is_reported_not_coerced_to_a_bool():
    graph = Graph()
    property_shape_iri = annotate_xpath(
        graph,
        standard="MiKaDiv-FM Meldeart23",
        shape_name="AOrdNrShape",
        property_name="value",
        xpath=AORDNR_XPATH + "/@name",
        source_uri=f"file://{REAL_XSD}",
        content_hash="sha256:" + "0" * 64,
    )
    # .../@name resolves to an attribute, not an element -- UNCITABLE per
    # the existing, already-proven behavior. Confirms this fourth Status
    # value is also reported distinctly, not folded into NOT_FOUND.
    result = check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)
    assert result.current_status == Status.UNCITABLE


@requires_real_corpus
def test_xpath_drift_check_on_an_svg_shaped_property_raises_clearly_not_a_false_not_found():
    # I5: check_xpath_drift fed an SVG selector's polygon markup to
    # resolve_xpath (which parses it as XML) instead of rejecting the
    # mismatch -- every healthy PDF annotation in a mixed store looked
    # like a broken NOT_FOUND citation.
    from annotation_model.rdf import annotate_svg

    graph = Graph()
    property_shape_iri = annotate_svg(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape", property_name="value",
        page=12, points="60,88 255,88 255,115 60,115",
        source_uri=f"file://{REAL_CORPUS_ROOT}/1.02/khb/khb_mikadiv_fm_de_v9.pdf",
        content_hash="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="XPath"):
        check_xpath_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri="anything")


@requires_real_corpus
def test_svg_drift_unchanged_source_reports_no_drift():
    from annotation_model.rdf import annotate_svg
    from annotation_model.selectors.svg import canonicalize_and_hash_text, resolve_svg_region

    real_pdf = f"{REAL_CORPUS_ROOT}/1.02/khb/khb_mikadiv_fm_de_v9.pdf"
    outcome = resolve_svg_region(real_pdf, 12, "60,88 255,88 255,115 60,115")
    content_hash = "sha256:" + canonicalize_and_hash_text(outcome.raw_content)

    graph = Graph()
    property_shape_iri = annotate_svg(
        graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape", property_name="value",
        page=12, points="60,88 255,88 255,115 60,115",
        source_uri=f"file://{real_pdf}", content_hash=content_hash,
    )

    result = check_svg_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=real_pdf)
    assert result.changed is False
    assert result.current_status == Status.RESOLVED


@requires_real_corpus
def test_svg_drift_check_on_an_xpath_shaped_property_raises_clearly():
    graph, property_shape_iri = _annotated_graph(f"file://{REAL_XSD}")
    with pytest.raises(ValueError, match="SVG"):
        check_svg_drift(graph, property_shape_iri=property_shape_iri, retrieval_uri=REAL_XSD)


@requires_real_corpus
def test_check_drift_dispatches_to_the_right_checker_by_selector_type():
    from annotation_model.rdf import annotate_svg
    from annotation_model.selectors.svg import canonicalize_and_hash_text, resolve_svg_region

    xpath_graph, xpath_iri = _annotated_graph(f"file://{REAL_XSD}")
    xpath_result = check_drift(xpath_graph, property_shape_iri=xpath_iri, retrieval_uri=REAL_XSD)
    assert xpath_result.current_status == Status.RESOLVED

    real_pdf = f"{REAL_CORPUS_ROOT}/1.02/khb/khb_mikadiv_fm_de_v9.pdf"
    outcome = resolve_svg_region(real_pdf, 12, "60,88 255,88 255,115 60,115")
    content_hash = "sha256:" + canonicalize_and_hash_text(outcome.raw_content)
    svg_graph = Graph()
    svg_iri = annotate_svg(
        svg_graph, standard="MiKaDiv-FM Meldeart23", shape_name="AOrdNrShape", property_name="value",
        page=12, points="60,88 255,88 255,115 60,115", source_uri=f"file://{real_pdf}",
        content_hash=content_hash,
    )
    svg_result = check_drift(svg_graph, property_shape_iri=svg_iri, retrieval_uri=real_pdf)
    assert svg_result.current_status == Status.RESOLVED


def test_check_xpath_drift_on_an_incomplete_shape_raises_a_clear_error_not_stopiteration():
    # I11: five chained bare next() calls raised an undiagnosable
    # StopIteration on a typo'd or partially-written property shape IRI.
    from rdflib import URIRef

    with pytest.raises(ValueError, match="no gen:contentHash"):
        check_xpath_drift(Graph(), property_shape_iri=URIRef("http://example.org/nope"), retrieval_uri="/etc/hostname")
