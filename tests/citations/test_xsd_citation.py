import os

import xmlschema

from citations.xsd_citation import capture_xsd_fragment

ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"


def test_capture_xsd_fragment_returns_the_exact_real_source_fragment_and_file():
    schema = xmlschema.XMLSchema(ROOT_XSD)
    type_name = "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType"
    component = schema.maps.types[type_name]

    citation = capture_xsd_fragment(component)

    assert "MeldepflichtigeStelleType" in citation.fragment
    assert citation.fragment.strip().startswith("<xs:complexType")
    assert citation.source_file.endswith("MiKaDiv_FM_Personentypen_1.02.xsd")
    # source_file must be a real, openable filesystem path -- not a raw
    # file://... URL -- so Plan C's design can use it directly with open().
    assert not citation.source_file.startswith("file://")
    assert os.path.exists(citation.source_file)
