"""Serializes a Reference to a plain JSON-safe dict. See
docs/specs/2026-09-24-references-catalog-design.md.
"""
from __future__ import annotations

import dataclasses

from reference_model.model import Reference


def to_json_dict(reference: Reference) -> dict:
    return dataclasses.asdict(reference)
