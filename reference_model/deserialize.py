"""Deserializes a plain JSON-safe dict (as produced by
reference_model.serialize.to_json_dict()) back into a real Reference.
See docs/specs/2026-09-29-webapp-react-rebuild-design.md.
"""
from __future__ import annotations

from reference_model.model import ContentHash, Leaf, Reference, SubjectDocument, Union
from reference_model.selectors.json_selector import JsonSelector
from reference_model.selectors.svg_selector import SvgSelector
from reference_model.selectors.xpath_selector import XPathSelector

_SELECTOR_TYPES = {
    "XPathSelector": XPathSelector,
    "JsonSelector": JsonSelector,
    "SvgSelector": SvgSelector,
}


class ReferenceDeserializationError(Exception):
    pass


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
        if selector_type not in _SELECTOR_TYPES:
            raise ReferenceDeserializationError(f"unknown selector type: {selector_type!r}")
        selector_cls = _SELECTOR_TYPES[selector_type]
        selector = selector_cls(**selector_data)

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
