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
    """`retrieval_uri` (passed to resolve(), not stored here) works as
    either a local filesystem path or a `file://`/`http://` URL -- lxml's
    own `etree.parse()` accepts both. This is inconsistent with
    SvgSelector, whose pdfplumber-backed resolve() only accepts a local
    path; each selector documents its own retrieval_uri contract rather
    than a shared one, since a general fetch abstraction isn't something
    either selector's real, current use needs yet.
    """

    type: str
    value: str

    @staticmethod
    def create(value: str) -> "XPathSelector":
        return XPathSelector(type="XPathSelector", value=value)


def resolve(selector: XPathSelector, retrieval_uri: str) -> ResolutionOutcome:
    try:
        tree = etree.parse(retrieval_uri)
    except OSError:
        # Missing/unreadable file -- the source is gone, same bucket as
        # "selector no longer matches anything" from the caller's view.
        return ResolutionOutcome(status=Status.NOT_FOUND)
    except etree.XMLSyntaxError:
        # Corrupt/unparsable XML -- also nothing to resolve against.
        return ResolutionOutcome(status=Status.NOT_FOUND)

    try:
        matches = tree.xpath(selector.value, namespaces=_NSMAP)
    except etree.XPathEvalError:
        return ResolutionOutcome(status=Status.UNCITABLE)

    if not isinstance(matches, list):
        # tree.xpath() only returns a node list for node-set expressions --
        # string()/count()/boolean() etc. return a str/float/bool instead,
        # and len() on those measures characters, not matches (a real bug:
        # it previously misreported string(...) results as AMBIGUOUS based
        # on string length). None of these are element-addressable the way
        # this selector type promises, regardless of their length/value.
        return ResolutionOutcome(status=Status.UNCITABLE)

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
    # The design spec says "Canonical XML 1.1"; lxml only offers 1.0
    # (method="c14n") or 2.0 (method="c14n2"), never 1.1 -- the spec's
    # wording isn't literally implementable, and 1.0 is what's used here.
    #
    # This is inclusive C14N (the lxml default), not exclusive: every
    # in-scope ancestor namespace declaration gets folded into the
    # canonicalized subtree, so an unrelated xmlns added anywhere on an
    # ancestor (even the document root) changes every descendant element's
    # hash. That's the safer failure mode for this project's purposes
    # (never silently miss a change) so it's kept deliberately, not
    # switched to exclusive C14N -- exclusive would drop the very
    # namespace declarations these real MiKaDiv-FM schemas actually need:
    # QName-valued attributes like `type="std:UUIDType"` reference a
    # prefix from *inside* an attribute value, which exclusive C14N's
    # visibly-used-in-the-subtree analysis cannot see and would prune.
    canonical_bytes = etree.tostring(raw_content, method="c14n")
    return hashlib.sha256(canonical_bytes).hexdigest()


register("XPathSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
