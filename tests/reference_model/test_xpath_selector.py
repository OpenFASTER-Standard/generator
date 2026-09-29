from pathlib import Path

import pytest

from reference_model.model import Status, SubjectDocument
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


def test_an_external_entity_declaration_never_reaches_a_real_citation(tmp_path: Path):
    # This system's entire input domain is externally authored regulatory
    # XML (fetched from BZSt); a malicious/tampered XSD declaring a SYSTEM
    # external entity must never have that entity's content reach a
    # citation -- it would flow through canonicalization/hashing into the
    # catalog and, via GET /api/review's CONTENT-drift path, into a
    # browser. See the 2026-09-29 audit finding on this exact gap.
    #
    # Goes through the real cite() -> canonicalize_and_hash() path (not a
    # hand-rolled etree.tostring() call that sidesteps it) -- a prior
    # version of this test used method="c14n" directly and hit a real
    # C14NError on the then-current resolve_entities=False hardening,
    # dismissed in a comment as "an orthogonal libxml2 limitation" instead
    # of being recognized as proof the hardening broke the production
    # code path. That hardening also silently broke drift detection for
    # any legitimate document using an internal entity (a real, different
    # bug caught in a whole-branch review) -- SAFE_XML_PARSER no longer
    # sets resolve_entities=False at all; the external-entity block below
    # comes from no_network/load_dtd, which this test still exercises for
    # real.
    from reference_model.cite import CitationError, cite

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
    subject_document = SubjectDocument(
        family="TestFamily", version="1", retrieval_uri=str(malicious_xsd)
    )
    selector = XPathSelector.create("/xs:schema/xs:element[@name='AOrdNr']/xs:annotation/xs:documentation")

    # The external entity breaks parsing outright (blocked, not expanded),
    # so citation fails safely rather than succeeding with leaked content.
    with pytest.raises(CitationError):
        cite(subject_document, selector)


def test_an_internal_entity_in_source_content_is_expanded_and_drift_is_still_detected(tmp_path: Path):
    # The regression this test guards against: hardening against XXE by
    # blanket-disabling entity resolution (resolve_entities=False) also
    # silently defeated this system's entire purpose for any legitimate
    # document using an internal (non-external) entity -- two different
    # documents whose only difference is an internal entity's value
    # canonicalized to the SAME hash, since the unexpanded entity
    # reference node dropped out of the canonical form entirely. Confirmed
    # live in a whole-branch review before this test was written.
    from reference_model.cite import check_leaf, cite

    def _xsd(entity_value: str) -> Path:
        path = tmp_path / f"doc-{entity_value}.xsd"
        path.write_text(
            f"""<?xml version="1.0"?>
<!DOCTYPE xs:schema [
  <!ENTITY typeval "{entity_value}">
]>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Foo" type="&typeval;"/>
</xs:schema>
""",
            encoding="utf-8",
        )
        return path

    subject_document = SubjectDocument(
        family="TestFamily", version="1", retrieval_uri=str(_xsd("xs:string"))
    )
    selector = XPathSelector.create("/xs:schema/xs:element[@name='Foo']")
    leaf = cite(subject_document, selector)

    # The entity's real value reached the citation -- proves it was
    # genuinely expanded, not silently dropped.
    outcome = _resolver().resolve(selector, str(_xsd("xs:string")))
    assert outcome.raw_content.get("type") == "xs:string"

    # Now the source changes (only the entity's value differs) -- a real
    # content change must be detected as drift, not hashed identically.
    result = check_leaf(leaf, retrieval_uri=str(_xsd("xs:integer")))
    assert result.hash_changed is True
