"""Serializes a Reference to a plain JSON-safe dict. See
docs/specs/2026-09-24-references-catalog-design.md.
"""
from __future__ import annotations

import dataclasses
import json

from reference_model.model import Reference


def to_json_dict(reference: Reference) -> dict:
    # dataclasses.asdict() reconstructs Union.parts (a tuple field) as a
    # tuple, not a list -- round-tripping through json once here normalizes
    # every sequence to what json.loads() would produce anyway, so a
    # caller's own round-trip never disagrees with this function's output.
    return json.loads(json.dumps(dataclasses.asdict(reference)))
