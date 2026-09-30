from lxml import etree

_SAFE_XML_PARSER_KWARGS = dict(
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)

# Kept for simple/single-threaded use (e.g. this module's own tests) --
# real parsing call sites should use get_safe_xml_parser() instead, since
# an lxml XMLParser instance carries state during a parse call and is not
# safe to share across threads.
SAFE_XML_PARSER = etree.XMLParser(**_SAFE_XML_PARSER_KWARGS)


def get_safe_xml_parser() -> etree.XMLParser:
    """A fresh, safely-configured parser instance. Construction is cheap
    (it's not parsing anything yet), so a fresh instance per call is the
    default that's safe under concurrent use without relying on every
    caller remembering not to share one."""
    return etree.XMLParser(**_SAFE_XML_PARSER_KWARGS)
