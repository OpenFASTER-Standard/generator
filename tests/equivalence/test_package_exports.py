"""The public interface later sub-projects import must be stable and
importable from the package root, not just individual submodules."""


def test_public_names_are_importable_from_the_package_root():
    from equivalence import (
        Divergence,
        Report,
        UnsupportedConstructError,
        check_equivalence,
    )

    assert callable(check_equivalence)
