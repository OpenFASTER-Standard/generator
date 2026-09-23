import subprocess
import sys


def test_importing_just_the_data_model_does_not_pull_in_every_selectors_dependencies():
    # A subprocess is required for this to be a real test: pdfplumber/shapely
    # may already be in sys.modules from another test module imported
    # earlier in the same pytest session, which would make an in-process
    # check pass even if reference_model.model itself newly imports them.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import reference_model.model\n"
            "import sys\n"
            "assert 'pdfplumber' not in sys.modules, 'pdfplumber should not be imported by reference_model.model alone'\n"
            "assert 'shapely' not in sys.modules, 'shapely should not be imported by reference_model.model alone'\n"
            "assert 'lxml' not in sys.modules, 'lxml should not be imported by reference_model.model alone'\n",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
