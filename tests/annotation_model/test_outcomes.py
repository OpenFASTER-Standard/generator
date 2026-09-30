from annotation_model.outcomes import ResolutionOutcome, Status


def test_status_has_four_members():
    assert {s.value for s in Status} == {"RESOLVED", "NOT_FOUND", "AMBIGUOUS", "UNCITABLE"}


def test_resolution_outcome_defaults_raw_content_to_none():
    outcome = ResolutionOutcome(status=Status.NOT_FOUND)
    assert outcome.raw_content is None
