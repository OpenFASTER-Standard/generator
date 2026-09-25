from pathlib import Path

from staleness_sweep.resolve import FamilyLocation, list_current_locations

REAL_MODULE_ROOT = "/work/ontologies/mikadiv-fm/sources"

REAL_FAMILIES = {
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
    "ausstellung_steuerbescheinigung",
    "einzelfragen_datenuebermittlung_de",
    "individual_questions_en",
    "khb_mikadiv_fm_anlage_de",
    "khb_mikadiv_fm_anlage_en",
    "khb_mikadiv_fm_de",
    "khb_mikadiv_fm_en",
    "verfahrensleitende_hinweise",
}


def test_lists_all_21_real_families_with_correct_version_and_existing_paths():
    locations = list_current_locations(REAL_MODULE_ROOT)

    assert len(locations) == 21
    assert {loc.family for loc in locations} == REAL_FAMILIES
    for loc in locations:
        assert loc.version == "1.02"
        assert Path(loc.retrieval_uri).exists()


def test_a_real_xsd_family_resolves_to_the_same_path_resolve_current_location_would():
    locations = {loc.family: loc for loc in list_current_locations(REAL_MODULE_ROOT)}

    expected = str(Path(REAL_MODULE_ROOT) / "1.02" / "xsd" / "MiKaDiv_FM_Meldeart23_1.02.xsd")
    assert locations["MiKaDiv_FM_Meldeart23"].retrieval_uri == expected


def test_results_are_sorted_by_family_name():
    locations = list_current_locations(REAL_MODULE_ROOT)
    families = [loc.family for loc in locations]
    assert families == sorted(families)


def test_missing_current_pointer_returns_empty_list(tmp_path):
    assert list_current_locations(str(tmp_path)) == []


def test_returns_family_location_instances():
    locations = list_current_locations(REAL_MODULE_ROOT)
    assert all(isinstance(loc, FamilyLocation) for loc in locations)
