"""A single, shared lxml XMLParser configuration for every XSD parse in
this system. lxml's default parser has `resolve_entities=True` and no
network/DTD restrictions -- fine for a document you trust, but this
system's entire input domain is externally authored regulatory XML
(fetched from BZSt), which a corrupted or malicious source could turn
into an XXE (XML External Entity) attack: a `<!ENTITY xxe SYSTEM
"file:///...">` declaration expanded into a cited value that then flows
through canonicalization, hashing, and the catalog into a browser via
GET /api/review's CONTENT-drift path, or a `SYSTEM "http://..."` DTD
reference turning every parse into an outbound network request. See the
2026-09-29 audit finding on this exact gap.
"""
from __future__ import annotations

from lxml import etree

SAFE_XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)
