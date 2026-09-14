"""Integration tests for the orchestrator, against small hand-crafted
fixtures -- not real government XSDs (see this plan's spec, Testing
strategy)."""
import pathlib

from rdflib import Graph

from equivalence.checker import check_equivalence

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(name: str) -> Graph:
    graph = Graph()
    graph.parse(FIXTURES / name, format="turtle")
    return graph


def test_truly_equivalent_schemas_produce_no_divergences():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
        official_graph=_load("equivalent_official.ttl"),
        generated_graph=_load("equivalent_generated.ttl"),
    )

    assert report.divergences == []
    assert report.unmatched_official == []
    assert report.unmatched_generated == []
    assert report.confidence_note  # must always be set, never blank
    assert "not a completeness proof" in report.confidence_note


def test_divergent_max_length_is_caught_with_a_concrete_counterexample():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "divergent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "divergent_generated.xsd"),
        official_graph=_load("divergent_official.ttl"),
        generated_graph=_load("divergent_generated.ttl"),
    )

    assert len(report.divergences) >= 1
    divergence = report.divergences[0]
    assert divergence.xml_document  # the literal generated document is included
    assert divergence.official_verdict != divergence.generated_verdict


def test_divergent_facet_on_an_optional_leaf_is_still_caught():
    """Regression test: the leaf-boundary pass used to reuse one shared
    baseline structural case (always the "every optional particle
    absent" case) for every leaf, so an optional leaf's own candidate
    values were always built into a document that omitted the leaf
    entirely -- the same document every time, meaning a real facet
    divergence on an optional leaf (e.g. this maxLength mismatch) could
    never be detected. Before the fix, this produced zero divergences."""
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "divergent_optional_official.xsd"),
        generated_xsd_path=str(FIXTURES / "divergent_optional_generated.xsd"),
        official_graph=_load("divergent_optional_official.ttl"),
        generated_graph=_load("divergent_optional_generated.ttl"),
    )

    assert len(report.divergences) >= 1
    divergence = report.divergences[0]
    assert divergence.xml_document
    assert divergence.official_verdict != divergence.generated_verdict


def test_non_root_capable_matched_element_is_reported_as_not_checked():
    """Both schemas declare `Adresse` only as a local (nested, non-global)
    element -- it can never validly stand as a document root, so every
    document check_equivalence builds for it is rejected by BOTH schemas
    for the same "not an element of the schema" reason. That must be
    surfaced as "we couldn't check this", not silently folded into
    "checked and found equivalent" (zero divergences)."""
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "not_root_capable_official.xsd"),
        generated_xsd_path=str(FIXTURES / "not_root_capable_generated.xsd"),
        official_graph=_load("not_root_capable_official.ttl"),
        generated_graph=_load("not_root_capable_generated.ttl"),
    )

    assert report.divergences == []
    assert "Adresse" in report.not_checked


def test_unmatched_type_is_reported_not_silently_skipped():
    report = check_equivalence(
        official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
        generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
        official_graph=_load("unmatched_type_official.ttl"),
        generated_graph=_load("equivalent_official.ttl"),
    )

    assert "Nachname" in report.unmatched_official


def test_guardrail_fires_at_the_integration_level_not_just_in_isolation():
    """preconditions.check has its own unit test (Task 1) proving it
    raises in isolation -- this proves check_equivalence actually calls
    it and doesn't swallow the error."""
    import pytest

    from equivalence.preconditions import UnsupportedConstructError

    with pytest.raises(UnsupportedConstructError):
        check_equivalence(
            official_xsd_path=str(FIXTURES / "equivalent_official.xsd"),
            generated_xsd_path=str(FIXTURES / "equivalent_generated.xsd"),
            official_graph=_load("assertion_official.ttl"),
            generated_graph=_load("equivalent_official.ttl"),
        )
