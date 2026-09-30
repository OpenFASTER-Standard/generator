from pathlib import Path

from lxml import etree

from annotation_model.xml_safety import SAFE_XML_PARSER


def test_external_entity_is_blocked(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("super-secret-file-content", encoding="utf-8")
    malicious = tmp_path / "malicious.xml"
    malicious.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file://{secret}">
]>
<root>&xxe;</root>
""",
        encoding="utf-8",
    )
    import pytest

    with pytest.raises(etree.XMLSyntaxError):
        etree.parse(str(malicious), parser=SAFE_XML_PARSER)


def test_internal_entity_still_expands_and_changes_the_hash(tmp_path: Path):
    def _doc(value: str) -> Path:
        path = tmp_path / f"doc-{value}.xml"
        path.write_text(
            f"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY val "{value}">
]>
<root>&val;</root>
""",
            encoding="utf-8",
        )
        return path

    tree_a = etree.parse(str(_doc("alpha")), parser=SAFE_XML_PARSER)
    tree_b = etree.parse(str(_doc("beta")), parser=SAFE_XML_PARSER)
    bytes_a = etree.tostring(tree_a.getroot(), method="c14n")
    bytes_b = etree.tostring(tree_b.getroot(), method="c14n")

    assert b"alpha" in bytes_a
    assert b"beta" in bytes_b
    assert bytes_a != bytes_b
