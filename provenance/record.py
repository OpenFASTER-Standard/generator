"""Attaches/reads provenance for one specific (subject, predicate, object)
fact via an RDF-star quoted triple -- verified live against pyoxigraph to
avoid classical RDF reification's 4-extra-triples-per-statement bloat.
Structural/cardinality facts do NOT get per-triple records here (see the
design spec's Data model section) -- only prose fields that are genuinely
multi-source or correctable route through this module.
"""
from __future__ import annotations

import hashlib
import urllib.parse
from dataclasses import dataclass

from rdflib import BNode, Dataset, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.term import Node

from provenance.vocab import PROV


@dataclass(frozen=True)
class ProvenanceRecord:
    source_uri: str
    generated_at: str


def _n3(term: Node) -> str:
    return term.n3()


def _record_uri(graph_uri: str, subject: Node, predicate: Node, obj: Node) -> str:
    """Generate a deterministic, stable URI for the provenance record linked to this fact.

    Uses SHA256 of the fact's canonical N3 representation (plus the owning
    graph_uri) to ensure the same fact always maps to the same record URI,
    enabling proper upsert semantics despite RDF-star deduplication
    limitations in this pyoxigraph version.

    graph_uri is included in the hash key so the same fact in two different
    run graphs gets two distinct record URIs -- without it, get_provenance
    is graph-scoped today so the collision is harmless, but any future
    cross-run lineage query would silently conflate different runs'
    provenance for what looks like one entity.

    Uses .n3() serialization (not str()) to preserve language tags and datatypes
    on Literals — str() would drop these, causing language variants of the same
    documentation text to collide to the same record URI and overwrite provenance.
    """
    key = f"{graph_uri}|{subject.n3()}|{predicate.n3()}|{obj.n3()}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"https://purl.openfaster.org/provenance/record/{digest}"


def _reject_bnode(subject: Node, predicate: Node, obj: Node) -> None:
    """A blank node embedded in a SPARQL text pattern (as this module builds
    its queries) is a non-distinguished variable, not a fixed value -- it
    would silently match ANY term, returning arbitrary/wrong provenance
    instead of erroring. Per the design's own rule, structural
    (blank-node-rooted) facts get one blanket per-run citation, not
    per-triple provenance -- this API is only ever meant to be called with
    real, addressable subjects/predicates/objects.
    """
    for name, term in (("subject", subject), ("predicate", predicate), ("obj", obj)):
        if isinstance(term, BNode):
            raise TypeError(
                f"{name} is a BNode ({term!r}); attach_provenance/get_provenance "
                "only support real, addressable subjects/predicates/objects -- "
                "structural (blank-node-rooted) facts get one blanket "
                "per-run citation, not per-triple provenance (see the design "
                "spec's Data model section)"
            )


def attach_provenance(
    dataset: Dataset,
    graph_uri: str,
    subject: Node,
    predicate: Node,
    obj: Node,
    source_uri: str,
    generated_at: str,
) -> None:
    _reject_bnode(subject, predicate, obj)
    quoted = f"<< {_n3(subject)} {_n3(predicate)} {_n3(obj)} >>"
    record = _record_uri(graph_uri, subject, predicate, obj)
    # Percent-encode source_uri first -- a realistic source_uri built from a
    # real file path (e.g. one containing a space) makes plain
    # URIRef(source_uri).n3() raise rdflib's own bare, unfriendly exception
    # ("does not look like a valid URI ... Perhaps you wanted to
    # urlencode it?"), confirmed live. The safe set preserves the URI's own
    # structural characters so real URIs with query strings/fragments still
    # round-trip unchanged.
    try:
        encoded_source_uri = urllib.parse.quote(source_uri, safe=":/?=&#")
        source_n3 = URIRef(encoded_source_uri).n3()
    except Exception as exc:
        raise ValueError(f"source_uri={source_uri!r} is not a valid URI even after percent-encoding") from exc
    timestamp_n3 = Literal(generated_at, datatype=XSD.dateTime).n3()

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
    # Note: unlike attach_provenance, get_provenance never calls
    # _record_uri directly -- it looks up the RDF-star link
    # (prov:hasProvenanceRecord) inside the caller's own GRAPH <{graph_uri}>
    # clause below, so it is already graph-scoped by construction.
    _reject_bnode(subject, predicate, obj)
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
