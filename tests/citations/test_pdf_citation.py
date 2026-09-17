import io

import pdfplumber
import pytest
from PIL import Image

from citations.pdf_citation import crop_pdf_page

ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_crop_pdf_page_returns_real_nonempty_png_bytes():
    png_bytes = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0))

    assert len(png_bytes) > 100
    image = Image.open(io.BytesIO(png_bytes))
    assert image.format == "PNG"
    assert image.width > 0 and image.height > 0


def test_crop_pdf_page_applies_padding_around_the_bbox():
    tight = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0), padding=0.0)
    padded = crop_pdf_page(ANNEX_PDF, page_number=5, bbox=(60.0, 60.0, 300.0, 120.0), padding=20.0)

    tight_image = Image.open(io.BytesIO(tight))
    padded_image = Image.open(io.BytesIO(padded))
    assert padded_image.width > tight_image.width
    assert padded_image.height > tight_image.height


def test_crop_pdf_page_rejects_negative_page_number():
    with pytest.raises(ValueError) as excinfo:
        crop_pdf_page(ANNEX_PDF, page_number=-1, bbox=(60.0, 60.0, 300.0, 120.0))

    error_msg = str(excinfo.value)
    assert "page_number=-1" in error_msg
    assert "out of range" in error_msg
    assert "262" in error_msg  # Real page count for this PDF


def test_crop_pdf_page_rejects_page_number_zero():
    # page_number is 1-indexed (see this function's own docstring) -- 0 is
    # exactly the off-by-one value the pre-fix bug effectively produced
    # for every real page-1 citation, so it must be rejected outright now.
    with pytest.raises(ValueError) as excinfo:
        crop_pdf_page(ANNEX_PDF, page_number=0, bbox=(60.0, 60.0, 300.0, 120.0))

    error_msg = str(excinfo.value)
    assert "page_number=0" in error_msg
    assert "out of range" in error_msg


def test_crop_pdf_page_rejects_out_of_range_page_number():
    with pytest.raises(ValueError) as excinfo:
        crop_pdf_page(ANNEX_PDF, page_number=99999, bbox=(60.0, 60.0, 300.0, 120.0))

    error_msg = str(excinfo.value)
    assert "page_number=99999" in error_msg
    assert "out of range" in error_msg
    assert "262" in error_msg  # Real page count for this PDF


def test_crop_pdf_page_uses_the_1_indexed_convention_pdfplumber_itself_uses():
    # Real, confirmed regression anchor (found live via the actual running
    # webapp, not synthesized): AOrdNr's real English citation is
    # page_number=196 at this exact bbox, which is genuinely where
    # "Official serial number." sits on real (pdfplumber 1-indexed) page
    # 196. The pre-fix code opened `pdf.pages[196]` directly -- pdfplumber's
    # own 0-indexed access, which is real page 197, where "ErstmeldungUUID"
    # sits at nearly the same coordinates instead. This asserts byte-exact
    # equality with an independently-cropped render of the CORRECT page,
    # not just "some PNG came back" (which the bug would have satisfied too).
    bbox = (137.64, 610.179, 223.878, 619.179)

    result = crop_pdf_page(ANNEX_PDF, page_number=196, bbox=bbox, padding=0.0)

    with pdfplumber.open(ANNEX_PDF) as pdf:
        assert pdf.pages[195].page_number == 196
        assert pdf.pages[196].page_number == 197
        expected_image = pdf.pages[195].crop(bbox).to_image(resolution=150)
        buffer = io.BytesIO()
        expected_image.original.save(buffer, format="PNG")
        expected_bytes = buffer.getvalue()

    assert result == expected_bytes
