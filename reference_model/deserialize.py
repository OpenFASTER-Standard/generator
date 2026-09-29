"""Deserializes a plain JSON-safe dict (as produced by
reference_model.serialize.to_json_dict()) back into a real Reference.
See docs/specs/2026-09-29-webapp-react-rebuild-design.md.

Looks selector classes up via reference_model.registry rather than
keeping a second, hand-maintained type->class dict here -- registry.py's
own documented promise is that adding a new source format means writing
a resolve()/canonicalize_and_hash() pair and registering it, "nothing
else in this package, or any future consumer, needs to change". A
consumer must have imported the selector module(s) it needs (so they've
registered themselves) before calling from_json_dict() on data using
that type -- the same "import what you use" contract
reference_model/__init__.py already documents for the format-agnostic
model, which is what keeps importing this module alone from dragging in
every selector's own dependencies (pdfplumber/shapely/lxml).
"""
from __future__ import annotations

from errors import GeneratorError
from reference_model.model import ContentHash, Leaf, Reference, SubjectDocument, Union
from reference_model.registry import get_resolver


class ReferenceDeserializationError(GeneratorError):
    # Malformed catalog data reaching an unexpected place is a server-side
    # data problem, not something a caller's request fixes by retrying.
    http_status = 500


def from_json_dict(data: dict) -> Reference:
    if not isinstance(data, dict):
        raise ReferenceDeserializationError(f"expected a JSON object, got {type(data).__name__}")

    if "parts" in data:
        try:
            parts = [from_json_dict(part) for part in data["parts"]]
        except (KeyError, TypeError) as exc:
            raise ReferenceDeserializationError(f"malformed Union.parts: {exc}") from exc
        return Union(parts=tuple(parts))

    try:
        selector_data = dict(data["selector"])
        selector_type = selector_data["type"]
        try:
            resolver = get_resolver(selector_type)
        except KeyError as exc:
            raise ReferenceDeserializationError(f"unknown selector type: {selector_type!r}") from exc
        if resolver.selector_cls is None:
            raise ReferenceDeserializationError(
                f"selector type {selector_type!r} is registered but has no selector_cls "
                "to deserialize into"
            )
        selector = resolver.selector_cls(**selector_data)

        subject_document = SubjectDocument(**data["subject_document"])
        content_hash = ContentHash(**data["content_hash"])

        return Leaf(
            reference_id=data["reference_id"],
            subject_document=subject_document,
            selector=selector,
            content_hash=content_hash,
            captured_at=data["captured_at"],
        )
    except KeyError as exc:
        raise ReferenceDeserializationError(f"missing required field: {exc}") from exc
    except TypeError as exc:
        raise ReferenceDeserializationError(f"malformed reference structure: {exc}") from exc
