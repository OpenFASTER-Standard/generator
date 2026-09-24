import json
import shutil

import pytest

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from review_consultation.consult import ReviewLoadError, apply_reviews, load_reviews
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import summarize_for_review
from staleness_sweep.sweep import sweep

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _real_meldeart23_subject_document():
    return SubjectDocument(
        family="MiKaDiv_FM_Meldeart23",
        version="1.02",
        retrieval_uri=f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
    )


def _write_snapshot(module_root, version, xsd_text):
    snapshot = module_root / version
    shutil.copytree(module_root / "1.02", snapshot)
    (snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(xsd_text, encoding="utf-8")
    (module_root / "_current").write_text(version)


def test_approved_review_suppresses_matching_content_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed benign.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_content_drift_resurfaces_after_further_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    first_mutation = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", first_mutation)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary_v1 = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf_v1,) = summary_v1.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf_v1,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First change confirmed benign.",
    )

    second_mutation = first_mutation.replace('minOccurs="0"', 'minOccurs="0" maxOccurs="2"')
    assert second_mutation != first_mutation
    (module_root / "1.03" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(
        second_mutation, encoding="utf-8"
    )

    summary_v2 = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary_v2, reviews)

    assert "fact-1" in filtered.flagged
    (still_flagged,) = filtered.flagged["fact-1"]
    assert still_flagged.fingerprint != flagged_leaf_v1.fingerprint


def test_approved_review_suppresses_matching_structural_drift(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]
    assert flagged_leaf.fingerprint == "NOT_FOUND"

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Renamed intentionally, extraction updated separately.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_rejected_review_does_not_suppress(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="This needs a real extraction fix.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged
    assert filtered.flagged["fact-1"] == summary.flagged["fact-1"]


def test_both_approved_and_rejected_for_same_fingerprint_stays_visible(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    )
    _write_snapshot(module_root, "1.03", mutated)

    leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, str(module_root)))
    (flagged_leaf,) = summary.flagged["fact-1"]

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Initially approved.",
    )
    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=flagged_leaf,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="On further thought, this needs a real fix.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged


def test_union_with_one_leaf_approved_key_remains_with_only_unreviewed_leaf(tmp_path):
    # Both leaves are renamed, so both go STRUCTURAL with the identical
    # fingerprint "NOT_FOUND" -- this is deliberate, not incidental: two
    # different leaves sharing a (fact_key, drift_kind, fingerprint) triple
    # is exactly the collision apply_reviews() must not conflate. Approving
    # one must never suppress the other just because they look alike.
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuerRenamed" type="std:Dezimal14dot2Type">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    abgef_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    aordnr_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([abgef_leaf, aordnr_leaf])

    summary = summarize_for_review(sweep({"fact-1": union}, str(module_root)))
    assert len(summary.flagged["fact-1"]) == 2
    assert {fl.fingerprint for fl in summary.flagged["fact-1"]} == {"NOT_FOUND"}
    abgef_flagged = next(fl for fl in summary.flagged["fact-1"] if fl.leaf == abgef_leaf)

    record_review(
        reviews_dir=str(tmp_path / "reviews"),
        fact_key="fact-1",
        flagged=abgef_flagged,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="This rename is expected; the other one is not yet reviewed.",
    )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" in filtered.flagged
    (remaining,) = filtered.flagged["fact-1"]
    assert remaining.leaf == aordnr_leaf


def test_union_with_all_leaves_approved_key_is_dropped(tmp_path):
    module_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_MODULE_ROOT, module_root)
    original = (module_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace(
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
        '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
    ).replace('name="AOrdNr"', 'name="AOrdNrRenamed"')
    _write_snapshot(module_root, "1.03", mutated)

    content_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))
    structural_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    union = cite_union([content_leaf, structural_leaf])

    summary = summarize_for_review(sweep({"fact-1": union}, str(module_root)))
    for flagged_leaf in summary.flagged["fact-1"]:
        record_review(
            reviews_dir=str(tmp_path / "reviews"),
            fact_key="fact-1",
            flagged=flagged_leaf,
            reviewer="julian.nalenz@divizend.com",
            verdict=Verdict.APPROVED,
            reasoning="Both changes confirmed benign.",
        )

    reviews = load_reviews(str(tmp_path / "reviews"))
    filtered = apply_reviews(summary, reviews)

    assert "fact-1" not in filtered.flagged


def test_unresolved_families_and_excluded_keys_pass_through_unchanged():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver",
        version="1.02",
        retrieval_uri=f"{REAL_MODULE_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd",
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    summary = summarize_for_review(sweep({"fact-1": leaf}, REAL_MODULE_ROOT))

    filtered = apply_reviews(summary, [])

    assert filtered.unresolved_families == summary.unresolved_families
    assert filtered.excluded_keys == summary.excluded_keys
    assert filtered.excluded_keys == ("fact-1",)


def test_load_reviews_on_nonexistent_directory_returns_empty_list(tmp_path):
    reviews = load_reviews(str(tmp_path / "does-not-exist"))
    assert reviews == []


def _complete_review_document(**overrides):
    document = {
        "fact_key": "fact-1",
        "family": "MiKaDiv_FM_Meldeart23",
        "leaf_reference_id": "some-reference-id",
        "drift_kind": "CONTENT",
        "reviewed_fingerprint": "abc123",
        "reviewer": "julian.nalenz@divizend.com",
        "reviewed_at": "2026-09-24T00:00:00+00:00",
        "verdict": "approved",
        "reasoning": "n/a",
    }
    document.update(overrides)
    return document


def test_load_reviews_raises_on_malformed_json(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="not valid JSON"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_non_utf8_file(tmp_path):
    (tmp_path / "latin1.json").write_bytes('{"caption": "Dateigröße"}'.encode("latin-1"))
    with pytest.raises(ReviewLoadError, match="not valid JSON"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_non_object_json(tmp_path):
    (tmp_path / "array.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="expected a JSON object"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_missing_required_field(tmp_path):
    incomplete = _complete_review_document()
    del incomplete["reasoning"]
    (tmp_path / "incomplete.json").write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="missing field"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_non_string_field_value(tmp_path):
    invalid = _complete_review_document(reviewed_fingerprint=12345)
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="reviewed_fingerprint"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_null_field_value(tmp_path):
    invalid = _complete_review_document(fact_key=None)
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="fact_key"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_invalid_drift_kind_value(tmp_path):
    invalid = _complete_review_document(drift_kind="NOT_A_REAL_DRIFT_KIND")
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="invalid drift_kind/verdict value"):
        load_reviews(str(tmp_path))


def test_load_reviews_raises_on_invalid_verdict_value(tmp_path):
    invalid = _complete_review_document(verdict="maybe")
    (tmp_path / "invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ReviewLoadError, match="invalid drift_kind/verdict value"):
        load_reviews(str(tmp_path))


def test_load_reviews_skips_a_directory_matching_the_glob_pattern(tmp_path):
    (tmp_path / "not-a-review.json").mkdir()
    (tmp_path / "real-review.json").write_text(
        json.dumps(_complete_review_document()), encoding="utf-8"
    )

    reviews = load_reviews(str(tmp_path))

    assert len(reviews) == 1
    assert reviews[0].fact_key == "fact-1"
