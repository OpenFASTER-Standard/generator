"""Resolves an XPath expression against a real XML/XSD source."""
from __future__ import annotations

import hashlib

from lxml import etree

from annotation_model.outcomes import ResolutionOutcome, Status
from annotation_model.xml_safety import SAFE_XML_PARSER

_NSMAP = {"xs": "http://www.w3.org/2001/XMLSchema"}


def resolve_xpath(retrieval_uri: str, xpath: str) -> ResolutionOutcome:
    try:
        tree = etree.parse(retrieval_uri, parser=SAFE_XML_PARSER)
    except OSError:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    except etree.XMLSyntaxError:
        return ResolutionOutcome(status=Status.NOT_FOUND)

    try:
        matches = tree.xpath(xpath, namespaces=_NSMAP)
    except etree.XPathEvalError:
        return ResolutionOutcome(status=Status.UNCITABLE)

    if not isinstance(matches, list):
        # tree.xpath() only returns a node list for node-set expressions --
        # string()/count()/boolean() etc. return a str/float/bool instead,
        # none of which are element-addressable the way this function
        # promises, regardless of length/value.
        return ResolutionOutcome(status=Status.UNCITABLE)

    if len(matches) == 0:
        return ResolutionOutcome(status=Status.NOT_FOUND)
    if len(matches) > 1:
        return ResolutionOutcome(status=Status.AMBIGUOUS)

    match = matches[0]
    if not isinstance(match, etree._Element):
        # e.g. an XPath ending in @attr or text() -- not element-rooted,
        # so it can't be canonicalized the way this function promises.
        return ResolutionOutcome(status=Status.UNCITABLE)
    return ResolutionOutcome(status=Status.RESOLVED, raw_content=match)


def canonicalize_and_hash_xml(element: "etree._Element") -> str:
    # Inclusive C14N (lxml's default), not exclusive -- see
    # reference_model/selectors/xpath_selector.py's own docstring for the
    # full reasoning (an unrelated xmlns on an ancestor changing every
    # descendant's hash is the safer failure mode for this project's
    # purposes than silently missing a real change).
    canonical_bytes = etree.tostring(element, method="c14n")
    return hashlib.sha256(canonical_bytes).hexdigest()
