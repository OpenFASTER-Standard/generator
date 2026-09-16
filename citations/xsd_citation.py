"""Real inline evidence for a structural XSD fact: the exact source
fragment and file it came from, not a re-typed summary. Verified live
during design: xmlschema's parsed objects expose `.elem` (a stdlib
ElementTree element, since xmlschema itself doesn't use lxml) --
ET.tostring gives the exact byte-faithful fragment, and
`.schema.source.url` gives the real file (the corpus is split across
multiple included files, so this is often not the root file extraction
was pointed at) -- converted from its raw `file://...` URL form to a
real, openable filesystem path before being returned as `source_file`.
No line number here -- xmlschema's stdlib ElementTree
parse drops source line info; recovering it needs a separate lxml pass,
deliberately out of scope for this task (see the design spec's
Non-Goals).
"""
from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class XsdCitation:
    fragment: str
    source_file: str


def capture_xsd_fragment(xsd_component) -> XsdCitation:
    fragment = ET.tostring(xsd_component.elem, encoding="unicode")
    # xsd_component.schema.source.url is a file:// URL, not a real,
    # openable filesystem path -- convert it so source_file is directly
    # usable with open()/os.path.exists() as its name and docstring imply.
    # url2pathname (not a bare urlparse().path) correctly handles any
    # percent-escaped special characters in the URL.
    source_file = urllib.request.url2pathname(urllib.parse.urlparse(xsd_component.schema.source.url).path)
    return XsdCitation(fragment=fragment, source_file=source_file)
