"""This project's real PROV-O usage: only the handful of predicates
actually needed, not the full PROV-O vocabulary -- attached to individual
facts via RDF-star quoted triples, not classical 4-triple reification.
"""
from rdflib import Namespace

PROV = Namespace("http://www.w3.org/ns/prov#")
