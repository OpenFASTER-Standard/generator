import shutil

from reference_model.cite import LeafCheckResult, cite, cite_union
from reference_model.model import ResolutionOutcome, SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from review_surfacing.summarize import DriftKind, summarize_for_review
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
    # Identity, not just .status -- the whole ResolutionOutcome (including
    # raw_content) must be the exact object that came from the SweepReport,
    # not a copy that dropped information.
    assert flagged_leaf.outcome is report.results_by_key["fact-1"][0].outcome


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
    # Pinned to real, non-empty values -- a regression that emptied both
    # sides of the pass-through would otherwise slip past the equality
    # check above, which is satisfied just as well by two empty tuples.
    assert summary.unresolved_families == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )
    assert summary.excluded_keys == ("fact-1",)


def test_ambiguous_drift_is_also_classified_as_structural(tmp_path):
    # A real mutation, not a synthetic status: duplicating the whole
    # AmtlicheOrdnungsnummerMa23ListeType complexType block makes AORDNR_XPATH
    # match two real elements instead of one -- a genuine AMBIGUOUS outcome,
    # not a hand-constructed one.
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)

    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    block_start = original.index('<xs:complexType name="AmtlicheOrdnungsnummerMa23ListeType">')
    block_end = original.index("</xs:complexType>", block_start) + len("</xs:complexType>")
    duplicated_block = original[block_start:block_end]
    mutated = original[:block_end] + duplicated_block + original[block_end:]
    assert mutated != original

    new_snapshot = module_root / "1.03"
    shutil.copytree(module_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (module_root / "_current").write_text("1.03")

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))

    summary = summarize_for_review(report)

    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.outcome.status == Status.AMBIGUOUS
    assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL


def test_uncitable_drift_is_also_classified_as_structural():
    # UNCITABLE cannot actually occur in a real LeafCheckResult produced by
    # this system: cite() rejects any selector that doesn't resolve to a
    # clean single RESOLVED at citation time, and for an element-test XPath
    # (the only kind reference_model builds), re-evaluating the same
    # selector string against a different document can only ever yield
    # zero, one, or many *elements* -- never a non-element match, since the
    # XPath's own trailing step syntax is what determines that, and it
    # doesn't change between documents. This test exists only to pin
    # _classify()'s own defined behavior for a status the spec explicitly
    # names, via a hand-constructed LeafCheckResult, not to simulate a
    # reachable real-world scenario.
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    fake_result = LeafCheckResult(
        leaf=leaf,
        outcome=ResolutionOutcome(status=Status.UNCITABLE),
        hash_changed=None,
        new_content_hash=None,
    )
    report = sweep({"fact-1": leaf}, REAL_MODULE_ROOT)
    report.results_by_key["fact-1"][:] = [fake_result]

    summary = summarize_for_review(report)

    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.outcome.status == Status.UNCITABLE
    assert flagged_leaf.drift_kind == DriftKind.STRUCTURAL
