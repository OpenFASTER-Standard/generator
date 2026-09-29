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


def test_importing_deserialize_alone_does_not_pull_in_every_selectors_dependencies():
    # reference_model.deserialize used to hardcode its own selector-type ->
    # class dict, importing all three selector modules eagerly at module
    # scope -- defeating the exact dependency isolation the test above
    # exists to guarantee for reference_model.model. It now looks selectors
    # up via the same registry.py every selector module already registers
    # itself into, so importing it alone pulls in nothing beyond the model.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import reference_model.deserialize\n"
            "import sys\n"
            "assert 'pdfplumber' not in sys.modules, 'pdfplumber should not be imported by reference_model.deserialize alone'\n"
            "assert 'shapely' not in sys.modules, 'shapely should not be imported by reference_model.deserialize alone'\n"
            "assert 'lxml' not in sys.modules, 'lxml should not be imported by reference_model.deserialize alone'\n",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
