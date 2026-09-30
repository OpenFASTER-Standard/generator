import pytest

from annotation_model.transform.registry import Transformation, get, register, unregister


def _transformation(name="t1", query="SELECT ?x WHERE { ?x ?p ?o }", min_rows=1):
    return Transformation(name=name, query=query, renderer=lambda rows: rows, min_rows=min_rows)


def test_register_then_get_round_trips():
    try:
        register(_transformation(name="round-trip-1"))
        result = get("round-trip-1")
        assert result.name == "round-trip-1"
    finally:
        unregister("round-trip-1")


def test_registering_the_same_name_twice_raises_without_replace():
    try:
        register(_transformation(name="dup-1"))
        with pytest.raises(ValueError, match="already registered"):
            register(_transformation(name="dup-1"))
    finally:
        unregister("dup-1")


def test_registering_the_same_name_twice_with_replace_succeeds():
    try:
        register(_transformation(name="replace-1", min_rows=1))
        register(_transformation(name="replace-1", min_rows=0), replace=True)
        assert get("replace-1").min_rows == 0
    finally:
        unregister("replace-1")


def test_get_missing_name_raises_with_known_names_listed():
    try:
        register(_transformation(name="known-1"))
        with pytest.raises(KeyError, match="known-1"):
            get("no-such-transformation-xyz")
    finally:
        unregister("known-1")


def test_two_transformations_do_not_see_each_others_registration():
    try:
        register(_transformation(name="a-1", query="SELECT ?a WHERE { ?a ?p ?o }"))
        register(_transformation(name="b-1", query="SELECT ?b WHERE { ?b ?p ?o }"))
        assert get("a-1").query != get("b-1").query
        assert get("a-1").name == "a-1"
        assert get("b-1").name == "b-1"
    finally:
        unregister("a-1")
        unregister("b-1")


def test_unregister_removes_a_transformation():
    register(_transformation(name="to-remove-1"))
    unregister("to-remove-1")
    with pytest.raises(KeyError):
        get("to-remove-1")


def test_unregister_of_a_missing_name_is_a_no_op():
    unregister("never-registered-xyz")  # must not raise


def test_negative_min_rows_is_rejected():
    with pytest.raises(ValueError, match="min_rows"):
        Transformation(name="bad-min-rows-1", query="SELECT ?x WHERE { ?x ?p ?o }", renderer=lambda rows: rows, min_rows=-1)


def test_non_integer_min_rows_is_rejected():
    with pytest.raises(ValueError, match="min_rows"):
        Transformation(name="bad-min-rows-2", query="SELECT ?x WHERE { ?x ?p ?o }", renderer=lambda rows: rows, min_rows="2")
