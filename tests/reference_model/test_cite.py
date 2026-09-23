from pathlib import Path

import pytest

from reference_model.cite import CitationError, check_leaf, check_reference, cite, cite_union
from reference_model.model import SubjectDocument, Status, compute_union_reference_id
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


def test_cite_union_raises_for_an_empty_parts_list():
    # An empty Union would be a well-formed Reference backed by nothing --
    # a staleness sweep asking "did any part fail?" over zero parts always
    # says no, forever. That's the one case the "by construction" guarantee
    # (see the next test) doesn't close on its own.
    with pytest.raises(CitationError):
        cite_union([])


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


def test_check_leaf_detects_a_changed_hash_for_a_changed_pdf_region(tmp_path: Path):
    # The XSD path already has hash_changed coverage above; SvgSelector's
    # canonicalize_and_hash is entirely different code (whitespace-collapsed
    # text, not C14N bytes) and had none -- this is the one place the
    # branch didn't actually demonstrate the property the model exists to
    # provide, for the PDF selector kind specifically.
    from reportlab.pdfgen import canvas as reportlab_canvas

    def make_pdf(path: Path, text: str) -> None:
        c = reportlab_canvas.Canvas(str(path), pagesize=(300, 100))
        c.drawString(20, 50, text)
        c.showPage()
        c.save()

    original_path = tmp_path / "sample.pdf"
    make_pdf(original_path, "Hello World")

    subject_document = SubjectDocument(family="synthetic-pdf", version="1", retrieval_uri=str(original_path))
    selector = SvgSelector.create(1, "0,0 300,0 300,100 0,100")
    leaf = cite(subject_document, selector)

    changed_path = tmp_path / "sample-changed.pdf"
    make_pdf(changed_path, "Goodbye World")

    result = check_leaf(leaf, retrieval_uri=str(changed_path))
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is True


def test_union_spanning_a_page_break_cites_both_real_pages():
    # The design spec's own headline motivating example: one citation
    # spanning a page break, as a Union of two same-document,
    # different-page SvgSelector leaves. Real text on page 13: "Bei den
    # Antwortnachrichten wird..."
    page_12_leaf = cite(_pdf_subject_document(), SvgSelector.create(PAGE_12, HEADING_POINTS))
    page_13_leaf = cite(_pdf_subject_document(), SvgSelector.create(13, "65,70 270,70 270,86 65,86"))
    union = cite_union([page_12_leaf, page_13_leaf])

    assert union.parts == (page_12_leaf, page_13_leaf)

    results = check_reference(union)
    assert [r.outcome.status for r in results] == [Status.RESOLVED, Status.RESOLVED]
    assert [r.hash_changed for r in results] == [False, False]


def test_nested_union_flattens_correctly_through_check_reference():
    # The spec states Union nesting is unrestricted; this pins that a
    # Union-of-a-Union both computes reference_id recursively and flattens
    # to every leaf's own result through check_reference(), not just the
    # top level's immediate parts.
    xsd_leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))
    page_12_leaf = cite(_pdf_subject_document(), SvgSelector.create(PAGE_12, HEADING_POINTS))
    page_13_leaf = cite(_pdf_subject_document(), SvgSelector.create(13, "65,70 270,70 270,86 65,86"))

    inner_union = cite_union([page_12_leaf, page_13_leaf])
    outer_union = cite_union([xsd_leaf, inner_union])

    assert outer_union.reference_id == compute_union_reference_id(
        [xsd_leaf.reference_id, inner_union.reference_id]
    )

    results = check_reference(outer_union)
    assert len(results) == 3
    assert all(r.outcome.status == Status.RESOLVED for r in results)


def test_check_leaf_detects_a_changed_hash_without_a_status_change(tmp_path: Path):
    leaf = cite(_xsd_subject_document(), XPathSelector.create(AORDNR_XPATH))

    original = Path(REAL_XSD).read_text(encoding="utf-8")
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = check_leaf(leaf, retrieval_uri=str(mutated_path))
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is True
