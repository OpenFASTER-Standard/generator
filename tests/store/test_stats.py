import shutil

from rdflib import Literal, Namespace

from review.corrections import propose_correction
from store.database import open_store
from store.stats import build_triple_count_summary, categorize_predicate
from webapp.pipeline import run_pipeline_and_store

STORE_PATH = "/tmp/test_store_stats"
ROOT_XSD = "/work/ontologies/mikadiv-fm/sources/xsd/MiKaDiv_FM_1.02.xsd"
ANNEX_PDF = "/work/ontologies/mikadiv-fm/sources/khb/khb_mikadiv_fm_anlage_en_v3.pdf"
EX = Namespace("https://example.org/test#")


def test_categorize_predicate_puts_every_real_kind_where_it_belongs():
    assert categorize_predicate("https://purl.openfaster.org/xsdo/documentation") == "documentation"
    assert categorize_predicate("http://www.w3.org/ns/prov#hasProvenanceRecord") == "provenance"
    assert categorize_predicate("http://www.w3.org/ns/prov#wasDerivedFrom") == "provenance"
    assert categorize_predicate("http://www.w3.org/ns/prov#generatedAtTime") == "provenance"
    assert categorize_predicate("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies") == "provenance"
    # Everything else -- structural facts, rdf:type classification, and
    # per-run metadata -- falls into the one remaining bucket.
    assert categorize_predicate("https://purl.openfaster.org/xsdo/hasParticle") == "structural"
    assert categorize_predicate("http://www.w3.org/1999/02/22-rdf-syntax-ns#type") == "structural"
    assert categorize_predicate("https://purl.openfaster.org/runs/runId") == "structural"


def test_build_triple_count_summary_against_the_real_running_corpus():
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-18T12:00:00Z", created_at="2026-09-18T12:00:00Z",
        )

        summary = build_triple_count_summary(dataset)

        assert summary["total"] > 0
        category_keys = {c["key"] for c in summary["categories"]}
        assert category_keys == {"documentation", "provenance", "structural"}

        by_key = {c["key"]: c for c in summary["categories"]}
        # Documentation is exactly one predicate: xsdo:documentation.
        assert by_key["documentation"]["count"] > 0
        assert [p["label"] for p in by_key["documentation"]["predicates"]] == ["xsdo:documentation"]

        # Provenance is real RDF-star bookkeeping -- 4 triples per citable
        # fact (hasProvenanceRecord, wasDerivedFrom, generatedAtTime,
        # reifies), so its total must be exactly 4x any one of its own
        # predicate's count, and a real multiple of the number of citable
        # facts, not an arbitrary number.
        provenance_predicate_counts = {p["label"]: p["count"] for p in by_key["provenance"]["predicates"]}
        assert set(provenance_predicate_counts) == {
            "prov:hasProvenanceRecord", "prov:wasDerivedFrom", "prov:generatedAtTime", "rdf:reifies",
        }
        assert len(set(provenance_predicate_counts.values())) == 1  # all four are equal, by construction

        # Structural facts must include real, distinct labels for the two
        # different real "type" predicates this store has (xsdo:type,
        # 272 in this corpus, and rdf:type, 561) -- confirmed they don't
        # collide into a single ambiguous "type" label.
        structural_labels = {p["label"] for p in by_key["structural"]["predicates"]}
        assert "xsdo:type" in structural_labels
        assert "rdf:type" in structural_labels

        # The whole summary must reconcile: category counts sum to the total.
        assert sum(c["count"] for c in summary["categories"]) == summary["total"]
        # And every predicate's own count sums to its category's count.
        for category in summary["categories"]:
            assert sum(p["count"] for p in category["predicates"]) == category["count"]
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)


def test_build_triple_count_summary_covers_every_real_stored_triple_not_a_subset():
    # The whole point of this view is "does this account for everything
    # actually in the store" -- so this test verifies that claim directly,
    # against a COMPLETELY INDEPENDENT count that shares no code path with
    # build_triple_count_summary's own SPARQL query: plain
    # dataset.contexts() (the real rdflib/oxrdflib Python API, not SPARQL
    # at all) enumerating every named graph and summing len(graph) per
    # graph. If the two ever disagree, the SPARQL query itself (not just
    # the categorization logic the other test above already covers) has a
    # real gap -- e.g. missing a graph, or a GRAPH ?g pattern silently
    # excluding the default graph if something were ever written there.
    #
    # Exercises three real graphs, not just one: the run's own extraction
    # graph, the runs index, AND a genuine corrections graph (a real,
    # separate named graph a documented run alone never touches) -- this
    # is deliberately the scenario a narrower single-graph test would miss.
    shutil.rmtree(STORE_PATH, ignore_errors=True)
    dataset = open_store(STORE_PATH, create=True)
    try:
        run_pipeline_and_store(
            dataset, xsd_path=ROOT_XSD, pdf_path=ANNEX_PDF,
            run_id="2026-09-18T13:00:00Z", created_at="2026-09-18T13:00:00Z",
        )
        propose_correction(
            dataset, graph_uri="https://purl.openfaster.org/review/graph/corrections",
            target_subject=EX.SomeSubject, target_predicate=EX.documentation, target_language="de",
            proposed_value="A test correction.", prior_value=Literal("Original.", lang="de"),
            proposer="test-proposer", reason="covering the corrections graph too",
            generated_at="2026-09-18T13:05:00Z",
        )

        summary = build_triple_count_summary(dataset)

        independent_total = sum(len(graph) for graph in dataset.contexts())
        # Sanity: this really did exercise more than one named graph --
        # otherwise this test wouldn't be testing what it claims to.
        real_graph_count = sum(1 for graph in dataset.contexts() if len(graph) > 0)
        assert real_graph_count >= 3

        assert summary["total"] == independent_total
    finally:
        dataset.close()
        shutil.rmtree(STORE_PATH, ignore_errors=True)
