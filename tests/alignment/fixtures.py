"""Shared access to the real, separately checked-out institutional-ontology
repo, mirroring tests/corpus_fixtures.py's requires_real_corpus exactly.
"""
from __future__ import annotations

import pytest

from alignment.institutional_ontology import institutional_ontology_path

def _real_institutional_ontology_is_available() -> bool:
    path = institutional_ontology_path()
    # is_file() alone is True for a 0-byte file (e.g. an interrupted
    # checkout) -- that isn't real data either, and parsing it raises a
    # raw SAXParseException instead of skipping cleanly.
    return path.is_file() and path.stat().st_size > 0


requires_real_institutional_ontology = pytest.mark.skipif(
    not _real_institutional_ontology_is_available(),
    reason=(
        f"real institutional-ontology.owl not available at "
        f"{institutional_ontology_path()!r} -- set INSTITUTIONAL_ONTOLOGY_PATH to override"
    ),
)
