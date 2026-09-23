"""XPathSelector: addresses one XML element inside an XSD by an XPath
expression evaluated against the schema's own document tree.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from lxml import etree

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register

_NSMAP = {"xs": "http://www.w3.org/2001/XMLSchema"}


@dataclass(frozen=True)
class XPathSelector:
    type: str
    value: str

    @staticmethod
    def create(value: str) -> "XPathSelector":
        return XPathSelector(type="XPathSelector", value=value)


def resolve(selector: XPathSelector, retrieval_uri: str) -> ResolutionOutcome:
    tree = etree.parse(retrieval_uri)
    matches = tree.xpath(selector.value, namespaces=_NSMAP)

    if len(matches) == 0:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    if len(matches) > 1:
        return ResolutionOutcome(status=Status.AMBIGUOUS)

    match = matches[0]
    if not isinstance(match, etree._Element):
        # e.g. an XPath ending in @attr or text() -- not element-rooted,
        # so it can't be canonicalized the way this selector type promises.
        return ResolutionOutcome(status=Status.UNCITABLE)
    return ResolutionOutcome(status=Status.RESOLVED, raw_content=match)


def canonicalize_and_hash(raw_content: "etree._Element") -> str:
    canonical_bytes = etree.tostring(raw_content, method="c14n")
    return hashlib.sha256(canonical_bytes).hexdigest()


register("XPathSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
