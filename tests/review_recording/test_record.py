import json
import shutil

from reference_model.cite import check_leaf, cite
from reference_model.model import SubjectDocument, Status
from reference_model.selectors.xpath_selector import XPathSelector
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import summarize_for_review
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


def _real_meldeart23_subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_MELDEART23_XSD)


def _make_content_and_structural_snapshot(module_root):
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


def _content_flagged_leaf(module_root):
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)
    (flagged_leaf,) = summary.flagged["fact-1"]
    return flagged_leaf


def _structural_flagged_leaf(module_root):
    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, str(module_root))
    summary = summarize_for_review(report)
    (flagged_leaf,) = summary.flagged["fact-1"]
    return flagged_leaf


def test_record_review_returns_a_resolvable_leaf(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    assert leaf.content_hash.algorithm == "sha256"
    assert len(leaf.content_hash.digest) == 64
    assert leaf.subject_document.family.startswith("review-")
    assert leaf.subject_document.version == "1"

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["verdict"] == "approved"


def test_record_review_writes_the_full_document_shape(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _structural_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="The renamed element needs a real extraction fix.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["fact_key"] == "fact-1"
    assert written["family"] == "MiKaDiv_FM_Meldeart23"
    assert written["drift_kind"] == "STRUCTURAL"
    assert written["reviewed_fingerprint"] == "NOT_FOUND"
    assert written["reviewer"] == "julian.nalenz@divizend.com"
    assert written["verdict"] == "rejected"
    assert written["reasoning"] == "The renamed element needs a real extraction fix."
    assert "reviewed_at" in written and "T" in written["reviewed_at"]  # a real ISO timestamp


def test_record_review_writes_the_content_fingerprint(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed benign.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["reviewed_fingerprint"] == flagged_leaf.fingerprint
    assert len(written["reviewed_fingerprint"]) == 64


def test_record_review_creates_reviews_dir_if_missing(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    reviews_dir = tmp_path / "does-not-exist-yet"
    assert not reviews_dir.exists()

    leaf = record_review(
        reviews_dir=str(reviews_dir),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First review ever written to this directory.",
    )

    assert reviews_dir.exists()
    written_files = list(reviews_dir.iterdir())
    assert len(written_files) == 1
    assert leaf.subject_document.retrieval_uri == str(written_files[0])


def test_unmodified_review_record_is_unchanged_on_recheck(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    leaf = record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )

    result = check_leaf(leaf)
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is False


def test_two_calls_with_identical_arguments_produce_independent_records(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    _make_content_and_structural_snapshot(module_root)
    flagged_leaf = _content_flagged_leaf(module_root)

    kwargs = dict(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    leaf_1 = record_review(**kwargs)
    leaf_2 = record_review(**kwargs)

    assert leaf_1.subject_document.family != leaf_2.subject_document.family
    assert leaf_1.subject_document.retrieval_uri != leaf_2.subject_document.retrieval_uri
    assert leaf_1.reference_id != leaf_2.reference_id
