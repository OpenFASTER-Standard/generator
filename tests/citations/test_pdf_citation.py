import io

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


def test_crop_pdf_page_rejects_out_of_range_page_number():
    with pytest.raises(ValueError) as excinfo:
        crop_pdf_page(ANNEX_PDF, page_number=99999, bbox=(60.0, 60.0, 300.0, 120.0))

    error_msg = str(excinfo.value)
    assert "page_number=99999" in error_msg
    assert "out of range" in error_msg
    assert "262" in error_msg  # Real page count for this PDF
