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
from shapely.geometry import Point, Polygon

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register

_POINTS_RE = re.compile(r"points=['\"]([^'\"]+)['\"]")


@dataclass(frozen=True)
class SvgSelector:
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
            x_str, y_str = pair.split(",")
            coords.append((float(x_str), float(y_str)))
        if len(coords) < 3:
            raise ValueError(f"SvgSelector polygon needs at least 3 points, got {coords!r}")
        return Polygon(coords)


def resolve(selector: SvgSelector, retrieval_uri: str) -> ResolutionOutcome:
    with pdfplumber.open(retrieval_uri) as pdf:
        if selector.page < 1 or selector.page > len(pdf.pages):
            return ResolutionOutcome(status=Status.NOT_FOUND)

        page = pdf.pages[selector.page - 1]
        words = page.extract_words()
        if not words:
            # The whole page has no text layer at all -- a scanned/image-only
            # page, not merely an empty region on an otherwise textful page.
            return ResolutionOutcome(status=Status.UNCITABLE)

        polygon = selector.polygon()
        matched = [
            w
            for w in words
            if polygon.contains(Point((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
        ]
        if not matched:
            return ResolutionOutcome(status=Status.NOT_FOUND)

        matched.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
        text = " ".join(w["text"] for w in matched)
        return ResolutionOutcome(status=Status.RESOLVED, raw_content=text)


def canonicalize_and_hash(raw_content: str) -> str:
    normalized = " ".join(raw_content.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


register("SvgSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
