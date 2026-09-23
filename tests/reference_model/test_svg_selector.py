from pathlib import Path

import pytest

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.svg_selector import SvgSelector

REAL_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12  # confirmed: real page with a text layer, out of 45 total pages

# Real word bounding boxes on page 12, verified live against the actual file:
#   "2.2 Nachrichteninhalte" heading: x [70.9, 246.8], top [92.1, 110.1]
#   "Inhalt einer Nachricht" caption: x [180.2, 260.7], top [572.4, 581.4]
#   a verified-blank region with zero overlapping words: x [400, 550], top [200, 220]
HEADING_POINTS = "60,88 255,88 255,115 60,115"
CAPTION_POINTS = "170,565 270,565 270,590 170,590"
BLANK_POINTS = "400,200 550,200 550,220 400,220"


def _resolver():
    return get_resolver("SvgSelector")


def test_resolves_real_heading_and_hash_is_reproducible():
    selector = SvgSelector.create(PAGE_12, HEADING_POINTS)
    resolver = _resolver()

    outcome_1 = resolver.resolve(selector, REAL_PDF)
    assert outcome_1.status == Status.RESOLVED
    assert "Nachrichteninhalte" in outcome_1.raw_content

    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)
    outcome_2 = resolver.resolve(selector, REAL_PDF)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)
    assert digest_1 == digest_2


def test_different_real_region_produces_different_hash():
    resolver = _resolver()
    heading_outcome = resolver.resolve(SvgSelector.create(PAGE_12, HEADING_POINTS), REAL_PDF)
    caption_outcome = resolver.resolve(SvgSelector.create(PAGE_12, CAPTION_POINTS), REAL_PDF)

    assert "Inhalt" in caption_outcome.raw_content
    heading_digest = resolver.canonicalize_and_hash(heading_outcome.raw_content)
    caption_digest = resolver.canonicalize_and_hash(caption_outcome.raw_content)
    assert heading_digest != caption_digest


def test_german_umlauts_and_eszett_round_trip_through_the_hash():
    # "Dateigröße" -- real body text a few lines below the heading on this
    # same page -- contains both an umlaut (ö) and an eszett (ß).
    selector = SvgSelector.create(PAGE_12, "118,155 174,155 174,172 118,172")
    resolver = _resolver()
    outcome = resolver.resolve(selector, REAL_PDF)
    assert outcome.status == Status.RESOLVED
    assert outcome.raw_content == "Dateigröße"
    digest = resolver.canonicalize_and_hash(outcome.raw_content)
    assert len(digest) == 64  # did not raise a UnicodeEncodeError etc.


def test_blank_region_is_not_found():
    selector = SvgSelector.create(PAGE_12, BLANK_POINTS)
    outcome = _resolver().resolve(selector, REAL_PDF)
    assert outcome.status == Status.NOT_FOUND


def test_nonexistent_page_is_not_found():
    selector = SvgSelector.create(46, HEADING_POINTS)  # real PDF has only 45 pages
    outcome = _resolver().resolve(selector, REAL_PDF)
    assert outcome.status == Status.NOT_FOUND


def test_page_with_no_text_layer_is_uncitable(tmp_path: Path):
    from reportlab.pdfgen import canvas as reportlab_canvas

    no_text_pdf = tmp_path / "no-text.pdf"
    c = reportlab_canvas.Canvas(str(no_text_pdf), pagesize=(200, 200))
    c.rect(10, 10, 180, 180, fill=1)  # a filled rectangle -- no text-drawing calls at all
    c.showPage()
    c.save()

    selector = SvgSelector.create(1, "0,0 200,0 200,200 0,200")
    outcome = _resolver().resolve(selector, str(no_text_pdf))
    assert outcome.status == Status.UNCITABLE


def test_missing_source_file_is_not_found():
    selector = SvgSelector.create(PAGE_12, HEADING_POINTS)
    outcome = _resolver().resolve(selector, "/nonexistent/path/does-not-exist.pdf")
    assert outcome.status == Status.NOT_FOUND


def test_image_region_on_a_page_with_text_elsewhere_is_uncitable():
    # Real page 1 has an image at x [16.2, 178.0], top [29.6, 127.6], and
    # 29 words of real text elsewhere on the same page -- so "the whole
    # page has zero words" is not a sufficient UNCITABLE test; a polygon
    # over the image specifically must be UNCITABLE too, not NOT_FOUND.
    selector = SvgSelector.create(1, "16,30 178,30 178,127 16,127")
    outcome = _resolver().resolve(selector, REAL_PDF)
    assert outcome.status == Status.UNCITABLE


def test_malformed_points_raises_a_clear_error():
    selector = SvgSelector(type="SvgSelector", page=PAGE_12, value="<svg:polygon xmlns:svg='http://www.w3.org/2000/svg'/>")
    with pytest.raises(ValueError, match="points="):
        _resolver().resolve(selector, REAL_PDF)


def test_malformed_coordinate_raises_a_clear_error_naming_the_bad_pair():
    selector = SvgSelector(
        type="SvgSelector", page=PAGE_12,
        value="<svg:polygon points='abc,def 1,1 2,2' xmlns:svg='http://www.w3.org/2000/svg'/>",
    )
    with pytest.raises(ValueError, match="abc,def"):
        _resolver().resolve(selector, REAL_PDF)


def test_zero_area_polygon_raises_a_clear_error():
    selector = SvgSelector.create(PAGE_12, "0,0 0,0 0,0")
    with pytest.raises(ValueError, match="zero area"):
        _resolver().resolve(selector, REAL_PDF)


def test_malformed_selector_is_caught_before_the_page_bounds_check():
    # Document state (an out-of-range page) must never mask a broken
    # selector -- the selector itself is validated first.
    selector = SvgSelector(type="SvgSelector", page=999, value="<svg:polygon xmlns:svg='http://www.w3.org/2000/svg'/>")
    with pytest.raises(ValueError, match="points="):
        _resolver().resolve(selector, REAL_PDF)
