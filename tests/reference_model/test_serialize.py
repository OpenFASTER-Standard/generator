import json

from reference_model.cite import cite, cite_union
from reference_model.model import SubjectDocument
from reference_model.selectors.xpath_selector import XPathSelector
from reference_model.serialize import to_json_dict

REAL_XSD = "/work/ontologies/mikadiv-fm/sources/1.02/xsd/MiKaDiv_FM_Meldeart23_1.02.xsd"
AORDNR_XPATH = (
    "/xs:schema/xs:complexType[@name='AmtlicheOrdnungsnummerMa23ListeType']"
    "/xs:sequence/xs:element[@name='AOrdNr']"
)
ABGEF_XPATH = (
    "/xs:schema/xs:complexType[@name='Meldeart23']/xs:complexContent"
    "/xs:extension/xs:sequence/xs:element[@name='AbgefKapitalertragsteuer']"
)


def _subject_document() -> SubjectDocument:
    return SubjectDocument(family="MiKaDiv_FM_Meldeart23", version="1.02", retrieval_uri=REAL_XSD)


def test_to_json_dict_serializes_a_real_leaf():
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    result = to_json_dict(leaf)

    assert result["reference_id"] == leaf.reference_id
    assert result["content_hash"]["algorithm"] == leaf.content_hash.algorithm
    assert result["content_hash"]["digest"] == leaf.content_hash.digest
    assert result["subject_document"]["family"] == "MiKaDiv_FM_Meldeart23"
    assert result["subject_document"]["version"] == "1.02"
    assert result["selector"]["type"] == "XPathSelector"
    assert result["selector"]["value"] == AORDNR_XPATH


def test_to_json_dict_survives_a_real_json_round_trip():
    leaf = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))

    result = to_json_dict(leaf)
    round_tripped = json.loads(json.dumps(result))

    assert round_tripped == result


def test_to_json_dict_serializes_a_union_recursively():
    leaf_1 = cite(_subject_document(), XPathSelector.create(AORDNR_XPATH))
    leaf_2 = cite(_subject_document(), XPathSelector.create(ABGEF_XPATH))
    union = cite_union([leaf_1, leaf_2])

    result = to_json_dict(union)

    assert result["reference_id"] == union.reference_id
    assert len(result["parts"]) == 2
    assert result["parts"][0] == to_json_dict(leaf_1)
    assert result["parts"][1] == to_json_dict(leaf_2)
