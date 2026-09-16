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
    graph_uri = str(RUNS[run_id])
    run_graph = dataset.graph(URIRef(graph_uri))
    for triple in graph.triples((None, None, None)):
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

    index = dataset.graph(URIRef(str(RUNS["index"])))
    subject = URIRef(graph_uri)
    index.add((subject, RUNS.runId, Literal(info.run_id)))
    index.add((subject, RUNS.xsdPath, Literal(info.xsd_path)))
    index.add((subject, RUNS.xsdHash, Literal(info.xsd_hash)))
    index.add((subject, RUNS.pdfPath, Literal(info.pdf_path)))
    index.add((subject, RUNS.pdfHash, Literal(info.pdf_hash)))
    index.add((subject, RUNS.createdAt, Literal(info.created_at)))

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
