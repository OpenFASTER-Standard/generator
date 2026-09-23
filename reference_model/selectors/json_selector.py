"""JsonSelector: addresses a value inside a JSON document via a real
standard, RFC 6901 JSON Pointer -- the JSON analogue of XPath. Unlike
XPath, a JSON Pointer always addresses exactly zero or one location, so
this selector's resolve() only ever returns RESOLVED or NOT_FOUND;
AMBIGUOUS/UNCITABLE never occur.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from reference_model.model import ResolutionOutcome, Status
from reference_model.registry import Resolver, register


@dataclass(frozen=True)
class JsonSelector:
    type: str
    pointer: str  # RFC 6901 JSON Pointer, e.g. "/verdict" or "" for the whole document

    @staticmethod
    def create(pointer: str) -> "JsonSelector":
        return JsonSelector(type="JsonSelector", pointer=pointer)


def _resolve_pointer(document, pointer: str):
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON Pointer (must start with '/'): {pointer!r}")

    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")  # RFC 6901 escaping
        if isinstance(current, dict):
            current = current[token]  # raises KeyError if missing
        elif isinstance(current, list):
            current = current[int(token)]  # raises ValueError (non-numeric) or IndexError
        else:
            raise KeyError(token)  # can't descend further into a scalar
    return current


def resolve(selector: JsonSelector, retrieval_uri: str) -> ResolutionOutcome:
    try:
        with open(retrieval_uri, encoding="utf-8") as f:
            document = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ResolutionOutcome(status=Status.NOT_FOUND)

    try:
        value = _resolve_pointer(document, selector.pointer)
    except (KeyError, IndexError, ValueError):
        return ResolutionOutcome(status=Status.NOT_FOUND)

    return ResolutionOutcome(status=Status.RESOLVED, raw_content=value)


def canonicalize_and_hash(raw_content) -> str:
    # JCS-inspired (sorted keys, no incidental whitespace), not byte-exact
    # RFC 8785 -- no ECMAScript number formatting. Review-result documents
    # are all strings, so this doesn't matter in practice.
    canonical = json.dumps(raw_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


register("JsonSelector", Resolver(resolve=resolve, canonicalize_and_hash=canonicalize_and_hash))
