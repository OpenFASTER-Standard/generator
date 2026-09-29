from pathlib import Path

import pytest

from reference_model.model import Status
from reference_model.registry import get_resolver
from reference_model.selectors.xpath_selector import XPathSelector

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


def _resolver():
    return get_resolver("XPathSelector")


def test_resolves_real_element_and_hash_is_reproducible():
    selector = XPathSelector.create(AORDNR_XPATH)
    resolver = _resolver()

    outcome_1 = resolver.resolve(selector, REAL_XSD)
    assert outcome_1.status == Status.RESOLVED
    digest_1 = resolver.canonicalize_and_hash(outcome_1.raw_content)

    outcome_2 = resolver.resolve(selector, REAL_XSD)
    digest_2 = resolver.canonicalize_and_hash(outcome_2.raw_content)

    assert digest_1 == digest_2
    assert len(digest_1) == 64  # sha256 hex digest


def test_rename_makes_selector_not_found(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1  # confirmed unique in the real file
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')

    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    selector = XPathSelector.create(AORDNR_XPATH)
    outcome = _resolver().resolve(selector, str(mutated_path))
    assert outcome.status == Status.NOT_FOUND


def test_content_change_without_rename_changes_hash_but_still_resolves(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('maxOccurs="3000"') == 1  # confirmed unique in the real file
    mutated = original.replace('maxOccurs="3000"', 'maxOccurs="5000"')

    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    selector = XPathSelector.create(AORDNR_XPATH)
    resolver = _resolver()

    original_outcome = resolver.resolve(selector, REAL_XSD)
    original_digest = resolver.canonicalize_and_hash(original_outcome.raw_content)

    mutated_outcome = resolver.resolve(selector, str(mutated_path))
    assert mutated_outcome.status == Status.RESOLVED
    mutated_digest = resolver.canonicalize_and_hash(mutated_outcome.raw_content)

    assert mutated_digest != original_digest


def test_xpath_matching_nothing_is_not_found():
    selector = XPathSelector.create("/xs:schema/xs:complexType[@name='NoSuchType']")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.NOT_FOUND


def test_xpath_matching_multiple_real_elements_is_ambiguous():
    # The real file has 3 xs:element nodes (AbgefKapitalertragsteuer,
    # AmtlicheOrdnungsnummerListe, AOrdNr).
    selector = XPathSelector.create("//xs:element")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.AMBIGUOUS


def test_xpath_resolving_to_an_attribute_is_uncitable():
    selector = XPathSelector.create(AORDNR_XPATH + "/@name")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.UNCITABLE


def test_missing_source_file_is_not_found():
    selector = XPathSelector.create(AORDNR_XPATH)
    outcome = _resolver().resolve(selector, "/nonexistent/path/does-not-exist.xsd")
    assert outcome.status == Status.NOT_FOUND


def test_malformed_xml_is_not_found(tmp_path: Path):
    malformed_path = tmp_path / "malformed.xsd"
    malformed_path.write_text("<xs:schema><unclosed>", encoding="utf-8")

    selector = XPathSelector.create(AORDNR_XPATH)
    outcome = _resolver().resolve(selector, str(malformed_path))
    assert outcome.status == Status.NOT_FOUND


def test_xpath_returning_a_string_is_uncitable_not_ambiguous():
    # tree.xpath() returns a str (not a node list) for string(...) --
    # len() on that string previously miscounted characters as matches.
    selector = XPathSelector.create("string(/xs:schema/@targetNamespace)")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.UNCITABLE


def test_xpath_count_function_is_uncitable():
    selector = XPathSelector.create("count(//xs:element)")
    outcome = _resolver().resolve(selector, REAL_XSD)
    assert outcome.status == Status.UNCITABLE


def test_an_external_entity_declaration_is_not_expanded_into_cited_content(tmp_path: Path):
    # This system's entire input domain is externally authored regulatory
    # XML (fetched from BZSt); a malicious/tampered XSD declaring a
    # SYSTEM external entity must never have that entity's content reach a
    # citation -- it would flow through canonicalization/hashing into the
    # catalog and, via GET /api/review's CONTENT-drift path, into a
    # browser. See the 2026-09-29 audit finding on this exact gap.
    secret_path = tmp_path / "secret.txt"
    secret_path.write_text("super-secret-file-content", encoding="utf-8")
    malicious_xsd = tmp_path / "malicious.xsd"
    malicious_xsd.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE xs:schema [
  <!ENTITY xxe SYSTEM "file://{secret_path}">
]>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="AOrdNr">
    <xs:annotation><xs:documentation>&xxe;</xs:documentation></xs:annotation>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )

    selector = XPathSelector.create("/xs:schema/xs:element[@name='AOrdNr']/xs:annotation/xs:documentation")
    outcome = _resolver().resolve(selector, str(malicious_xsd))

    if outcome.status == Status.RESOLVED:
        from lxml import etree

        # Not method="c14n" -- an unresolved entity reference node (exactly
        # what SAFE_XML_PARSER's resolve_entities=False leaves behind) is
        # not something C14N knows how to serialize at all (C14NError),
        # which is an orthogonal libxml2 limitation, not a leak. Plain
        # tostring() is the real assertion: the entity reference is
        # preserved literally as "&xxe;" text, never expanded.
        rendered = etree.tostring(outcome.raw_content).decode()
        assert "super-secret-file-content" not in rendered
    # NOT_FOUND (the entity reference left unresolved breaks the document)
    # is an equally acceptable safe outcome -- either way, the secret must
    # never appear anywhere reachable.
