from citations.source_files import github_url_for, infer_kind, list_source_files, list_xsd_files

ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"


def test_infer_kind_from_extension():
    assert infer_kind("/a/b.pdf") == "pdf"
    assert infer_kind("/a/b.PDF") == "pdf"
    assert infer_kind("/a/b.xsd") == "xsd"
    assert infer_kind("/a/b.xml") == "xsd"


def test_github_url_for_a_real_corpus_path():
    assert github_url_for(ROOT_XSD) == (
        "https://github.com/OpenFASTER-Standard/ontologies/blob/main/"
        "mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
    )


def test_github_url_for_a_path_outside_the_corpus_repo_is_none():
    assert github_url_for("/tmp/not-the-corpus/file.xsd") is None


def test_list_xsd_files_finds_every_real_imported_file_not_just_the_root():
    files = list_xsd_files(ROOT_XSD)

    assert ROOT_XSD in files
    assert "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Personentypen_1.02.xsd" in files
    assert "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd" in files
    # xmlschema's own bundled built-in schemas (XMLSchema.xsd, xml.xsd,
    # XMLSchema-instance.xsd) must be excluded -- they're not part of
    # this corpus's own repo.
    assert not any("xmlschema/schemas" in f for f in files)
    assert len(files) == 13


def test_list_source_files_includes_the_pdf_alongside_every_xsd_file():
    files = list_source_files(ROOT_XSD, ANNEX_PDF)

    assert len(files) == 14
    pdf_entries = [f for f in files if f.path == ANNEX_PDF]
    assert len(pdf_entries) == 1
    assert pdf_entries[0].kind == "pdf"
    assert pdf_entries[0].github_url is not None
