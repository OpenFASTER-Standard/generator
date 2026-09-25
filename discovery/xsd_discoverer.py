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
        matches = tree.xpath(xpath, namespaces={"xs": _XS_NS})
        tag = etree.QName(node).localname
        name = node.get("name")
        if len(matches) == 1:
            candidates.append(Candidate(tag=tag, name=name, xpath=xpath))
        else:
            excluded.append(
                ExcludedCandidate(tag=tag, name=name, xpath=xpath, match_count=len(matches))
            )
    return DiscoveryResult(candidates=tuple(candidates), excluded=tuple(excluded))
