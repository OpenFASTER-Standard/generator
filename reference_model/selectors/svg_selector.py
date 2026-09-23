"""SvgSelector: addresses an arbitrary polygon region on one page of a PDF.

Deliberately not a rectangle-only bounding box -- real PDF paragraphs wrap
irregularly around figures/columns, so an arbitrary polygon (borrowing the
real W3C Web Annotation SvgSelector shape) is needed. `page` is a plain
field rather than a full per-page sub-resource -- a deliberate
simplification, see the design spec.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pdfplumber
from shapely.geometry import Point, Polygon, box

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register

_POINTS_RE = re.compile(r"points=['\"]([^'\"]+)['\"]")


@dataclass(frozen=True)
class SvgSelector:
    """`retrieval_uri` (passed to resolve(), not stored here) is a local
    filesystem path, not a general URI -- pdfplumber has no concept of
    fetching a remote document, unlike XPathSelector's lxml-backed resolve()
    which does accept e.g. file:// URLs. Documented as a path deliberately
    rather than building URI-fetch support neither selector's real, current
    use needs.

    Polygon coordinates are in pdfplumber's own coordinate convention:
    origin at the page's top-left corner, y increasing downward (`top`/
    `bottom`, not PDF's native bottom-up user-space y). A selector authored
    from a PDF library that uses bottom-up y (most do) needs to flip it
    first, or every polygon silently lands on the mirrored region.
    """

    type: str
    page: int  # 1-indexed, matching how humans refer to PDF page numbers
    value: str  # e.g. "<svg:polygon points='60,88 255,88 255,115 60,115' xmlns:svg='...'/>"

    @staticmethod
    def create(page: int, points: str) -> "SvgSelector":
        value = f"<svg:polygon points='{points}' xmlns:svg='http://www.w3.org/2000/svg'/>"
        return SvgSelector(type="SvgSelector", page=page, value=value)

    def polygon(self) -> Polygon:
        match = _POINTS_RE.search(self.value)
        if not match:
            raise ValueError(f"SvgSelector.value has no parseable points= attribute: {self.value!r}")
        coords = []
        for pair in match.group(1).strip().split():
            try:
                x_str, y_str = pair.split(",")
                coords.append((float(x_str), float(y_str)))
            except ValueError as exc:
                raise ValueError(
                    f"SvgSelector.value has a malformed coordinate {pair!r} "
                    f"in points={match.group(1)!r}: {exc}"
                ) from exc
        if len(coords) < 3:
            raise ValueError(f"SvgSelector polygon needs at least 3 points, got {coords!r}")
        polygon = Polygon(coords)
        if polygon.area == 0:
            raise ValueError(f"SvgSelector polygon has zero area, got {coords!r}")
        return polygon


def _overlaps_any(polygon: Polygon, objects) -> bool:
    for obj in objects:
        bbox = box(obj["x0"], obj["top"], obj["x1"], obj["bottom"])
        if polygon.intersects(bbox):
            return True
    return False


def resolve(selector: SvgSelector, retrieval_uri: str) -> ResolutionOutcome:
    # Validate the selector itself first -- document state (a missing file,
    # an out-of-range page) must never mask a malformed selector.
    polygon = selector.polygon()

    try:
        pdf = pdfplumber.open(retrieval_uri)
    except OSError:
        return ResolutionOutcome(status=Status.NOT_FOUND)

    with pdf:
        if selector.page < 1 or selector.page > len(pdf.pages):
            return ResolutionOutcome(status=Status.NOT_FOUND)

        page = pdf.pages[selector.page - 1]
        # Tested by word center, not per-character as the design spec's
        # prose literally says -- a deliberate choice, not an oversight:
        # per-character point-in-polygon is far more brittle across
        # extraction-library versions (character segmentation is not as
        # stable an API contract as word segmentation), and a word
        # straddling the polygon edge is an edge case either granularity
        # has to accept whole-or-nothing for.
        words = page.extract_words()
        matched = [
            w
            for w in words
            if polygon.contains(Point((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
        ]
        if matched:
            matched.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
            text = " ".join(w["text"] for w in matched)
            return ResolutionOutcome(status=Status.RESOLVED, raw_content=text)

        # No text under the polygon -- distinguish "genuinely nothing here"
        # (NOT_FOUND) from "there's real content here, just not
        # machine-checkable text" (UNCITABLE: an image, or a scanned page
        # rendered as a filled shape). Checked at polygon granularity, not
        # whole-page: a page can have real text elsewhere and still have an
        # uncitable image under this specific polygon.
        if _overlaps_any(polygon, page.images) or _overlaps_any(polygon, page.rects):
            return ResolutionOutcome(status=Status.UNCITABLE)
        return ResolutionOutcome(status=Status.NOT_FOUND)


def canonicalize_and_hash(raw_content: str) -> str:
    normalized = " ".join(raw_content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


register("SvgSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
