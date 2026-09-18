"""A one-glimpse, honest accounting of what this store actually holds --
literally how many RDF triples exist for each real kind of thing, across
every named graph in the dataset (the run's own extraction graph, the
runs index, corrections/provenance if any have been recorded). Answers
"where does all this data actually live" directly from the real store,
not from any one materialized view.

Every fact this project stores falls into exactly one of three real
categories -- confirmed against this corpus's own actual predicate list,
not guessed:

- **Documentation text** (`xsdo:documentation`) -- the human-readable
  German/English strings every other view in this app is built around.
- **Provenance & citations** (`prov:hasProvenanceRecord`,
  `prov:wasDerivedFrom`, `prov:generatedAtTime`, `rdf:reifies`) -- the
  RDF-star bookkeeping every citation this app renders comes from. Real,
  confirmed live on the actual corpus: this is a genuinely large slice
  (a citable fact needs 4 of these triples for every 1 documentation
  triple it backs), not a rounding error -- worth surfacing honestly
  rather than folding into "structural facts" where it would hide.
- **Structural schema facts** -- everything else: the XSD content
  model itself (`xsdo:hasParticle`, `xsdo:type`, `xsdo:extends`, etc.),
  `rdf:type` classification triples, and the handful of per-run metadata
  triples (`https://purl.openfaster.org/runs/*`) -- kept in this same
  bucket rather than its own category since it's under 1% of the total
  in every real run so far and would otherwise need a 4th categorical
  color slot this design's own validated palette doesn't have room for
  (see the frontend's own TripleCountsTreemap component).
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, Dataset

from extraction.documentation import XSDO
from provenance.vocab import PROV

# rdflib's own bundled RDF namespace doesn't define `reifies` (it's a
# newer RDF-star-era term outside the closed vocabulary rdflib ships),
# so it's built directly rather than via RDF.reifies -- this is the
# real, correct predicate: RDF-star's own "this quoted-triple's real
# (s, p, o) is reified by this record" relationship, the same one
# review/current_view.py's own comment on synthetic (BNode, rdf:reifies,
# (s, p, o)) triples describes.
_RDF_REIFIES = str(RDF) + "reifies"

_PROVENANCE_PREDICATES = {
    str(PROV.hasProvenanceRecord),
    str(PROV.wasDerivedFrom),
    str(PROV.generatedAtTime),
    _RDF_REIFIES,
}


@dataclass(frozen=True)
class PredicateCount:
    predicate: str
    label: str
    count: int


@dataclass(frozen=True)
class CategoryCount:
    key: str
    label: str
    count: int
    predicates: list[PredicateCount]


# A short, human prefix per real namespace this store's predicates use --
# not just the bare local name, since that collides for real: xsdo:type
# and rdf:type are two different, real predicates in this store (272 and
# 561 triples respectively) that would otherwise both display as the
# single word "type".
_KNOWN_PREFIXES = {
    str(XSDO): "xsdo",
    str(PROV): "prov",
    str(RDF): "rdf",
    "https://purl.openfaster.org/runs/": "runs",
}


def _label_for(predicate: str) -> str:
    for namespace, prefix in _KNOWN_PREFIXES.items():
        if predicate.startswith(namespace):
            return f"{prefix}:{predicate[len(namespace):]}"
    for separator in ("#", "/"):
        if separator in predicate:
            return predicate.rsplit(separator, 1)[-1]
    return predicate


def categorize_predicate(predicate: str) -> str:
    if predicate == str(XSDO.documentation):
        return "documentation"
    if predicate in _PROVENANCE_PREDICATES:
        return "provenance"
    return "structural"


def count_triples_by_predicate(dataset: Dataset) -> list[PredicateCount]:
    """Every real predicate in the store and how many triples use it,
    across every named graph -- not scoped to one run's own graph, since
    the honest question here is "what does this whole store hold," not
    "what does the latest run's own view show."
    """
    results = dataset.query("""
    SELECT ?p (COUNT(*) AS ?cnt) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?p ORDER BY DESC(?cnt)
    """)
    return [
        PredicateCount(predicate=str(row["p"]), label=_label_for(str(row["p"])), count=int(row["cnt"]))
        for row in results
    ]


_CATEGORY_LABELS = {
    "documentation": "Documentation text",
    "provenance": "Provenance & citations",
    "structural": "Structural schema facts",
}


def build_triple_count_summary(dataset: Dataset) -> dict:
    predicate_counts = count_triples_by_predicate(dataset)
    by_category: dict[str, list[PredicateCount]] = {"documentation": [], "provenance": [], "structural": []}
    for predicate_count in predicate_counts:
        by_category[categorize_predicate(predicate_count.predicate)].append(predicate_count)

    categories = [
        CategoryCount(
            key=key,
            label=_CATEGORY_LABELS[key],
            count=sum(p.count for p in predicates),
            predicates=predicates,
        )
        for key, predicates in by_category.items()
        if predicates
    ]
    categories.sort(key=lambda c: c.count, reverse=True)

    return {
        "total": sum(c.count for c in categories),
        "categories": [
            {
                "key": category.key,
                "label": category.label,
                "count": category.count,
                "predicates": [
                    {"predicate": p.predicate, "label": p.label, "count": p.count} for p in category.predicates
                ],
            }
            for category in categories
        ],
    }
