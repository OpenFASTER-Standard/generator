"""URI minting for extracted xsdo: facts. Only components with real
global XSD identity (named complexType/simpleType, global element) get
a stable, name-based URI -- everything else (local element/attribute
declarations, anonymous types) is scoped under whichever declaration
owns it, since XSD itself gives those no identity outside that scope.
Real, confirmed necessary: this corpus has 149 real xs:attribute
declarations and zero are global -- a bare local name is not unique
across types, so local declarations must be scoped, not minted flat.
"""
from __future__ import annotations

from rdflib import URIRef


def global_uri(target_namespace: str, local_name: str) -> URIRef:
    return URIRef(f"{target_namespace}#{local_name}")


def child_uri(parent_uri: URIRef, local_name: str) -> URIRef:
    return URIRef(f"{parent_uri}.{local_name}")


def type_uri(xsd_type, owner_uri: URIRef) -> URIRef:
    if xsd_type.name is not None:
        return global_uri(xsd_type.target_namespace, xsd_type.local_name)
    return child_uri(owner_uri, "Type")
