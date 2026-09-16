from rdflib import RDF, Graph, Literal
from rdflib.namespace import XSD

from review.validate import validate_graph
from review.vocab import REVIEW
from provenance.vocab import PROV


def test_a_correction_with_status_proposed_conforms():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_correction_with_an_invalid_status_value_does_not_conform():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("bogus")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_with_a_valid_outcome_conforms():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-someone"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_decision_with_outcome_proposed_does_not_conform():
    graph = Graph()
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("proposed")))
    graph.add((decision, REVIEW.decides, REVIEW["correction-1"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_by_the_same_agent_that_proposed_the_correction_does_not_conform():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_by_a_different_agent_conforms():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-someone-else"]))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_correction_with_an_ill_formed_generated_at_time_does_not_conform():
    """Important whole-branch-review finding: generated_at was never validated
    as a real timestamp -- junk strings (e.g. "not-a-timestamp") were silently
    accepted and stored as xsd:dateTime-typed literals, corrupting every
    ordering-dependent guarantee in this package (SPARQL ORDER BY DESC(?time),
    get_correction_status's sort). Note: constructing this Literal doesn't
    itself raise -- rdflib doesn't validate datatype/lexical-form match at
    construction time -- so the SHACL validation step below is what must
    catch it."""
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    graph.add((correction, PROV.generatedAtTime, Literal("not-a-timestamp", datatype=XSD.dateTime)))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_decision_with_an_ill_formed_generated_at_time_does_not_conform():
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    graph.add((decision, PROV.wasAttributedTo, REVIEW["reviewer-someone-else"]))
    graph.add((decision, PROV.generatedAtTime, Literal("not-a-timestamp", datatype=XSD.dateTime)))

    conforms, _ = validate_graph(graph)

    assert conforms is False


def test_a_correction_with_a_well_formed_generated_at_time_still_conforms():
    """Regression guard alongside the ill-formed-timestamp test above: a
    real, well-formed xsd:dateTime value must still conform."""
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    graph.add((correction, PROV.generatedAtTime, Literal("2026-09-16T09:00:00Z", datatype=XSD.dateTime)))

    conforms, _ = validate_graph(graph)

    assert conforms is True


def test_a_decision_without_attribution_does_not_conform():
    """Regression test: verify that omitting prov:wasAttributedTo on a Decision
    is caught as a violation, preventing bypass of the no-self-approval constraint."""
    graph = Graph()
    correction = REVIEW["correction-1"]
    graph.add((correction, RDF.type, REVIEW.Correction))
    graph.add((correction, REVIEW.status, Literal("proposed")))
    graph.add((correction, REVIEW.targetSubject, REVIEW["some-subject"]))
    graph.add((correction, REVIEW.targetPredicate, REVIEW["some-predicate"]))
    graph.add((correction, PROV.wasAttributedTo, REVIEW["reviewer-julian"]))
    decision = REVIEW["decision-1"]
    graph.add((decision, RDF.type, REVIEW.Decision))
    graph.add((decision, REVIEW.outcome, Literal("approved")))
    graph.add((decision, REVIEW.decides, correction))
    # Deliberately omit prov:wasAttributedTo on decision

    conforms, _ = validate_graph(graph)

    assert conforms is False
