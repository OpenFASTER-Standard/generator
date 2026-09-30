from lxml import etree

SAFE_XML_PARSER = etree.XMLParser(
    no_network=True,
    load_dtd=False,
    huge_tree=False,
)
