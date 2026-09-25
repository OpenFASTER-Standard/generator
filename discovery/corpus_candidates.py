"""Lists every citable candidate across the whole real corpus, grouped by
family, by combining staleness_sweep's current-snapshot listing with
discover_candidates() per XSD family. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass

from discovery.xsd_discoverer import discover_candidates
from staleness_sweep.resolve import list_current_locations


@dataclass(frozen=True)
class CorpusCandidate:
    tag: str
    name: str
    xpath: str


def list_corpus_candidates(module_root: str) -> dict[str, list[CorpusCandidate]]:
    result: dict[str, list[CorpusCandidate]] = {}
    for location in list_current_locations(module_root):
        if not location.retrieval_uri.endswith(".xsd"):
            continue
        discovery_result = discover_candidates(location.retrieval_uri)
        result[location.family] = [
            CorpusCandidate(tag=c.tag, name=c.name, xpath=c.xpath)
            for c in discovery_result.candidates
        ]
    return result
