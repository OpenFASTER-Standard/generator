def test_package_level_import_matches_the_spec_own_example():
    # docs/specs/2026-09-29-webapp-react-rebuild-design.md's own example
    # writes `from review_workflow import get_review_summary, submit_review`
    # -- previously broken, since __init__.py was empty and only
    # `from review_workflow.orchestrate import ...` worked.
    from review_workflow import get_review_summary, submit_review

    assert callable(get_review_summary)
    assert callable(submit_review)
