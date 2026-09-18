"""Enumerates every real source file a run actually touches (every XSD
file the schema includes/imports, plus the annex PDF), for the Sources
tab and Synced Panes' source picker -- both of which need the FULL file
list, not just the one root XSD path `RunInfo`/`RunSummary` track (see
this module's own `list_xsd_files` docstring for why the root path alone
was never enough).

Also converts a real filesystem path under this box's `/work/ontologies`
checkout into the actual, permanent GitHub URL for that same file --
this deployment's own corpus IS a real, single GitHub repo (see
`ONTOLOGIES_GITHUB_REPO` below), not a synthetic fixture, so a real user
can click through to see the exact same content on GitHub instead of a
local-filesystem path that means nothing off this box.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import url2pathname

import xmlschema


# This box's own checkout of the real corpus repo, and the exact remote
# it was cloned from -- confirmed live (`git remote -v` in
# /work/ontologies) at the time this module was written. Hardcoded, not
# derived from `git remote` at request time: this deployment has exactly
# one corpus repo, matching the existing pragmatic convention already
# used throughout this project for real, fixed corpus paths (e.g.
# webapp/main.py's `_e2e_app`).
ONTOLOGIES_REPO_ROOT = "/work/ontologies"
ONTOLOGIES_GITHUB_REPO = "https://github.com/OpenFASTER-Standard/ontologies"
ONTOLOGIES_GITHUB_BRANCH = "main"


@dataclass(frozen=True)
class SourceFile:
    path: str
    kind: str
    github_url: str | None


def infer_kind(path: str) -> str:
    """The source kind, from the file's own extension -- not a caller-
    supplied label. A `.pdf` is always the "pdf" plugin's kind; every
    other extension (in practice: `.xsd`) is "xsd" for this corpus, but
    written as "not pdf" rather than "must be .xsd" so a genuinely new
    XSD-adjacent extension in a future corpus (`.xsd_bak`, `.xml`) doesn't
    need this function to know its exact spelling in advance.
    """
    return "pdf" if path.lower().endswith(".pdf") else "xsd"


def github_url_for(path: str) -> str | None:
    """None for any path outside the one real corpus repo this box has
    checked out -- callers must handle a file with no public source
    (there isn't one in this corpus today, but this stays honest rather
    than assuming every path is repo-relative).
    """
    repo_root = os.path.normpath(ONTOLOGIES_REPO_ROOT) + os.sep
    normalized = os.path.normpath(path)
    if not normalized.startswith(repo_root):
        return None
    relative = normalized[len(repo_root):]
    return f"{ONTOLOGIES_GITHUB_REPO}/blob/{ONTOLOGIES_GITHUB_BRANCH}/{relative}"


def list_xsd_files(xsd_path: str) -> list[str]:
    """Every real XSD file the schema rooted at `xsd_path` actually
    includes/imports -- not just that one root file. Real, confirmed
    necessary: this corpus's root file (MiKaDiv_FM_1.02.xsd) itself
    carries no element/type definitions of its own; it exists purely to
    `xs:import` 10 other real files (Personentypen, Standardtypen, one
    file per Meldeart, etc.) that hold everything the extractor and every
    citation actually point into. Listing only the root file, the way
    `RunInfo`/`RunSummary` track it, made every one of those files
    unreachable from the UI.

    `xmlschema.XMLSchema(xsd_path).maps.schemas` also carries the
    handful of built-in schemas the library bundles with itself
    (XMLSchema.xsd, xml.xsd, XMLSchema-instance.xsd, resolved from
    xmlschema's own install directory, not this corpus) -- filtered out
    by keeping only paths actually under this corpus's own repo root.
    """
    schema = xmlschema.XMLSchema(xsd_path)
    repo_root = os.path.normpath(ONTOLOGIES_REPO_ROOT) + os.sep
    paths = set()
    for sub_schema in schema.maps.schemas:
        real_path = url2pathname(urlparse(sub_schema.url).path)
        if real_path.startswith(repo_root):
            paths.add(real_path)
    return sorted(paths)


def list_source_files(xsd_path: str, pdf_path: str) -> list[SourceFile]:
    paths = [*list_xsd_files(xsd_path), pdf_path]
    return [SourceFile(path=path, kind=infer_kind(path), github_url=github_url_for(path)) for path in paths]
