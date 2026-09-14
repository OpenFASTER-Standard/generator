"""Identity-constraint extraction: xs:key/xs:unique/xs:keyref, the
complete closed set of XSD identity-constraint kinds. Only xs:unique
is confirmed real anywhere in this corpus (an earlier claim of real
xs:key/xs:keyref usage in KaFE did not survive re-verification against
every real XSD file on disk -- see the extraction design spec's
corrected census); xs:key/xs:keyref stay supported regardless, as the
same closed kind set xs:unique belongs to.

Attachment (which URI hasIdentityConstraint is linked from) is the
caller's decision, not this module's -- see this plan's Global
Constraints for why it must be a type URI, computed the same way as
the owning element's own xsdo:type link.
"""
from __future__ import annotations

import xmlschema
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from extraction.uris import child_uri

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_KIND_BY_CLASS = (
    (xmlschema.validators.identities.XsdKey, XSDO.Key),
    (xmlschema.validators.identities.XsdUnique, XSDO.Unique),
    (xmlschema.validators.identities.XsdKeyref, XSDO.KeyRef),
)


def _kind_of(identity_constraint):
    for cls, kind in _KIND_BY_CLASS:
        if isinstance(identity_constraint, cls):
            return kind
    raise NotImplementedError(
        f"unknown identity constraint kind: {type(identity_constraint)}"
    )


def extract_identity_constraints(graph: Graph, xsd_element, owner_uri: URIRef) -> None:
    for identity_constraint in xsd_element.identities:
        constraint_uri = child_uri(owner_uri, identity_constraint.local_name)
        graph.add((constraint_uri, RDF.type, _kind_of(identity_constraint)))
        graph.add(
            (constraint_uri, XSDO.selector, Literal(identity_constraint.selector.path))
        )
        for field in identity_constraint.fields:
            graph.add((constraint_uri, XSDO.field, Literal(field.path)))
        if isinstance(identity_constraint, xmlschema.validators.identities.XsdKeyref):
            graph.add(
                (constraint_uri, XSDO.refer, Literal(identity_constraint.refer.local_name))
            )
        graph.add((owner_uri, XSDO.hasIdentityConstraint, constraint_uri))
