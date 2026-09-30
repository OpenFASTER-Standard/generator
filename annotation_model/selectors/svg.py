"""Resolves an arbitrary polygon region on one page of a real PDF."""
from __future__ import annotations

import hashlib
import re

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException
from shapely.geometry import Point, Polygon, box

from annotation_model.outcomes import ResolutionOutcome, Status

_POINTS_RE = re.compile(r"points=['\"]([^'\"]+)['\"]")


def extract_points(svg_value: str) -> str:
    """Recovers the raw "x,y x,y ..." points string from the inline SVG
    markup annotate_svg() stores as a selector's rdf:value -- used by
    drift checking, which only has that stored string to re-resolve from.
    """
    match = _POINTS_RE.search(svg_value)
    if not match:
        raise ValueError(f"no parseable points= attribute in {svg_value!r}")
    return match.group(1)


def _parse_points(points: str) -> Polygon:
    coords = []
    for pair in points.strip().split():
        try:
            x_str, y_str = pair.split(",")
            coords.append((float(x_str), float(y_str)))
        except ValueError as exc:
            raise ValueError(f"malformed coordinate {pair!r} in points={points!r}: {exc}") from exc
    if len(coords) < 3:
        raise ValueError(f"polygon needs at least 3 points, got {coords!r}")
    polygon = Polygon(coords)
    if polygon.area == 0:
        raise ValueError(f"polygon has zero area, got {coords!r}")
    return polygon


def _overlaps_any(polygon: Polygon, objects) -> bool:
    for obj in objects:
        bbox = box(obj["x0"], obj["top"], obj["x1"], obj["bottom"])
        if polygon.intersects(bbox):
            return True
    return False


def resolve_svg_region(retrieval_uri: str, page: int, points: str) -> ResolutionOutcome:
    """Two different failure channels, deliberately: a malformed `points`
    selector (not enough points, unparseable coordinates, zero area)
    raises ValueError, since that's a bug in the caller's own selector,
    not a fact about the document. Everything about the *document*
    (missing, corrupt, page out of range, nothing under the polygon)
    comes back as a ResolutionOutcome instead -- resolve_xpath never
    raises at all, so this asymmetry is specific to this function; a
    caller resolving an unknown selector type needs to know both.
    """
    # Validate the selector itself first -- document state (a missing
    # file, an out-of-range page) must never mask a malformed selector.
    polygon = _parse_points(points)

    try:
        pdf = pdfplumber.open(retrieval_uri)
    except (OSError, PdfminerException):
        # OSError: missing/unreadable file. PdfminerException: the file
        # exists but isn't a valid PDF -- also nothing to resolve against,
        # and symmetric with resolve_xpath's own etree.XMLSyntaxError ->
        # NOT_FOUND mapping. Without this, a single truncated PDF in a
        # store would abort an entire drift sweep instead of flagging just
        # that one annotation.
        return ResolutionOutcome(status=Status.NOT_FOUND)

    with pdf:
        if page < 1 or page > len(pdf.pages):
            return ResolutionOutcome(status=Status.NOT_FOUND)

        pdf_page = pdf.pages[page - 1]
        # Tested by word center, not per-character -- per-character
        # point-in-polygon is far more brittle across extraction-library
        # versions than word segmentation.
        words = pdf_page.extract_words()
        matched = [
            w
            for w in words
            if polygon.contains(Point((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
        ]
        if matched:
            matched.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
            text = " ".join(w["text"] for w in matched)
            return ResolutionOutcome(status=Status.RESOLVED, raw_content=text)

        # No text under the polygon -- distinguish "genuinely nothing
        # here" (NOT_FOUND) from "there's real content here, just not
        # machine-checkable text" (UNCITABLE: an image, or a scanned
        # page rendered as a filled shape).
        if _overlaps_any(polygon, pdf_page.images) or _overlaps_any(polygon, pdf_page.rects):
            return ResolutionOutcome(status=Status.UNCITABLE)
        return ResolutionOutcome(status=Status.NOT_FOUND)


def canonicalize_and_hash_text(raw_content: str) -> str:
    normalized = " ".join(raw_content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
