import shutil
from pathlib import Path

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from staleness_sweep.sweep import FamilyResolutionFailure, sweep

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
REAL_MELDEART23_XSD = f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _real_meldeart23_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_MELDEART23_XSD)


def test_sweep_reports_a_real_reference_as_unchanged():
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    assert report.family_resolution_failures == ()
    assert report.results_by_key["fact-1"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["fact-1"][0].hash_changed is False


def test_sweep_reports_an_unresolvable_family_as_a_failure_not_a_leaf_result():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )
    assert "fact-1" not in report.results_by_key


def test_sweep_with_no_references_returns_an_empty_report():
    report = sweep({}, REAL_MODULE_ROOT)
    assert report.results_by_key == {}
    assert report.family_resolution_failures == ()


def test_sweep_uses_the_resolved_current_path_not_a_leaf_own_stale_stored_uri(tmp_path):
    stale_copy = tmp_path / "stale-copy.xsd"
    original = Path(REAL_MELDEART23_XSD).read_text(encoding="utf-8")
    # Mutate the very element this leaf cites, in the stale copy only --
    # citing against the stale copy captures the MUTATED content as the
    # leaf's stored hash.
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    assert mutated != original  # confirms the replace actually matched something real
    stale_copy.write_text(mutated, encoding="utf-8")

    stale_subject_document = SubjectDocument(
        family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=str(stale_copy)
    )
    leaf = cite(stale_subject_document, XPathSelector.create(ABGEF_XPATH))

    report = sweep({"fact": leaf}, REAL_MODULE_ROOT)

    # The leaf's own stored retrieval_uri (stale_copy) still has the
    # mutation baked into its stored hash, so falling back to checking
    # THAT path again would report unchanged. The real current file was
    # never mutated, so if sweep() correctly used the resolved current
    # path instead, the content reverts relative to what was stored and
    # this must report a real change -- the only way to tell which path
    # sweep() actually used.
    assert report.results_by_key["fact"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["fact"][0].hash_changed is True


def test_union_with_one_unresolvable_family_is_fully_excluded_from_results():
    good_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    bad_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    bad_leaf = cite(bad_subject_document, XPathSelector.create(ABGEF_XPATH))
    union = cite_union([good_leaf, bad_leaf])

    report = sweep({"fact": union}, REAL_MODULE_ROOT)

    assert "fact" not in report.results_by_key
    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )


def test_sweep_over_a_deliberately_changed_synthetic_snapshot(tmp_path):
    # The spec's own Definition of Done scenario: cite a real fact, then
    # sweep against a tmp_path copy of the corpus with one deliberate
    # change on a second, synthetic snapshot -- never the real repo.
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)

    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')

    new_snapshot = module_root / "1.03"
    shutil.copytree(module_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (module_root / "_current").write_text("1.03")

    changed_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    unchanged_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))

    report = sweep({"changed-fact": changed_leaf, "unchanged-fact": unchanged_leaf}, str(module_root))

    assert report.family_resolution_failures == ()
    assert report.results_by_key["changed-fact"][0].outcome.status == Status.NOT_FOUND
    assert report.results_by_key["unchanged-fact"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["unchanged-fact"][0].hash_changed is False
