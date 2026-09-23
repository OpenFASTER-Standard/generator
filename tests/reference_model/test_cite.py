from pathlib import Path

import pytest

from reference_model.cite import CitationError, check_leaf, check_reference, cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.svg_selector import SvgSelector
from reference_model.selectors.xpath_selector import XPathSelector

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
REAL_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12
HEADING_POINTS = "60,88 255,88 255,115 60,115"


def _xsd_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def _pdf_subject_document() -> SubjectDocument:
    return SubjectDocument(family="khb_mikadiv_fm_de", version="v9", retrieval_uri=REAL_PDF)


def test_cite_builds_a_leaf_from_a_real_xsd_element():
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    assert leaf.subject_document.family == "MiKaDiv_FM_Meldeart23"
    assert leaf.content_hash.algorithm == "sha256"
    assert len(leaf.content_hash.digest) == 64


def test_citing_the_same_span_twice_is_idempotent():
    leaf_1 = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    assert leaf_1.reference_id == leaf_2.reference_id
    assert leaf_1.content_hash.digest == leaf_2.content_hash.digest


def test_cite_raises_when_selector_does_not_resolve():
    bad_selector = XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']")
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), bad_selector)


def test_cite_raises_when_selector_is_ambiguous():
    ambiguous_selector = XPathSelector.create("//xs:element")
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), ambiguous_selector)


def test_cite_raises_when_region_is_uncitable(tmp_path: Path):
    from reportlab.pdfgen import canvas as reportlab_canvas

    no_text_pdf = tmp_path / "no-text.pdf"
    c = reportlab_canvas.Canvas(str(no_text_pdf), pagesize=(200, 200))
    c.rect(10, 10, 180, 180, fill=1)
    c.showPage()
    c.save()

    subject_document = SubjectDocument(family="synthetic", version="1", retrieval_uri=str(no_text_pdf))
    selector = SvgSelector.create(1, "0,0 200,0 200,200 0,200")
    with pytest.raises(CitationError):
        cite(subject_document, selector)


def test_a_union_can_only_ever_contain_already_resolved_leaves():
    # There is no way to construct a Leaf that failed to resolve -- cite()
    # already raised before one could exist -- so a Union is guaranteed by
    # construction to never contain a broken part. This test documents and
    # pins that guarantee rather than re-checking it defensively at
    # cite_union() time.
    good_leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    with pytest.raises(CitationError):
        cite(_xsd_subject_document(), XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']"))
    # The only Leaf available to put in a Union is the one that already
    # succeeded above.
    union = cite_union([good_leaf])
    assert union.parts == (good_leaf,)


def test_check_reference_on_a_union_reports_each_part_independently(tmp_path: Path):
    xsd_leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    pdf_leaf = cite(_pdf_subject_document(), SvgSelector.create(PAGE_12, HEADING_POINTS))
    union = cite_union([xsd_leaf, pdf_leaf])

    # Break only the XSD part, by pointing that family's re-check at a
    # mutated temp copy while the PDF part is re-checked against its real,
    # unchanged file.
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    results = check_reference(union, retrieval_overrides={"MiKaDiv_FM_Meldeart23": str(mutated_path)})
    results_by_family = {r.leaf.subject_document.family: r for r in results}

    assert results_by_family["MiKaDiv_FM_Meldeart23"].outcome.status == Status.NOT_FOUND
    assert results_by_family["khb_mikadiv_fm_de"].outcome.status == Status.RESOLVED
    assert results_by_family["khb_mikadiv_fm_de"].hash_changed is False


def test_check_leaf_detects_a_changed_hash_without_a_status_change(tmp_path: Path):
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))

    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = check_leaf(leaf, retrieval_uri=str(mutated_path))
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is True
