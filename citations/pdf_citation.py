"""Real inline evidence for an English documentation string: a cropped
PNG of the actual annex-PDF page region it came from, not re-typed text.
Verified live against the real annex PDF during design -- pdfplumber
(already a project dependency) can extract word-level bounding boxes and
render/crop a page region directly, no new dependency needed.
"""
from __future__ import annotations

import io

import pdfplumber


def _open_validated_page(pdf: pdfplumber.PDF, page_number: int, pdf_path: str):
    """`page_number` is 1-indexed, matching pdfplumber's own `Page.page_number`
    attribute -- the same convention `extraction.annex_pdf.TextOccurrence`
    (the only real producer of a citation's page_number) already uses and
    documents. This was a real, previously-shipped off-by-one bug in
    `crop_pdf_page` (fixed 2026-09-17): it used to index `pdf.pages` directly
    with the 1-indexed value, silently cropping the page AFTER the intended
    one for every citation in the system -- invisible to every existing test
    at the time, since none of them checked cropped *content*, only that some
    non-empty PNG came back.
    """
    if not (1 <= page_number <= len(pdf.pages)):
        raise ValueError(
            f"page_number={page_number} out of range for {pdf_path} "
            f"(has {len(pdf.pages)} pages, 1-indexed)"
        )
    return pdf.pages[page_number - 1]


def crop_pdf_page(
    pdf_path: str,
    page_number: int,
    bbox: tuple[float, float, float, float],
    padding: float = 5.0,
    resolution: int = 150,
) -> bytes:
    x0, top, x1, bottom = bbox
    with pdfplumber.open(pdf_path) as pdf:
        page = _open_validated_page(pdf, page_number, pdf_path)
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


def render_pdf_page(pdf_path: str, page_number: int, resolution: int = 150) -> bytes:
    """The whole page, uncropped -- for Synced Panes mode's source pane,
    which shows a real, complete page a user can scroll/click through,
    not a single fact's citation crop.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = _open_validated_page(pdf, page_number, pdf_path)
        page_image = page.to_image(resolution=resolution)

        buffer = io.BytesIO()
        page_image.original.save(buffer, format="PNG")
        return buffer.getvalue()
