"""Real inline evidence for an English documentation string: a cropped
PNG of the actual annex-PDF page region it came from, not re-typed text.
Verified live against the real annex PDF during design -- pdfplumber
(already a project dependency) can extract word-level bounding boxes and
render/crop a page region directly, no new dependency needed.
"""
from __future__ import annotations

import io

import pdfplumber


def crop_pdf_page(
    pdf_path: str,
    page_number: int,
    bbox: tuple[float, float, float, float],
    padding: float = 5.0,
    resolution: int = 150,
) -> bytes:
    x0, top, x1, bottom = bbox
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
        padded_bbox = (
            max(0.0, x0 - padding),
            max(0.0, top - padding),
            min(page.width, x1 + padding),
            min(page.height, bottom + padding),
        )
        cropped_page = page.crop(padded_bbox)
        page_image = cropped_page.to_image(resolution=resolution)

        buffer = io.BytesIO()
        page_image.original.save(buffer, format="PNG")
        return buffer.getvalue()
