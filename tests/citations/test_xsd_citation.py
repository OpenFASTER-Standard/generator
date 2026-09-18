import os

import xmlschema

from citations.xsd_citation import capture_xsd_fragment, resolve_xsd_component

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


def test_resolve_xsd_component_finds_a_real_global_type():
    schema = xmlschema.XMLSchema(ROOT_XSD)
    component = resolve_xsd_component(
        schema, "{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType"
    )
    assert component is schema.maps.types["{http://www.itzbund.de/MiKaDiv/FMPers/1.02}MeldepflichtigeStelleType"]


def test_resolve_xsd_component_finds_a_real_global_element():
    # Real, confirmed bug this function fixes: the pre-existing dict-only
    # lookups used by webapp/routes_provenance.py checked schema.maps.types
    # only, so this corpus's one real global element (MiKaDivFMRoot) was
    # unresolvable there even though it was never locally-scoped.
    schema = xmlschema.XMLSchema(ROOT_XSD)
    component = resolve_xsd_component(schema, "{http://www.itzbund.de/MiKaDiv/FM/1.02}MiKaDivFMRoot")
    assert component is schema.maps.elements["{http://www.itzbund.de/MiKaDiv/FM/1.02}MiKaDivFMRoot"]


def test_resolve_xsd_component_finds_a_real_locally_scoped_element():
    # Real, confirmed regression anchor: AOrdNr is a local xs:element
    # declaration nested inside AmtlicheOrdnungsnummerMa23ListeType (a
    # real global complex type) -- not itself globally named, so it
    # cannot appear in schema.maps.types/elements directly.
    schema = xmlschema.XMLSchema(ROOT_XSD)
    component = resolve_xsd_component(
        schema,
        "{http://www.itzbund.de/MiKaDiv/FMMa23/1.02}AmtlicheOrdnungsnummerMa23ListeType.AOrdNr",
    )
    assert component is not None
    assert component.local_name == "AOrdNr"
    citation = capture_xsd_fragment(component)
    assert 'name="AOrdNr"' in citation.fragment
    assert "Amtliche Ordnungsnummer" in citation.fragment


def test_resolve_xsd_component_finds_a_real_locally_scoped_attribute():
    # This corpus has 149 real xs:attribute declarations and zero global
    # ones (see extraction/uris.py's own docstring) -- every one is
    # reached the same "@name" way as this real, known example
    # (NachrichtenType's own NachrichtUUID attribute).
    qname = "{http://www.itzbund.de/MiKaDiv/FMStd/1.02}NachrichtenType.@NachrichtUUID"
    schema = xmlschema.XMLSchema(ROOT_XSD)

    component = resolve_xsd_component(schema, qname)

    assert component is not None
    assert component.local_name == "NachrichtUUID"


def test_resolve_xsd_component_returns_none_for_an_unknown_global_qname():
    schema = xmlschema.XMLSchema(ROOT_XSD)
    assert resolve_xsd_component(schema, "{urn:nope}Nope") is None


def test_resolve_xsd_component_returns_none_for_an_unresolvable_local_segment():
    schema = xmlschema.XMLSchema(ROOT_XSD)
    assert resolve_xsd_component(
        schema,
        "{http://www.itzbund.de/MiKaDiv/FMMa23/1.02}AmtlicheOrdnungsnummerMa23ListeType.NotARealChild",
    ) is None
