from extraction.annex_pdf import extract_name_occurrences, extract_name_occurrences_with_pages

ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_text_output_is_byte_identical_to_the_existing_function_on_the_real_corpus():
    """The whole point of this new function is to add page/bbox info
    without changing any text extraction/n behavior -- this is a real
    regression guard, not a synthetic example, run against the real,
    full 262-page annex PDF."""
    old = extract_name_occurrences(ANNEX_PDF)
    new = extract_name_occurrences_with_pages(ANNEX_PDF)

    old_text_only = old
    new_text_only = {name: [occ.text for occ in occs] for name, occs in new.items()}

    assert set(old_text_only.keys()) == set(new_text_only.keys())
    assert old_text_only == new_text_only


def test_every_occurrence_carries_a_real_page_number_and_a_real_bbox():
    occurrences = extract_name_occurrences_with_pages(ANNEX_PDF)

    sample = occurrences["WIdNr"]
    assert len(sample) > 0
    for occ in sample:
        assert isinstance(occ.page_number, int) and occ.page_number >= 1
        x0, top, x1, bottom = occ.bbox
        assert x1 > x0 and bottom > top
