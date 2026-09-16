"""Attaches/reads provenance for one specific (subject, predicate, object)
fact via an RDF-star quoted triple -- verified live against pyoxigraph to
avoid classical RDF reification's 4-extra-triples-per-statement bloat.
Structural/cardinality facts do NOT get per-triple records here (see the
design spec's Data model section) -- only prose fields that are genuinely
multi-source or correctable route through this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Dataset
from rdflib.term import Node

from provenance.vocab import PROV


@dataclass(frozen=True)
class ProvenanceRecord:
    source_uri: str
    generated_at: str


def _n3(term: Node) -> str:
    return term.n3()


def attach_provenance(
    dataset: Dataset,
    graph_uri: str,
    subject: Node,
    predicate: Node,
    obj: Node,
    source_uri: str,
    generated_at: str,
) -> None:
    quoted = f"<< {_n3(subject)} {_n3(predicate)} {_n3(obj)} >>"
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom <{source_uri}> .
        {quoted} prov:generatedAtTime "{generated_at}" .
      }}
    }}
    """)


def get_provenance(
    dataset: Dataset,
    graph_uri: str,
    subject: Node,
    predicate: Node,
    obj: Node,
) -> ProvenanceRecord | None:
    quoted = f"<< {_n3(subject)} {_n3(predicate)} {_n3(obj)} >>"
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?src ?time WHERE {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom ?src .
        {quoted} prov:generatedAtTime ?time .
      }}
    }}
    """))
    if not results:
        return None
    row = results[0]
    return ProvenanceRecord(source_uri=str(row["src"]), generated_at=str(row["time"]))
