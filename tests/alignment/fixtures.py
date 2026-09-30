"""Shared access to the real, separately checked-out institutional-ontology
repo, mirroring tests/corpus_fixtures.py's requires_real_corpus exactly.
"""
from __future__ import annotations

import pytest

from alignment.institutional_ontology import institutional_ontology_path

requires_real_institutional_ontology = pytest.mark.skipif(
    not institutional_ontology_path().is_file(),
    reason=(
        f"real institutional-ontology.owl not available at "
        f"{institutional_ontology_path()!r} -- set INSTITUTIONAL_ONTOLOGY_PATH to override"
    ),
)
