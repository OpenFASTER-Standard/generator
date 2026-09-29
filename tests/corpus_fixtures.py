"""Shared access to the real MiKaDiv-FM corpus (a separate repo,
`ontologies`, checked out alongside this one) that many tests exercise
directly rather than only through synthetic fixtures -- deliberately, since
testing against real source material is a real strength of this project
(see docs/specs/2026-09-23-source-reference-model-design.md and others).

The path is overridable via MIKADIV_CORPUS_ROOT so a CI runner (or any
environment without that sibling checkout) can point it elsewhere; when
it isn't available at all, `requires_real_corpus` skips rather than
failing opaquely with an empty/wrong result. See the 2026-09-29 audit
finding on this exact gap.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REAL_CORPUS_ROOT = os.environ.get("MIKADIV_CORPUS_ROOT", "/work/ontologies/mikadiv-fm/sources")

requires_real_corpus = pytest.mark.skipif(
    not Path(REAL_CORPUS_ROOT).is_dir(),
    reason=f"real corpus not available at {REAL_CORPUS_ROOT!r} -- set MIKADIV_CORPUS_ROOT to override",
)
