from discovery.xsd_discoverer import Candidate
from discovery.corpus_candidates import list_corpus_candidates

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

REAL_XSD_FAMILIES = {
    "MiKaDiv_FM",
    "MiKaDiv_FM_Fachtypen",
    "MiKaDiv_FM_Meldeart11",
    "MiKaDiv_FM_Meldeart13",
    "MiKaDiv_FM_Meldeart21",
    "MiKaDiv_FM_Meldeart22",
    "MiKaDiv_FM_Meldeart23",
    "MiKaDiv_FM_MeldeartErg",
    "MiKaDiv_FM_MeldeartenBasis",
    "MiKaDiv_FM_MeldeartenSonder",
    "MiKaDiv_FM_Personentypen",
    "MiKaDiv_FM_Standardtypen",
    "din-norm-91379-datatypes",
}

REAL_PER_FAMILY_COUNTS = {
    "MiKaDiv_FM": 47,
    "MiKaDiv_FM_Fachtypen": 85,
    "MiKaDiv_FM_Meldeart11": 1,
    "MiKaDiv_FM_Meldeart13": 18,
    "MiKaDiv_FM_Meldeart21": 14,
    "MiKaDiv_FM_Meldeart22": 19,
    "MiKaDiv_FM_Meldeart23": 5,
    "MiKaDiv_FM_MeldeartErg": 2,
    "MiKaDiv_FM_MeldeartenBasis": 22,
    "MiKaDiv_FM_MeldeartenSonder": 8,
    "MiKaDiv_FM_Personentypen": 127,
    "MiKaDiv_FM_Standardtypen": 73,
    "din-norm-91379-datatypes": 1,
}


def test_returns_exactly_the_13_real_xsd_families_never_any_pdf_family():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    assert set(result.keys()) == REAL_XSD_FAMILIES


def test_real_per_family_candidate_counts_match_live_verification():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    for family, expected_count in REAL_PER_FAMILY_COUNTS.items():
        assert len(result[family].candidates) == expected_count, family


def test_total_real_candidate_count_across_the_whole_corpus_is_422():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    assert sum(len(r.candidates) for r in result.values()) == 422


def test_a_known_real_candidate_appears_with_the_correct_xpath():
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    aordnr_xpath = (
        "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
        "/xs:sequence/xs:element[@name='AOrdNr']"
    )
    matches = [c for c in result["MiKaDiv_FM_Meldeart23"].candidates if c.xpath == aordnr_xpath]
    assert len(matches) == 1
    assert matches[0].name == "AOrdNr"
    assert matches[0].tag == "element"


def test_returns_the_real_candidate_type_with_no_family_or_location_fields():
    # No second, hand-maintained "CorpusCandidate" dataclass duplicating
    # discovery.xsd_discoverer.Candidate field-for-field -- this returns
    # the real DiscoveryResult (candidates + excluded) discover_candidates()
    # itself produces, per the 2026-09-29 audit finding on that duplication
    # silently dropping `excluded`.
    result = list_corpus_candidates(REAL_MODULE_ROOT)
    sample = result["MiKaDiv_FM_Meldeart23"].candidates[0]
    assert isinstance(sample, Candidate)
    assert not hasattr(sample, "family")
    assert not hasattr(sample, "retrieval_uri")


def test_on_corpus_with_no_current_pointer_returns_empty_dict(tmp_path):
    assert list_corpus_candidates(str(tmp_path)) == {}


def _synthetic_corpus(tmp_path, entries: dict) -> str:
    import json

    module_root = tmp_path / "corpus"
    snapshot_dir = module_root / "1.0"
    snapshot_dir.mkdir(parents=True)
    manifest = {}
    for family, (filename, content) in entries.items():
        if content is not None:
            (snapshot_dir / filename).write_text(content, encoding="utf-8")
        manifest[family] = filename
    (snapshot_dir / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (module_root / "_current").write_text("1.0", encoding="utf-8")
    return str(module_root)


_VALID_XSD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
    '<xs:element name="Foo" type="xs:string"/>'
    "</xs:schema>"
)


def test_list_corpus_candidates_skips_a_family_whose_manifest_entry_is_broken_but_keeps_others(tmp_path):
    module_root = _synthetic_corpus(tmp_path, {
        "GoodFamily": ("good.xsd", _VALID_XSD),
        "BrokenFamily": ("does-not-exist.xsd", None),
    })

    result = list_corpus_candidates(module_root)

    assert "GoodFamily" in result
    assert len(result["GoodFamily"].candidates) == 1
    assert "BrokenFamily" not in result


def test_list_corpus_candidates_skips_a_family_with_corrupt_xml_but_keeps_others(tmp_path):
    module_root = _synthetic_corpus(tmp_path, {
        "GoodFamily": ("good.xsd", _VALID_XSD),
        "CorruptFamily": ("corrupt.xsd", "<not><valid>xml"),
    })

    result = list_corpus_candidates(module_root)

    assert "GoodFamily" in result
    assert len(result["GoodFamily"].candidates) == 1
    assert "CorruptFamily" not in result


_XSD_WITH_AMBIGUOUS_NAMES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" '
    'xmlns:vendor="urn:vendor">'
    "<wrapper><xs:element name=\"Decoy\" type=\"xs:string\"/></wrapper>"
    "<vendor:wrapper><xs:element name=\"Decoy\" type=\"xs:string\"/></vendor:wrapper>"
    "</xs:schema>"
)


def test_list_corpus_candidates_surfaces_excluded_candidates_not_just_real_ones(tmp_path):
    # Real bug found in the 2026-09-29 audit: a construct discover_candidates()
    # itself classifies as ExcludedCandidate (an ambiguous computed xpath)
    # used to be silently dropped one layer up here -- GET /api/candidates
    # could not tell "this schema has no such construct" from "it exists
    # but couldn't be given an unambiguous xpath".
    module_root = _synthetic_corpus(tmp_path, {
        "AmbiguousFamily": ("ambiguous.xsd", _XSD_WITH_AMBIGUOUS_NAMES),
    })

    result = list_corpus_candidates(module_root)

    # Two "Decoy" elements share the same computed xpath (a non-XSD-namespace
    # ancestor doesn't affect the path): one is a real, correct candidate,
    # the other is recorded as excluded -- not silently dropped, per
    # discover_candidates()'s own "recorded, never silently wrong" rule.
    assert len(result["AmbiguousFamily"].candidates) == 1
    assert len(result["AmbiguousFamily"].excluded) == 1
    assert result["AmbiguousFamily"].excluded[0].name == "Decoy"
