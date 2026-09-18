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

import xmlschema


@dataclass(frozen=True)
class XsdCitation:
    fragment: str
    source_file: str


def resolve_xsd_component(schema: xmlschema.XMLSchema, qname: str):
    """Resolves a component back to its real xmlschema object, given the
    same Clark-notation qname extraction/uris.py mints as that
    component's own citable identity: `{namespace}GlobalName` for
    anything with real global XSD identity, or
    `{namespace}GlobalName.local1.local2...` for a declaration scoped
    inside one -- see extraction/uris.py's own docstring on why local
    element/attribute declarations (and the anonymous types they can
    own) get a dotted, scoped identity instead of a flat one: XSD itself
    gives them no identity outside that scope, so a bare local name is
    not unique across types (149 real xs:attribute declarations in this
    corpus, zero global, is the confirmed reason that module gives).

    Previously, both call sites that needed this (webapp/pipeline.py's
    provenance attachment, webapp/routes_provenance.py's citation
    rendering) only ever checked `schema.maps.types`/`schema.maps.elements`
    directly and explicitly skipped anything with a "." in it -- so ANY
    locally-scoped declaration's citation was unconditionally treated as
    unavailable, not just genuinely unresolvable ones. Real, confirmed
    impact: 239 of 377 documented subjects in this corpus are locally
    scoped, so this was the majority case, not an edge case -- e.g.
    `AmtlicheOrdnungsnummerMa23ListeType.AOrdNr` (a local element inside
    a global complex type), whose German documentation is real and
    present but was always reported as "no source recorded" even though
    its English documentation (attached via the separate PDF-occurrence
    path, unaffected by this) always resolved correctly.

    Returns None if any segment can't be resolved (a genuinely
    unsupported shape, e.g. a simple-type union member's synthetic
    `Member{N}` segment -- this corpus's simple_types.py mints those but
    nothing walks into a union member's own citable fragment separately
    from its owning type's), so callers can report "no citation
    available" honestly instead of crashing.
    """
    namespace_end = qname.index("}")
    global_name, *segments = qname[namespace_end + 1 :].split(".")
    global_qname = qname[: namespace_end + 1] + global_name
    component = schema.maps.types.get(global_qname) or schema.maps.elements.get(global_qname)
    for segment in segments:
        if component is None:
            return None
        component = _descend(component, segment)
    return component


def _descend(component, segment: str):
    if segment == "Type":
        # An anonymous complex/simple type owned by the element/attribute
        # `component` -- see extraction/uris.py's own type_uri.
        return getattr(component, "type", None)
    if segment.startswith("@"):
        attributes = getattr(component, "attributes", None)
        return attributes.get(segment[1:]) if attributes is not None else None
    # A local element -- content lives on a type, not on an element
    # object itself, so descend into `.type` first if `component` is one
    # (an XsdComplexType already has `.content` directly, e.g. when this
    # is the very first segment after a global type).
    content_owner = component if hasattr(component, "content") else getattr(component, "type", None)
    content = getattr(content_owner, "content", None)
    return _find_in_content_model(content, segment) if content is not None else None


def _find_in_content_model(group, local_name: str):
    # Mirrors extraction/complex_types.py's own _extract_content_model
    # recursion exactly: a nested Choice/Sequence group's own particles
    # were minted under the SAME owner URI during extraction (no
    # group-level URI segment of their own), so a search here must
    # recurse into nested groups transparently too, not just scan one
    # flat level.
    for particle in group.iter_model():
        if isinstance(particle, xmlschema.validators.groups.XsdGroup):
            found = _find_in_content_model(particle, local_name)
            if found is not None:
                return found
        elif getattr(particle, "local_name", None) == local_name:
            return particle
    return None


def capture_xsd_fragment(xsd_component) -> XsdCitation:
    fragment = ET.tostring(xsd_component.elem, encoding="unicode")
    # xsd_component.schema.source.url is a file:// URL, not a real,
    # openable filesystem path -- convert it so source_file is directly
    # usable with open()/os.path.exists() as its name and docstring imply.
    # url2pathname (not a bare urlparse().path) correctly handles any
    # percent-escaped special characters in the URL.
    source_file = urllib.request.url2pathname(urllib.parse.urlparse(xsd_component.schema.source.url).path)
    return XsdCitation(fragment=fragment, source_file=source_file)
