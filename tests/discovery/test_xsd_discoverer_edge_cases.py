from discovery.xsd_discoverer import discover_candidates


def test_ambiguous_synthetic_candidates_are_excluded_with_correct_match_count(tmp_path):
    xsd_path = tmp_path / "ambiguous.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="Ambiguous">
    <xs:choice>
      <xs:sequence>
        <xs:element name="Same" type="xs:string"/>
      </xs:sequence>
      <xs:sequence>
        <xs:element name="Same" type="xs:string"/>
      </xs:sequence>
    </xs:choice>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    same_excluded = [e for e in result.excluded if e.name == "Same"]
    assert len(same_excluded) == 2
    for excluded in same_excluded:
        assert excluded.match_count == 2
        assert excluded.tag == "element"
    assert not any(c.name == "Same" for c in result.candidates)
    assert any(c.name == "Ambiguous" for c in result.candidates)


def test_computed_xpath_always_uses_xs_prefix_regardless_of_source_document_prefix(tmp_path):
    xsd_path = tmp_path / "xsd_prefix.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <xsd:element name="Foo" type="xsd:string"/>
</xsd:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    (candidate,) = result.candidates
    assert candidate.xpath == "/xs:schema/xs:element[@name='Foo']"


def test_ref_based_element_usage_has_no_name_and_is_not_a_candidate(tmp_path):
    xsd_path = tmp_path / "ref_usage.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="RealElement" type="xs:string"/>
  <xs:complexType name="Wrapper">
    <xs:sequence>
      <xs:element ref="RealElement"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    names = {c.name for c in result.candidates}
    assert names == {"RealElement", "Wrapper"}
    assert result.excluded == ()


def test_same_name_different_tag_candidates_are_not_conflated(tmp_path):
    xsd_path = tmp_path / "shared_name.xsd"
    xsd_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="Shared">
    <xs:sequence>
      <xs:element name="Shared" type="xs:string"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>
""",
        encoding="utf-8",
    )

    result = discover_candidates(str(xsd_path))

    assert result.excluded == ()
    by_tag = {(c.tag, c.name): c.xpath for c in result.candidates}
    assert by_tag[("complexType", "Shared")] == "/xs:schema/xs:complexType[@name='Shared']"
    assert by_tag[("element", "Shared")] == (
        "/xs:schema/xs:complexType[@name='Shared']/xs:sequence/xs:element[@name='Shared']"
    )
