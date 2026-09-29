"""Lists every citable candidate across the whole real corpus, grouped by
family, by combining staleness_sweep's current-snapshot listing with
discover_candidates() per XSD family. See
docs/specs/2026-09-25-citation-workflow-design.md.
"""
from __future__ import annotations

from lxml import etree

from discovery.xsd_discoverer import DiscoveryResult, discover_candidates
from staleness_sweep.resolve import CorpusIntegrityError, list_current_families, resolve_family_location


def list_corpus_candidates(module_root: str) -> dict[str, DiscoveryResult]:
    result: dict[str, DiscoveryResult] = {}
    for family in list_current_families(module_root):
        try:
            location = resolve_family_location(module_root, family)
        except CorpusIntegrityError:
            # One family's manifest entry being broken (missing file,
            # escaping path) must not take down the listing for every
            # OTHER, healthy family.
            continue
        if location is None:
            continue
        # A filename-extension check, even though staleness_sweep's own
        # docstring says "no filename parsing anywhere" -- that guarantee
        # is about *resolving* a family's location, which never inspects
        # the name. This check decides which already-resolved families
        # discover_candidates() (XSD-only) can even attempt; it would
        # misclassify a manifest entry that points at non-XML content
        # named with a ".xsd" extension, or a real schema under a
        # different extension, but the real corpus has no such case today.
        if not location.retrieval_uri.endswith(".xsd"):
            continue
        try:
            result[family] = discover_candidates(location.retrieval_uri)
        except etree.XMLSyntaxError:
            # One corrupt XSD must not take down the listing for every
            # OTHER, well-formed family.
            continue
    return result
