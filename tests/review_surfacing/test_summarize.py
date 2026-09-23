import shutil

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from review_surfacing.summarize import DriftKind, summarize_for_review
from staleness_sweep.sweep import sweep

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
# A real element that is a SIBLING of xs:complexContent (which holds
# AbgefKapitalertragsteuer), not an ancestor or descendant of it -- so
# mutating ABGEF never changes this element's own canonical bytes. Real
# text, verified live: "Meldung nach § 45c Absatz 2 Satz 3 EStG."
MELDEART_DOC_XPATH = "/xs:schema/xs:complexType[@name='Meldeart23']/xs:annotation/xs:documentation"


def _real_meldeart23_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_MELDEART23_XSD)


def _make_content_and_structural_snapshot(module_root):
    """Copies the real corpus into module_root, then creates a synthetic
    1.03 snapshot that content-drifts ABGEF and structurally breaks AOrdNr,
    leaving MELDEART_DOC_XPATH's own target untouched. Points _current at
    1.03. Never touches the real /work/ontologies repo."""
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    assert mutated != original

    new_snapshot = module_root / "1.03"
    shutil.copytree(module_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (module_root / "_current").write_text("1.03")


def test_healthy_report_produces_an_entirely_empty_summary():
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    summary = summarize_for_review(report)

    assert summary.flagged == {}
    assert summary.unresolved_families == ()
    assert summary.excluded_keys == ()


def test_empty_sweep_report_produces_an_empty_summary():
    report = sweep({}, REAL_MODULE_ROOT)
    summary = summarize_for_review(report)

    assert summary.flagged == {}
    assert summary.unresolved_families == ()
    assert summary.excluded_keys == ()


def test_content_drift_is_classified_as_content(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))

    summary = summarize_for_review(report)

    assert list(summary.flagged.keys()) == ["fact-1"]
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.drift_kind == DriftKind.CONTENT
    assert flagged_leaf.outcome.status == Status.RESOLVED
    assert flagged_leaf.leaf == leaf


def test_structural_drift_is_classified_as_structural(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))

    summary = summarize_for_review(report)

    assert list(summary.flagged.keys()) == ["fact-1"]
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL
    assert flagged_leaf.outcome.status == Status.NOT_FOUND
    assert flagged_leaf.leaf == leaf


def test_union_mixing_healthy_content_and_structural_leaves(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)

    healthy_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(MELDEART_DOC_XPATH))
    content_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    structural_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([healthy_leaf, content_leaf, structural_leaf])

    report = sweep({"fact-1": union}, str(module_root))
    summary = summarize_for_review(report)

    flagged_by_kind = {fl.drift_kind: fl for fl in summary.flagged["fact-1"]}
    assert len(summary.flagged["fact-1"]) == 2
    assert flagged_by_kind[DriftKind.CONTENT].leaf == content_leaf
    assert flagged_by_kind[DriftKind.STRUCTURAL].leaf == structural_leaf
    assert all(fl.leaf != healthy_leaf for fl in summary.flagged["fact-1"])


def test_unresolved_families_and_excluded_keys_pass_through_verbatim():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)

    summary = summarize_for_review(report)

    assert summary.unresolved_families == report.family_resolution_failures
    assert summary.excluded_keys == report.excluded_keys
    assert summary.excluded_keys == ("fact-1",)
