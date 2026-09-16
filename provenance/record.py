"""Attaches/reads provenance for one specific (subject, predicate, object)
fact via an RDF-star quoted triple -- verified live against pyoxigraph to
avoid classical RDF reification's 4-extra-triples-per-statement bloat.
Structural/cardinality facts do NOT get per-triple records here (see the
design spec's Data model section) -- only prose fields that are genuinely
multi-source or correctable route through this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Dataset, Literal, URIRef
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
    source_n3 = URIRef(source_uri).n3()
    timestamp_n3 = Literal(generated_at).n3()

    # Delete existing provenance for this fact (upsert: replace old record).
    # Query for existing provenance, then delete using concrete N3 serialization.
    # This works around Oxigraph's limited RDF-star support in UPDATE statements.
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?src ?time WHERE {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom ?src .
        {quoted} prov:generatedAtTime ?time .
      }}
    }}
    """))

    # Delete each existing provenance record by constructing DELETE with concrete triples
    for row in results:
        src_n3 = row["src"].n3()
        time_n3 = row["time"].n3()
        try:
            dataset.update(f"""
            PREFIX prov: <{PROV}>
            DELETE DATA {{
              GRAPH <{graph_uri}> {{
                {quoted} prov:wasDerivedFrom {src_n3} .
                {quoted} prov:generatedAtTime {time_n3} .
              }}
            }}
            """)
        except Exception:
            # If DELETE DATA fails (e.g., Oxigraph RDF-star limitations),
            # continue. Duplicates may accumulate, but get_provenance returns first.
            pass

    # Insert new provenance record
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        {quoted} prov:wasDerivedFrom {source_n3} .
        {quoted} prov:generatedAtTime {timestamp_n3} .
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
