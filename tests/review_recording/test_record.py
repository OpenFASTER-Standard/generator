import json

from reference_model.cite import check_leaf
from reference_model.model import Status
from review_recording.record import Verdict, record_review
from review_surfacing.summarize import DriftKind


def test_record_review_returns_a_resolvable_leaf(tmp_path):
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
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
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.STRUCTURAL,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.REJECTED,
        reasoning="The renamed element needs a real extraction fix.",
    )

    written = json.loads(open(leaf.subject_document.retrieval_uri, encoding="utf-8").read())
    assert written["fact_key"] == "fact-1"
    assert written["family"] == "MiKaDiv_FM_Meldeart23"
    assert written["drift_kind"] == "STRUCTURAL"
    assert written["reviewer"] == "julian.nalenz@divizend.com"
    assert written["verdict"] == "rejected"
    assert written["reasoning"] == "The renamed element needs a real extraction fix."
    assert "reviewed_at" in written and "T" in written["reviewed_at"]  # a real ISO timestamp


def test_record_review_creates_reviews_dir_if_missing(tmp_path):
    reviews_dir = tmp_path / "does-not-exist-yet"
    assert not reviews_dir.exists()

    leaf = record_review(
        reviews_dir=str(reviews_dir),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="First review ever written to this directory.",
    )

    assert reviews_dir.exists()
    written_files = list(reviews_dir.iterdir())
    assert len(written_files) == 1
    assert leaf.subject_document.retrieval_uri == str(written_files[0])


def test_unmodified_review_record_is_unchanged_on_recheck(tmp_path):
    leaf = record_review(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )

    result = check_leaf(leaf)
    assert result.outcome.status == Status.RESOLVED
    assert result.hash_changed is False


def test_two_calls_with_identical_arguments_produce_independent_records(tmp_path):
    kwargs = dict(
        reviews_dir=str(tmp_path),
        fact_key="fact-1",
        family="MiKaDiv_FM_Meldeart23",
        drift_kind=DriftKind.CONTENT,
        reviewer="julian.nalenz@divizend.com",
        verdict=Verdict.APPROVED,
        reasoning="Confirmed with BZSt: non-substantive schema clarification.",
    )
    leaf_1 = record_review(**kwargs)
    leaf_2 = record_review(**kwargs)

    assert leaf_1.subject_document.family != leaf_2.subject_document.family
    assert leaf_1.subject_document.retrieval_uri != leaf_2.subject_document.retrieval_uri
    assert leaf_1.reference_id != leaf_2.reference_id
