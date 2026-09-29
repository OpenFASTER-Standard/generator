import json
import shutil
from pathlib import Path

from reference_model.cite import cite, cite_union
from reference_model.model import ResolutionOutcome, SubjectDocument, Status
from reference_model.registry import Resolver, register, unregister
from reference_model.selectors.xpath_selector import XPathSelector
from staleness_sweep.sweep import FamilyResolutionFailure, sweep
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

pytestmark = requires_real_corpus

REAL_MELDEART23_XSD = f"{REAL_CORPUS_ROOT}/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
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
    report = sweep({"fact-1": leaf}, REAL_CORPUS_ROOT)

    assert report.family_resolution_failures == ()
    assert report.results_by_key["fact-1"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["fact-1"][0].hash_changed is False


def test_sweep_reports_an_unresolvable_family_as_a_failure_not_a_leaf_result():
    fake_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    leaf = cite(fake_subject_document, XPathSelector.create(AORDNR_XPATH))
    report = sweep({"fact-1": leaf}, REAL_CORPUS_ROOT)

    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )
    assert "fact-1" not in report.results_by_key


def test_sweep_with_no_references_returns_an_empty_report():
    report = sweep({}, REAL_CORPUS_ROOT)
    assert report.results_by_key == {}
    assert report.family_resolution_failures == ()
    assert report.excluded_keys == ()


def test_family_resolution_failures_are_sorted_deterministically():
    leaves = {
        f"fact-{name}": cite(
            SubjectDocument(family=name, version="1.02", retrieval_uri=REAL_MELDEART23_XSD),
            XPathSelector.create(AORDNR_XPATH),
        )
        for name in ("GhostZ", "GhostA", "GhostM")
    }
    report = sweep(leaves, REAL_CORPUS_ROOT)

    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="GhostA", status=Status.NOT_FOUND),
        FamilyResolutionFailure(family="GhostM", status=Status.NOT_FOUND),
        FamilyResolutionFailure(family="GhostZ", status=Status.NOT_FOUND),
    )


def test_excluded_keys_lists_every_key_touching_an_unresolved_family():
    good_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    bad_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    bad_leaf = cite(bad_subject_document, XPathSelector.create(ABGEF_XPATH))

    report = sweep({"good-fact": good_leaf, "bad-fact": bad_leaf}, REAL_CORPUS_ROOT)

    assert report.excluded_keys == ("bad-fact",)
    assert "good-fact" in report.results_by_key
    assert "bad-fact" not in report.results_by_key


def test_two_references_same_family_different_stale_stored_uris_both_use_resolved_path(tmp_path):
    original = Path(REAL_MELDEART23_XSD).read_text(encoding="utf-8")

    stale_copy_a = tmp_path / "stale-a.xsd"
    stale_copy_a.write_text(
        original.replace(
            '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
            '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="0">',
        ),
        encoding="utf-8",
    )
    stale_copy_b = tmp_path / "stale-b.xsd"
    stale_copy_b.write_text(
        original.replace(
            '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type">',
            '<xs:element name="AbgefKapitalertragsteuer" type="std:Dezimal14dot2Type" minOccurs="1">',
        ),
        encoding="utf-8",
    )

    leaf_a = cite(
        SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=str(stale_copy_a)),
        XPathSelector.create(ABGEF_XPATH),
    )
    leaf_b = cite(
        SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=str(stale_copy_b)),
        XPathSelector.create(ABGEF_XPATH),
    )

    report = sweep({"fact-a": leaf_a, "fact-b": leaf_b}, REAL_CORPUS_ROOT)

    # Both leaves' own stored URIs differ from each other AND from the
    # real current file -- if either fell back to its own stored path,
    # that path's own mutation would make it look unchanged. Both must
    # report a real change, proving both used the one resolved current file.
    assert report.results_by_key["fact-a"][0].hash_changed is True
    assert report.results_by_key["fact-b"][0].hash_changed is True


def test_family_nested_inside_a_union_is_still_collected():
    good_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    bad_subject_document = SubjectDocument(
        family="NoSuchFamilyEver", version="1.02", retrieval_uri=REAL_MELDEART23_XSD
    )
    bad_leaf = cite(bad_subject_document, XPathSelector.create(ABGEF_XPATH))
    inner_union = cite_union([bad_leaf])
    outer_union = cite_union([good_leaf, inner_union])

    report = sweep({"fact": outer_union}, REAL_CORPUS_ROOT)

    assert "fact" not in report.results_by_key
    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )


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

    report = sweep({"fact": leaf}, REAL_CORPUS_ROOT)

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

    report = sweep({"fact": union}, REAL_CORPUS_ROOT)

    assert "fact" not in report.results_by_key
    assert report.family_resolution_failures == (
        FamilyResolutionFailure(family="NoSuchFamilyEver", status=Status.NOT_FOUND),
    )


def test_sweep_over_a_deliberately_changed_synthetic_snapshot(tmp_path):
    # The spec's own Definition of Done scenario: cite a real fact, then
    # sweep against a tmp_path copy of the corpus with one deliberate
    # change on a second, synthetic snapshot -- never the real repo.
    corpus_root = tmp_path / "mikadiv-fm-sources"
    shutil.copytree(REAL_CORPUS_ROOT, corpus_root)

    original = (corpus_root / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").read_text(encoding="utf-8")
    mutated = original.replace('name="AOrdNr"', 'name="AOrdNrRenamed"')

    new_snapshot = corpus_root / "1.03"
    shutil.copytree(corpus_root / "1.02", new_snapshot)
    (new_snapshot / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd").write_text(mutated, encoding="utf-8")
    (corpus_root / "_current").write_text("1.03")

    changed_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))
    unchanged_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(ABGEF_XPATH))

    report = sweep({"changed-fact": changed_leaf, "unchanged-fact": unchanged_leaf}, str(corpus_root))

    assert report.family_resolution_failures == ()
    assert report.results_by_key["changed-fact"][0].outcome.status == Status.NOT_FOUND
    assert report.results_by_key["unchanged-fact"][0].outcome.status == Status.RESOLVED
    assert report.results_by_key["unchanged-fact"][0].hash_changed is False


def test_one_references_unexpected_check_failure_does_not_take_down_the_whole_sweep():
    # Real regression found in a whole-branch review: sweep() had no
    # per-reference error isolation, unlike every other seam in this
    # codebase (list_corpus_candidates() isolates one corrupt XSD,
    # resolve_family_location() isolates one broken manifest entry,
    # get_review_summary() isolates one undeserializable catalog entry).
    # An unexpected exception from a selector's own canonicalize_and_hash()
    # (the exact shape of the real C14NError bug this same review found)
    # must exclude only that one key, not 500 the whole review summary.
    healthy_leaf = cite(_real_meldeart23_subject_document(), XPathSelector.create(AORDNR_XPATH))

    from reference_model.model import Leaf, ContentHash, compute_leaf_reference_id
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _ExplodingSelector:
        type: str
        value: str

    def _exploding_resolve(selector, retrieval_uri):
        return ResolutionOutcome(status=Status.RESOLVED, raw_content="does not matter")

    def _exploding_canonicalize_and_hash(raw_content):
        raise RuntimeError("simulated C14N-shaped failure")

    register(
        "ExplodingSelectorForSweepTest",
        Resolver(resolve=_exploding_resolve, canonicalize_and_hash=_exploding_canonicalize_and_hash),
    )
    try:
        selector = _ExplodingSelector(type="ExplodingSelectorForSweepTest", value="/x")
        exploding_leaf = Leaf(
            reference_id=compute_leaf_reference_id("MiKaDiv_FM_Meldeart23", selector),
            subject_document=_real_meldeart23_subject_document(),
            selector=selector,
            content_hash=ContentHash(algorithm="sha256", digest="0" * 64),
            captured_at="2026-01-01T00:00:00Z",
        )

        report = sweep({"exploding-fact": exploding_leaf, "healthy-fact": healthy_leaf}, REAL_CORPUS_ROOT)

        assert "exploding-fact" in {f.key for f in report.check_failures}
        assert report.results_by_key["healthy-fact"][0].outcome.status == Status.RESOLVED
    finally:
        unregister("ExplodingSelectorForSweepTest")
