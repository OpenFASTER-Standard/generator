"""Answers "what was derived from this source location" -- the reverse
of provenance.record.get_provenance, which only ever answers "where did
this fact come from." Needed for Synced Panes mode's source-to-derived
direction (see the design spec).

The query shape -- a variable RDF-star triple used as a subject,
`<<?s ?p ?o>> prov:hasProvenanceRecord ?record` -- was verified live
against the real demo store (not assumed) before this module was written:
this pyoxigraph version supports it and returns correct results. This is
the same GRAPH-scoped SPARQL string-building style already used by
provenance.record and review.corrections in this codebase.
"""
from __future__ import annotations

import re
import urllib.parse

from rdflib import Dataset, Literal

from citations.locator import SourceLocator, locator_lookup_key
from provenance.vocab import PROV


def find_facts_by_locator(
    dataset: Dataset, graph_uri: str, locator: SourceLocator
) -> list[tuple[str, str, str]]:
    # Percent-encode the same way attach_provenance encodes source_uri
    # before storing it (urllib.parse.quote(..., safe=":/?=&#")) -- for
    # every real path in this corpus (no spaces) this is a no-op, but
    # matching the encoding exactly keeps this correct if that ever
    # changes, rather than relying on it being a no-op by accident.
    key = urllib.parse.quote(locator_lookup_key(locator), safe=":/?=&#")
    # REGEX with a real anchor (a following "&" or end-of-string), not a
    # plain substring match -- confirmed live during this plan's own
    # design that a naive CONTAINS/STRSTARTS check on "page=196" would
    # also match "page=1960". re.escape handles the locator's own special
    # regex characters (e.g. XSD component qnames contain "{", "}").
    pattern = re.escape(key) + r"(&|$)"
    # re.escape's own backslash-escapes (e.g. "\?", "\.", "\{") are NOT
    # valid SPARQL string-literal escapes (SPARQL's ECHAR grammar only
    # allows \t\b\n\r\f\"\'\\) -- confirmed live: embedding the pattern
    # via a plain f-string '"{pattern}"' raises a SPARQL SyntaxError
    # ("expected one of ENCODE_FOR_URI, ['t'|'b'|'n'|'r'|'f'|'"'|'\''|'\\']")
    # the moment the locator's key contains any re.escape'd character.
    # rdflib's Literal(...).n3() produces a correctly-escaped SPARQL/Turtle
    # string literal instead of hand-rolling the quoting.
    pattern_n3 = Literal(pattern).n3()
    results = list(dataset.query(f"""
    PREFIX prov: <{PROV}>
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri}> {{
        ?record prov:wasDerivedFrom ?src .
        FILTER(REGEX(STR(?src), {pattern_n3}))
        <<?s ?p ?o>> prov:hasProvenanceRecord ?record .
      }}
    }}
    """))
    return [(str(row["s"]), str(row["p"]), str(row["o"])) for row in results]
