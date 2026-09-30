from annotation_model.outcomes import ResolutionOutcome, Status


def test_status_has_four_members():
    assert {s.value for s in Status} == {"RESOLVED", "NOT_FOUND", "AMBIGUOUS", "UNCITABLE"}


def test_resolution_outcome_defaults_raw_content_to_none():
    outcome = ResolutionOutcome(status=Status.NOT_FOUND)
    assert outcome.raw_content is None


def test_public_surface_is_importable_from_the_package_root():
    import annotation_model

    for name in annotation_model.__all__:
        assert hasattr(annotation_model, name)
