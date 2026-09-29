"""A single, shared lxml XMLParser configuration for every XSD parse in
this system. This system's entire input domain is externally authored
regulatory XML (fetched from BZSt), which a corrupted or malicious
source could turn into an XXE (XML External Entity) attack: a `<!ENTITY
xxe SYSTEM "file:///...">` declaration expanded into a cited value that
then flows through canonicalization, hashing, and the catalog into a
browser via GET /api/review's CONTENT-drift path, or a `SYSTEM
"http://..."` DTD reference turning every parse into an outbound network
request. See the 2026-09-29 audit finding on this exact gap.

Deliberately does NOT set `resolve_entities=False`. That was this
module's own first attempt, live-verified at the time to block the
external-entity attack above -- but a whole-branch review caught two
real regressions it introduced (confirmed live, see
tests/reference_model/test_xpath_selector.py's own regression tests for
both): (1) an unresolved entity-reference node dropped out of the
canonical form entirely, so two documents differing only in an
internal entity's value hashed identically -- this system's entire
purpose (detecting a real content change) silently defeated for any
legitimate document using an internal entity; (2) `canonicalize_and_hash()`
calls `etree.tostring(..., method="c14n")`, which cannot serialize an
unresolved entity-reference node at all, so parsing such a document
raised an uncaught `C14NError` instead of a handled `CitationError`/
`Status.NOT_FOUND`. `no_network`/`load_dtd=False` alone already block
the real external-entity attack (confirmed live: a `SYSTEM` entity
still fails with "Entity ... not defined" during parsing, the same as
lxml's own bare default) without touching entity resolution at all, so
internal entities keep expanding correctly and drift detection keeps
working for real documents that use them.
"""
from __future__ import annotations

from lxml import etree

SAFE_XML_PARSER = etree.XMLParser(
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)
