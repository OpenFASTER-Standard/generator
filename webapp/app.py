"""Serves the references catalog: one JSON API endpoint, one static page
that renders it. See docs/specs/2026-09-24-references-catalog-design.md
and docs/specs/2026-09-24-catalog-write-path-design.md.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from references_catalog.catalog import load_catalog

DEFAULT_CATALOG_PATH = "/work/ontologies/mikadiv-fm/references.json"

app = FastAPI()


def _catalog_path() -> Path:
    # Read at call time, not import time, so tests can override it via
    # REFERENCES_CATALOG_PATH without needing a fresh process per test.
    return Path(os.environ.get("REFERENCES_CATALOG_PATH", DEFAULT_CATALOG_PATH))


@app.get("/api/references")
def list_references() -> dict:
    return load_catalog(str(_catalog_path()))


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
