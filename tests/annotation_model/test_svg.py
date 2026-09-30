from annotation_model.outcomes import Status
from annotation_model.selectors.svg import canonicalize_and_hash_text, resolve_svg_region
from tests.corpus_fixtures import requires_real_corpus

REAL_PDF = "/work/ontologies/mikadiv-fm/sources/1.02/khb/khb_mikadiv_fm_de_v9.pdf"
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
