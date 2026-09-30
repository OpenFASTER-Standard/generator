from pathlib import Path

from annotation_model.outcomes import Status
from annotation_model.selectors.xpath import canonicalize_and_hash_xml, resolve_xpath
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)


@requires_real_corpus
def test_resolves_real_element_and_hash_is_reproducible():
    outcome_1 = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    assert outcome_1.status == Status.RESOLVED
    digest_1 = canonicalize_and_hash_xml(outcome_1.raw_content)

    outcome_2 = resolve_xpath(REAL_XSD, AORDNR_XPATH)
    digest_2 = canonicalize_and_hash_xml(outcome_2.raw_content)

    assert digest_1 == digest_2
    assert len(digest_1) == 64


@requires_real_corpus
def test_rename_makes_selector_not_found(tmp_path: Path):
    original = Path(REAL_XSD).read_text(encoding="utf-8")
    assert original.count('name="AOrdNr"') == 1
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    mutated_path = tmp_path / "mutated.xsd"
    mutated_path.write_text(mutated, encoding="utf-8")

    outcome = resolve_xpath(str(mutated_path), AORDNR_XPATH)
    assert outcome.status == Status.NOT_FOUND


def test_missing_source_file_is_not_found():
    outcome = resolve_xpath("/nonexistent/path/does-not-exist.xsd", AORDNR_XPATH)
    assert outcome.status == Status.NOT_FOUND


@requires_real_corpus
def test_xpath_matching_multiple_real_elements_is_ambiguous():
    outcome = resolve_xpath(REAL_XSD, "//xs:element")
    assert outcome.status == Status.AMBIGUOUS


@requires_real_corpus
def test_xpath_resolving_to_an_attribute_is_uncitable():
    outcome = resolve_xpath(REAL_XSD, AORDNR_XPATH + "/@name")
    assert outcome.status == Status.UNCITABLE


def test_an_external_entity_never_reaches_a_resolved_outcome(tmp_path: Path):
    secret = tmp_path / "secret.txt"
    secret.write_text("super-secret-file-content", encoding="utf-8")
    malicious = tmp_path / "malicious.xsd"
    malicious.write_text(
        f"""<?xml version="1.0"?>
<!DOCTYPE xs:schema [
  <!ENTITY xxe SYSTEM "file://{secret}">
]>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="AOrdNr">
    <xs:annotation><xs:documentation>&xxe;</xs:documentation></xs:annotation>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )
    outcome = resolve_xpath(
        str(malicious), "/xs:schema/xs:element[@name='AOrdNr']/xs:annotation/xs:documentation"
    )
    assert outcome.status == Status.NOT_FOUND
