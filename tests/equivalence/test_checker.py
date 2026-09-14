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
        generated_graph=_load("equivalent_official.ttl"),
    )

    assert report.divergences == []
    assert report.unmatched_official == []
    assert report.unmatched_generated == []
    assert report.confidence_note  # must always be set, never blank


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
