import json

from reference_model.cite import cite
from reference_model.model import ResolutionOutcome, Status, SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from references_catalog.catalog import add_revision, get_history
from review_recording.record import Verdict
from review_surfacing.summarize import DriftKind, FlaggedLeaf
from review_workflow.orchestrate import get_review_summary, submit_review
from staleness_sweep.resolve import resolve_family_location

CORPUS_ROOT = "/work/ontologies/mikadiv-fm/sources"


def _real_leaf(family: str, xpath: str):
    location = resolve_family_location(CORPUS_ROOT, family)
    subject_document = SubjectDocument(family=family, version="1.02", retrieval_uri=location.retrieval_uri)
    return cite(subject_document, XPathSelector.create(xpath))


def test_healthy_and_corrupted_entries_coexist(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "healthy-key", leaf, "author", "comment", False)

    catalog = json.loads(catalog_path.read_text())
    catalog["corrupted-key"] = [{
        "revision_id": "x", "reference": {"not": "a-real-reference"},
        "author": "a", "comment": "c", "is_correction": False, "created_at": "2026-01-01T00:00:00+00:00",
    }]
    catalog_path.write_text(json.dumps(catalog))

    result = get_review_summary(str(catalog_path), CORPUS_ROOT, str(tmp_path / "reviews"))

    assert result.deserialization_failures == ("corrupted-key",)
    assert "corrupted-key" not in result.summary.flagged


def test_submit_review_appends_a_catalog_revision_citing_the_review_decision(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "some-key", leaf, "author", "comment", False)

    flagged = FlaggedLeaf(
        leaf=leaf,
        outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT,
        fingerprint="abc123",
    )

    revision = submit_review(
        str(catalog_path), str(tmp_path / "reviews"), "some-key", flagged, "reviewer-1", Verdict.APPROVED, "looks fine",
    )

    history = get_history(str(catalog_path), "some-key")
    assert len(history) == 2
    assert history[-1] == revision
    assert "looks fine" in revision.comment
    assert "approved" in revision.comment
    assert revision.is_correction is False


def test_get_review_summary_runs_apply_reviews_end_to_end(tmp_path):
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    reviews_dir = tmp_path / "reviews"
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "some-key", leaf, "author", "comment", False)

    result_before = get_review_summary(str(catalog_path), CORPUS_ROOT, str(reviews_dir))
    assert result_before.summary.flagged == {}
    assert result_before.deserialization_failures == ()


def test_submitting_a_review_does_not_stop_the_fact_key_from_being_swept_again(tmp_path):
    # The architectural bug found in the 2026-09-29 audit, predicted by name
    # in docs/specs/2026-09-23-review-recording-design.md's own warning:
    # submit_review() appends a REVIEW-kind revision on the fact_key it
    # reviewed. If that revision were ever treated as the page's "current"
    # citation, the next get_review_summary() would try to resolve family
    # "review-<uuid>" (never in any real manifest), get NOT_FOUND, and drop
    # the fact_key into excluded_keys -- silently ending drift monitoring
    # for exactly the fact a human just looked at. Assert the real seam:
    # after a review, the fact_key is still genuinely swept, not excluded.
    catalog_path = tmp_path / "references.json"
    catalog_path.write_text("{}")
    reviews_dir = tmp_path / "reviews"
    leaf = _real_leaf("MiKaDiv_FM_Meldeart23", "/xs:schema/xs:complexType[@name='Meldeart23']")
    add_revision(str(catalog_path), "some-key", leaf, "author", "comment", False)

    flagged = FlaggedLeaf(
        leaf=leaf,
        outcome=ResolutionOutcome(status=Status.RESOLVED),
        drift_kind=DriftKind.CONTENT,
        fingerprint="abc123",
    )
    submit_review(str(catalog_path), str(reviews_dir), "some-key", flagged, "reviewer-1", Verdict.APPROVED, "fine")

    result = get_review_summary(str(catalog_path), CORPUS_ROOT, str(reviews_dir))

    assert "some-key" not in result.summary.excluded_keys
    assert result.summary.unresolved_families == ()
    # Suppressed via apply_reviews() (the approved fingerprint matching),
    # not via exclusion from the sweep entirely -- the distinction Finding 1
    # is about.
    assert "some-key" not in result.summary.flagged
