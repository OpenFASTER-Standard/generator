from annotation_model.outcomes import Status
from annotation_model.selectors.svg import canonicalize_and_hash_text, resolve_svg_region
from tests.corpus_fixtures import REAL_CORPUS_ROOT, requires_real_corpus

REAL_PDF = f"{REAL_CORPUS_ROOT}/1.02/khb/khb_mikadiv_fm_de_v9.pdf"
PAGE_12 = 12
HEADING_POINTS = "60,88 255,88 255,115 60,115"
CAPTION_POINTS = "170,565 270,565 270,590 170,590"


@requires_real_corpus
def test_resolves_real_heading_and_hash_is_reproducible():
    outcome_1 = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    assert outcome_1.status == Status.RESOLVED
    assert "Nachrichteninhalte" in outcome_1.raw_content

    digest_1 = canonicalize_and_hash_text(outcome_1.raw_content)
    outcome_2 = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    digest_2 = canonicalize_and_hash_text(outcome_2.raw_content)
    assert digest_1 == digest_2


@requires_real_corpus
def test_different_real_region_produces_different_hash():
    heading = resolve_svg_region(REAL_PDF, PAGE_12, HEADING_POINTS)
    caption = resolve_svg_region(REAL_PDF, PAGE_12, CAPTION_POINTS)
    assert canonicalize_and_hash_text(heading.raw_content) != canonicalize_and_hash_text(caption.raw_content)


@requires_real_corpus
def test_page_beyond_real_document_length_is_not_found():
    outcome = resolve_svg_region(REAL_PDF, 9999, HEADING_POINTS)
    assert outcome.status == Status.NOT_FOUND


def test_missing_pdf_file_is_not_found():
    outcome = resolve_svg_region("/nonexistent/does-not-exist.pdf", 1, HEADING_POINTS)
    assert outcome.status == Status.NOT_FOUND


def test_corrupt_pdf_is_not_found_not_a_raised_exception(tmp_path):
    # I10: a file that exists but isn't a valid PDF propagated a raw
    # pdfminer exception instead of resolving NOT_FOUND -- asymmetric
    # with the XPath side, which deliberately maps a parse failure to
    # NOT_FOUND, and would abort an entire drift sweep over one bad file.
    bad_pdf = tmp_path / "notapdf.pdf"
    bad_pdf.write_text("this is not a PDF", encoding="utf-8")
    outcome = resolve_svg_region(str(bad_pdf), 1, HEADING_POINTS)
    assert outcome.status == Status.NOT_FOUND


def test_extract_points_recovers_the_raw_points_string():
    from annotation_model.selectors.svg import extract_points

    svg_value = "<svg:polygon points='60,88 255,88 255,115 60,115' xmlns:svg='http://www.w3.org/2000/svg'/>"
    assert extract_points(svg_value) == "60,88 255,88 255,115 60,115"
