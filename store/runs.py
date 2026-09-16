"""Each extraction run is written as one immutable named graph, never
mutated afterward -- that immutability is itself provenance (you can
always see exactly what a given run believed). Real content hashes (not
just paths) are recorded so a later run can be told apart from an
identical re-run of the same inputs.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import XSD

RUNS = Namespace("https://purl.openfaster.org/runs/")


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    graph_uri: str
    xsd_path: str
    xsd_hash: str
    pdf_path: str
    pdf_hash: str
    created_at: str


def _sha256_of_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write_run(
    dataset: Dataset,
    run_id: str,
    graph: Graph,
    xsd_path: str,
    pdf_path: str,
    created_at: str,
) -> RunInfo:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    if any(index.subjects(RUNS.runId, Literal(run_id))):
        raise ValueError(f"a run with run_id={run_id!r} already exists")

    graph_uri = str(RUNS[run_id])

    # Canonicalize blank-node labels before copying into the named graph.
    # extraction.extract()'s real output is heavily blank-node-shaped
    # (freshly, randomly labeled per call) -- without this, diff_runs's
    # FILTER NOT EXISTS never matches a blank-node triple across two runs
    # of the identical corpus, reporting thousands of phantom changes.
    # to_canonical_graph returns a read-only graph aggregate; iterating
    # its .triples((None, None, None)) yields real, usable
    # BNode/URIRef/Literal terms just like a normal Graph.
    canonical_graph = to_canonical_graph(graph)
    run_graph = dataset.graph(URIRef(graph_uri))
    for triple in canonical_graph.triples((None, None, None)):
        run_graph.add(triple)

    info = RunInfo(
        run_id=run_id,
        graph_uri=graph_uri,
        xsd_path=xsd_path,
        xsd_hash=_sha256_of_file(xsd_path),
        pdf_path=pdf_path,
        pdf_hash=_sha256_of_file(pdf_path),
        created_at=created_at,
    )

    subject = URIRef(graph_uri)
    index.add((subject, RUNS.runId, Literal(info.run_id)))
    index.add((subject, RUNS.xsdPath, Literal(info.xsd_path)))
    index.add((subject, RUNS.xsdHash, Literal(info.xsd_hash)))
    index.add((subject, RUNS.pdfPath, Literal(info.pdf_path)))
    index.add((subject, RUNS.pdfHash, Literal(info.pdf_hash)))
    index.add((subject, RUNS.createdAt, Literal(info.created_at, datatype=XSD.dateTime)))

    return info


def list_runs(dataset: Dataset) -> list[RunInfo]:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    runs = []
    for subject in set(index.subjects(RUNS.runId, None)):
        runs.append(
            RunInfo(
                run_id=str(index.value(subject, RUNS.runId)),
                graph_uri=str(subject),
                xsd_path=str(index.value(subject, RUNS.xsdPath)),
                xsd_hash=str(index.value(subject, RUNS.xsdHash)),
                pdf_path=str(index.value(subject, RUNS.pdfPath)),
                pdf_hash=str(index.value(subject, RUNS.pdfHash)),
                created_at=str(index.value(subject, RUNS.createdAt)),
            )
        )
    runs.sort(key=lambda r: r.created_at)
    return runs


@dataclass(frozen=True)
class RunDiff:
    added: list[tuple[str, str, str]]
    removed: list[tuple[str, str, str]]


def _run_graph_uri(dataset: Dataset, run_id: str) -> str:
    index = dataset.graph(URIRef(str(RUNS["index"])))
    for subject in index.subjects(RUNS.runId, Literal(run_id)):
        return str(subject)
    raise ValueError(f"no run with run_id={run_id!r}")


def diff_runs(dataset: Dataset, run_id_a: str, run_id_b: str) -> RunDiff:
    graph_uri_a = _run_graph_uri(dataset, run_id_a)
    graph_uri_b = _run_graph_uri(dataset, run_id_b)

    removed_query = f"""
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri_a}> {{ ?s ?p ?o }}
      FILTER NOT EXISTS {{ GRAPH <{graph_uri_b}> {{ ?s ?p ?o }} }}
    }}
    """
    added_query = f"""
    SELECT ?s ?p ?o WHERE {{
      GRAPH <{graph_uri_b}> {{ ?s ?p ?o }}
      FILTER NOT EXISTS {{ GRAPH <{graph_uri_a}> {{ ?s ?p ?o }} }}
    }}
    """
    removed = [(str(r["s"]), str(r["p"]), str(r["o"])) for r in dataset.query(removed_query)]
    added = [(str(r["s"]), str(r["p"]), str(r["o"])) for r in dataset.query(added_query)]
    return RunDiff(added=added, removed=removed)
