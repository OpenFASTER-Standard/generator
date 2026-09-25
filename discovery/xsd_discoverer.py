"""Mechanically discovers citable candidates in one real XSD file: every
named XML Schema construct (elements, complexTypes, simpleTypes,
attributes, groups, attributeGroups -- anything with a `name` attribute
in the XML Schema namespace), with no judgment about which ones are
"worth" citing. See docs/specs/2026-09-25-xsd-discovery-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

_XS_NS = "http://www.w3.org/2001/XMLSchema"


@dataclass(frozen=True)
class Candidate:
    tag: str
    name: str
    xpath: str


@dataclass(frozen=True)
class ExcludedCandidate:
    """`match_count` is the raw number of nodes the computed `xpath`
    evaluated to: 0 means the path didn't resolve at all (including a
    path that failed to even parse as valid XPath, e.g. an unescaped
    quote in a `name`, or one that resolved to zero or to the wrong node
    entirely due to a non-XSD-namespace ancestor along the way); 2+ means
    a genuine ambiguity (multiple real nodes share the same computed
    path). Both are folded into this one type rather than a raw exception
    or a silently-dropped candidate, per this module's own "recorded,
    never silently wrong" rule -- not because they're the same failure.
    """

    tag: str
    name: str
    xpath: str
    match_count: int


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[Candidate, ...]
    excluded: tuple[ExcludedCandidate, ...]


def _is_named_xsd_construct(node) -> bool:
    return (
        isinstance(node.tag, str)
        and node.tag.startswith(f"{{{_XS_NS}}}")
        and node.get("name") is not None
    )


def _path_step(node) -> str:
    qname = etree.QName(node)
    tag = f"xs:{qname.localname}" if qname.namespace == _XS_NS else qname.localname
    name = node.get("name")
    return f"{tag}[@name='{name}']" if name else tag


def _compute_xpath(node) -> str:
    steps = []
    current = node
    while current is not None:
        steps.append(_path_step(current))
        current = current.getparent()
    return "/" + "/".join(reversed(steps))


def discover_candidates(xsd_path: str) -> DiscoveryResult:
    tree = etree.parse(xsd_path)
    candidates = []
    excluded = []
    for node in tree.iter():
        if not _is_named_xsd_construct(node):
            continue
        xpath = _compute_xpath(node)
        tag = etree.QName(node).localname
        name = node.get("name")
        try:
            matches = tree.xpath(xpath, namespaces={"xs": _XS_NS})
        except etree.XPathEvalError:
            # An unescaped quote in `name` (never valid per XSD's own
            # NCName rule, but this module doesn't validate that) breaks
            # the generated predicate's own quoting -- record it as
            # unresolvable rather than letting the whole file's discovery
            # crash on one malformed name.
            excluded.append(ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=0))
            continue
        if len(matches) == 1 and matches[0] is node:
            candidates.append(Candidate(tag=tag, name=name, xpath=xpath))
        else:
            excluded.append(
                ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=len(matches))
            )
    return DiscoveryResult(candidates=tuple(candidates), excluded=tuple(excluded))
