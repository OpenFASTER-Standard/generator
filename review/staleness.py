"""A correction is only ever silently applied, or silently flagged --
never silently misapplied. If the real value in a new run no longer
matches what an approved correction was originally made against, that
correction is stale and must be surfaced for re-review, not re-applied
as if nothing changed.
"""
from __future__ import annotations

from rdflib import Dataset, URIRef

from provenance.vocab import PROV
from review.current_view import get_correction_status


def _revision_of_value(dataset: Dataset, corrections_graph_uri: str, correction_uri: str):
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?s ?p ?priorValue WHERE {{
      GRAPH <{corrections_graph_uri}> {{
        <{correction_uri}> prov:wasRevisionOf << ?s ?p ?priorValue >> .
      }}
    }}
    """))
    if not results:
        raise ValueError(f"correction {correction_uri!r} has no prov:wasRevisionOf record")
    row = results[0]
    return URIRef(str(row["s"])), URIRef(str(row["p"])), row["priorValue"]


def is_correction_stale(
    dataset: Dataset, corrections_graph_uri: str, new_run_graph_uri: str, correction_uri: str
) -> bool:
    if get_correction_status(dataset, corrections_graph_uri, correction_uri) != "approved":
        return False

    subject, predicate, prior_value = _revision_of_value(dataset, corrections_graph_uri, correction_uri)

    new_run_graph = dataset.graph(URIRef(new_run_graph_uri))
    current_raw_values = list(new_run_graph.objects(subject, predicate))
    return prior_value not in current_raw_values
