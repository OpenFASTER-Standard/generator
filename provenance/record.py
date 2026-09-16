"""Attaches/reads provenance for one specific (subject, predicate, object)
fact via an RDF-star quoted triple -- verified live against pyoxigraph to
avoid classical RDF reification's 4-extra-triples-per-statement bloat.
Structural/cardinality facts do NOT get per-triple records here (see the
design spec's Data model section) -- only prose fields that are genuinely
multi-source or correctable route through this module.
"""
from __future__ import annotations

import hashlib
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


def _record_uri(subject: Node, predicate: Node, obj: Node) -> str:
    """Generate a deterministic, stable URI for the provenance record linked to this fact.

    Uses SHA256 of the fact's canonical representation to ensure the same fact
    always maps to the same record URI, enabling proper upsert semantics despite
    RDF-star deduplication limitations in this pyoxigraph version.
    """
    key = f"{subject}|{predicate}|{obj}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"https://purl.openfaster.org/provenance/record/{digest}"


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
    record = _record_uri(subject, predicate, obj)
    source_n3 = URIRef(source_uri).n3()
    timestamp_n3 = Literal(generated_at).n3()

    # Clear any prior provenance values for this fact's record. Ordinary
    # (non-RDF-star) triples -- DELETE/WHERE works reliably for these.
    # RDF-star patterns inside a DELETE/WHERE template are rejected by
    # this pyoxigraph version (confirmed live, "expected GRAPH" syntax
    # error, regardless of GRAPH-wrapping or pattern count) -- that's
    # why the RDF-star link below is never deleted/rewritten, only
    # conditionally inserted once.
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    DELETE {{
      GRAPH <{graph_uri}> {{
        <{record}> prov:wasDerivedFrom ?oldSrc .
        <{record}> prov:generatedAtTime ?oldTime .
      }}
    }}
    WHERE {{
      GRAPH <{graph_uri}> {{
        OPTIONAL {{ <{record}> prov:wasDerivedFrom ?oldSrc . }}
        OPTIONAL {{ <{record}> prov:generatedAtTime ?oldTime . }}
      }}
    }}
    """)

    # Link the fact to its stable, deterministic record -- only once ever.
    # Re-inserting an identical RDF-star triple was confirmed live to
    # create a true duplicate rather than deduplicating, so this must be
    # conditional, not a plain repeated INSERT DATA.
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT {{ GRAPH <{graph_uri}> {{ {quoted} prov:hasProvenanceRecord <{record}> . }} }}
    WHERE {{
      FILTER NOT EXISTS {{ GRAPH <{graph_uri}> {{ {quoted} prov:hasProvenanceRecord <{record}> . }} }}
    }}
    """)

    # Write the new provenance values (ordinary triples about the record).
    dataset.update(f"""
    PREFIX prov: <{PROV}>
    INSERT DATA {{
      GRAPH <{graph_uri}> {{
        <{record}> prov:wasDerivedFrom {source_n3} .
        <{record}> prov:generatedAtTime {timestamp_n3} .
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
        {quoted} prov:hasProvenanceRecord ?record .
        ?record prov:wasDerivedFrom ?src ; prov:generatedAtTime ?time .
      }}
    }}
    """))
    if not results:
        return None
    row = results[0]
    return ProvenanceRecord(source_uri=str(row["src"]), generated_at=str(row["time"]))
