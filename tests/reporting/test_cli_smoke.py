"""A real, whole-corpus smoke test: the CLI's own main() runs the full
real pipeline end to end and produces a non-trivial HTML file. This is
deliberately not a mock of the pipeline -- it's the same real pipeline
the operator will actually run, exercised once here so a real breakage
(e.g. an import error, an argument-parsing bug) fails in CI/test runs
too, not only when a human happens to run the CLI by hand.

Both real fixture paths are given as absolute paths, and the subprocess
runs with cwd=/work/generator explicitly -- this repo's real fixture
files live in a separate sibling repo at /work/ontologies/, so a
cwd-relative path here would resolve incorrectly regardless of which
directory pytest itself happens to be invoked from."""
import subprocess
import sys

ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_cli_generates_a_real_non_trivial_report(tmp_path):
    output = tmp_path / "report.html"

    result = subprocess.run(
        [sys.executable, "-m", "reporting", ROOT_XSD, ANNEX_PDF, "-o", str(output)],
        cwd="/work/generator",
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    html = output.read_text()
    assert "<html" in html
    assert "MiKaDivFMRoot" in html  # a real, known type/element name must appear
    assert len(html) > 100_000  # a real, non-trivial report, not an empty shell
