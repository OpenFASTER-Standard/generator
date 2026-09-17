"""Formalizes the source-URI scheme webapp/pipeline.py already writes
(`citation:pdf?...`/`citation:xsd?...`) into a real, typed, round-trippable
locator -- without changing the scheme itself, so every fact already
recorded by Plans A-D keeps working unchanged. See the design spec's
"Synced Panes mode + the generic source-viewer abstraction" section.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True)
class PdfLocator:
    path: str
    page: int
    bbox: tuple[float, float, float, float] | None = None
    kind: Literal["pdf"] = "pdf"


@dataclass(frozen=True)
class XsdLocator:
    file: str
    component: str
    kind: Literal["xsd"] = "xsd"


SourceLocator = Union[PdfLocator, XsdLocator]


def locator_to_source_uri(locator: SourceLocator) -> str:
    if isinstance(locator, PdfLocator):
        base = f"citation:pdf?path={locator.path}&page={locator.page}"
        if locator.bbox is None:
            return base
        x0, top, x1, bottom = locator.bbox
        return f"{base}&x0={x0}&top={top}&x1={x1}&bottom={bottom}"
    if isinstance(locator, XsdLocator):
        return f"citation:xsd?file={locator.file}&component={locator.component}"
    raise TypeError(f"unknown locator type: {locator!r}")


def source_uri_to_locator(source_uri: str) -> SourceLocator | None:
    if source_uri.startswith("citation:pdf?"):
        params = urllib.parse.parse_qs(source_uri[len("citation:pdf?"):])
        bbox = None
        if "x0" in params:
            bbox = (
                float(params["x0"][0]), float(params["top"][0]),
                float(params["x1"][0]), float(params["bottom"][0]),
            )
        return PdfLocator(path=params["path"][0], page=int(params["page"][0]), bbox=bbox)
    if source_uri.startswith("citation:xsd?"):
        params = urllib.parse.parse_qs(source_uri[len("citation:xsd?"):])
        return XsdLocator(file=params["file"][0], component=params["component"][0])
    return None


def locator_lookup_key(locator: SourceLocator) -> str:
    """The source-URI *prefix pattern* every fact recorded at this locator's
    own granularity shares -- page-level for PDF (deliberately ignores
    bbox), the full exact URI for XSD (there is no finer granularity to
    ignore). Used by provenance.reverse_lookup to build a REGEX-anchored
    SPARQL filter, not a plain string match, so a source_uri never
    partially matches a different one with the same numeric prefix (e.g.
    page=196 must never match page=1960) -- see reverse_lookup's own
    docstring for the verified-live query shape.
    """
    if isinstance(locator, PdfLocator):
        return f"citation:pdf?path={locator.path}&page={locator.page}"
    if isinstance(locator, XsdLocator):
        return locator_to_source_uri(locator)
    raise TypeError(f"unknown locator type: {locator!r}")
