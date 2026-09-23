from dataclasses import dataclass

from reference_model.model import (
    ContentHash,
    Leaf,
    SubjectDocument,
    Union,
    compute_leaf_reference_id,
    compute_union_content_hash,
    compute_union_reference_id,
    now_iso,
    selector_canonical_form,
)


@dataclass(frozen=True)
class _DummySelector:
    type: str
    value: str


def _make_leaf(family: str, version: str, digest: str) -> Leaf:
    selector = _DummySelector(type="Dummy", value="same-for-both")
    return Leaf(
        reference_id=compute_leaf_reference_id(family, selector),
        subject_document=SubjectDocument(family=family, version=version, retrieval_uri=f"/tmp/{family}"),
        selector=selector,
        content_hash=ContentHash(algorithm="sha256", digest=digest),
        captured_at=now_iso(),
    )


def test_selector_canonical_form_is_stable_and_reflects_content():
    a = _DummySelector(type="Dummy", value="x")
    b = _DummySelector(type="Dummy", value="x")
    c = _DummySelector(type="Dummy", value="y")
    assert selector_canonical_form(a) == selector_canonical_form(b)
    assert selector_canonical_form(a) != selector_canonical_form(c)


def test_leaf_reference_id_is_deterministic_and_excludes_version():
    # Same family+selector, deliberately different version and content_hash --
    # per the spec, reference_id must still match. See Global Constraints.
    leaf_v1 = _make_leaf("MiKaDiv_FM_Meldeart23", "1.02", "aaa")
    leaf_v2 = _make_leaf("MiKaDiv_FM_Meldeart23", "1.03", "bbb")
    assert leaf_v1.reference_id == leaf_v2.reference_id
    assert leaf_v1.content_hash.digest != leaf_v2.content_hash.digest


def test_leaf_reference_id_differs_across_families():
    leaf_a = _make_leaf("family-a", "1.0", "aaa")
    leaf_b = _make_leaf("family-b", "1.0", "aaa")
    assert leaf_a.reference_id != leaf_b.reference_id


def test_union_reference_id_and_hash_are_deterministic_given_order():
    leaf_1 = _make_leaf("family-a", "1.0", "aaa")
    leaf_2 = _make_leaf("family-b", "1.0", "bbb")

    union_1 = Union(parts=(leaf_1, leaf_2))
    union_2 = Union(parts=(leaf_1, leaf_2))
    assert union_1.reference_id == union_2.reference_id
    assert union_1.content_hash.digest == union_2.content_hash.digest

    # Order is load-bearing -- reversing it changes both ids, on purpose.
    union_reversed = Union(parts=(leaf_2, leaf_1))
    assert union_reversed.reference_id != union_1.reference_id
    assert union_reversed.content_hash.digest != union_1.content_hash.digest


def test_compute_union_reference_id_and_hash_are_pure_functions():
    assert compute_union_reference_id(["a", "b"]) == compute_union_reference_id(["a", "b"])
    assert compute_union_reference_id(["a", "b"]) != compute_union_reference_id(["b", "a"])
    hash_1 = compute_union_content_hash(["digest-a", "digest-b"])
    hash_2 = compute_union_content_hash(["digest-a", "digest-b"])
    assert hash_1.digest == hash_2.digest
    assert hash_1.algorithm == "sha256"
