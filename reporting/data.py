"""Walks an already-extracted xsdo: rdflib.Graph into a plain,
JSON-serializable dict for the HTML report's client-side renderer.

Real construct shapes this module reads are exactly what extraction/
already produces (verified directly against the merged source, not
guessed) -- see this plan's own Global Constraints for the full list.
"""
from __future__ import annotations

from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")

_FACET_PREDICATES = {
    "length": XSDO.length,
    "minLength": XSDO.minLength,
    "maxLength": XSDO.maxLength,
    "whiteSpace": XSDO.whiteSpace,
    "minInclusive": XSDO.minInclusive,
    "maxInclusive": XSDO.maxInclusive,
    "minExclusive": XSDO.minExclusive,
    "maxExclusive": XSDO.maxExclusive,
    "totalDigits": XSDO.totalDigits,
    "fractionDigits": XSDO.fractionDigits,
}


def _json_safe_facet_value(value):
    """Coerce RDF facet value to a JSON-safe Python type.

    Keeps int/bool as-is (already JSON-safe), converts all other types
    (Decimal, date, datetime, etc.) to strings to avoid json.dumps errors.
    """
    python_value = value.toPython()
    if isinstance(python_value, (int, bool)):
        return python_value
    return str(python_value)


def _target_namespace_of(uri: str) -> str:
    return uri.split("#", 1)[0]


# FM's own real xs:documentation is untagged (no xml:lang at all) and is
# German-only -- a real, verified, project-specific fact (see
# extraction/documentation.py's own docstring), not an arbitrary
# assumption -- so an untagged xsdo:documentation Literal is keyed under
# "de" here, same as a real xml:lang="de"-tagged one would be.
_UNTAGGED_LANGUAGE_KEY = "de"


def _documentation_by_language(graph: Graph, subject) -> dict[str, str]:
    """Every real xsdo:documentation value on a subject, keyed by its
    real language -- NOT hardcoded to exactly "de"/"en". A module whose
    real XSD carries a third real xml:lang tag (not present in the
    MiKaDiv-FM corpus today, but not something this function should
    silently drop either) shows up here under its own real language
    key instead of being lost.
    """
    texts: dict[str, str] = {}
    for doc in graph.objects(subject, XSDO.documentation):
        lang = doc.language if doc.language is not None else _UNTAGGED_LANGUAGE_KEY
        texts[lang] = str(doc)
    return texts


def _build_content_model(graph: Graph, group_node) -> dict:
    kind = "Choice" if (group_node, RDF.type, XSDO.Choice) in graph else "Sequence"
    particles = sorted(
        graph.objects(group_node, XSDO.hasParticle),
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )
    return {"kind": kind, "particles": [_build_particle(graph, p) for p in particles]}


def _build_particle(graph: Graph, particle_node) -> dict:
    min_occurs = int(graph.value(particle_node, XSDO.minOccurs))
    unbounded = graph.value(particle_node, XSDO.maxOccursUnbounded)
    if unbounded is not None:
        max_occurs: int | str = "unbounded"
    else:
        max_occurs = int(graph.value(particle_node, XSDO.maxOccurs))
    term = graph.value(particle_node, XSDO["term"])
    is_nested_group = (term, RDF.type, XSDO.Sequence) in graph or (
        term, RDF.type, XSDO.Choice
    ) in graph
    if is_nested_group:
        term_data = {"nested": _build_content_model(graph, term)}
    else:
        term_data = {"ref": str(term)}
    return {"minOccurs": min_occurs, "maxOccurs": max_occurs, "term": term_data}


def _build_attribute_uses(graph: Graph, type_uri: URIRef) -> list[dict]:
    uses = []
    for use in graph.objects(type_uri, XSDO.hasAttributeUse):
        required = bool(graph.value(use, XSDO.required))
        term = graph.value(use, XSDO["term"])
        uses.append({"required": required, "ref": str(term)})
    return uses


def _identity_constraint_kind(graph: Graph, constraint) -> str:
    for kind in ("Key", "Unique", "KeyRef"):
        if (constraint, RDF.type, XSDO[kind]) in graph:
            return kind
    raise ValueError(f"unknown identity constraint kind for {constraint}")


def _build_identity_constraints(graph: Graph, type_uri: URIRef) -> list[dict]:
    constraints = []
    for constraint in graph.objects(type_uri, XSDO.hasIdentityConstraint):
        fields = [str(f) for f in graph.objects(constraint, XSDO.field)]
        refer = graph.value(constraint, XSDO.refer)
        constraints.append(
            {
                "kind": _identity_constraint_kind(graph, constraint),
                "selector": str(graph.value(constraint, XSDO.selector)),
                "fields": fields,
                "refer": str(refer) if refer is not None else None,
            }
        )
    return constraints


def _build_complex_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    extends = graph.value(type_uri, XSDO.extends)
    content_node = graph.value(type_uri, XSDO.contentModel)
    if content_node is None:
        raise ValueError(f"{type_uri} has no xsdo:contentModel")
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "abstract": bool(graph.value(type_uri, XSDO.abstract)),
        "extends": str(extends) if extends is not None else None,
        "contentModel": _build_content_model(graph, content_node),
        "attributeUses": _build_attribute_uses(graph, type_uri),
        "identityConstraints": _build_identity_constraints(graph, type_uri),
    }


def _build_simple_type(graph: Graph, type_uri: URIRef) -> dict:
    name = graph.value(type_uri, XSDO.name)
    facets = {}
    for label, predicate in _FACET_PREDICATES.items():
        value = graph.value(type_uri, predicate)
        if value is not None:
            facets[label] = _json_safe_facet_value(value)
    enumeration = [
        str(graph.value(value_node, XSDO.literalValue))
        for value_node in graph.objects(type_uri, XSDO.hasEnumerationValue)
    ]
    patterns = [str(p) for p in graph.objects(type_uri, XSDO.pattern)]
    union_members = [str(m) for m in graph.objects(type_uri, XSDO.hasUnionMember)]
    return {
        "uri": str(type_uri),
        "name": str(name) if name is not None else None,
        "facets": facets,
        "enumeration": enumeration,
        "patterns": patterns,
        "unionMembers": union_members,
    }


def build_structure(graph: Graph) -> dict:
    structure: dict[str, dict[str, list]] = {}

    for type_uri in graph.subjects(RDF.type, XSDO.ComplexTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["complexTypes"].append(_build_complex_type(graph, type_uri))

    for type_uri in graph.subjects(RDF.type, XSDO.SimpleTypeDefinition):
        ns = _target_namespace_of(str(type_uri))
        structure.setdefault(ns, {"complexTypes": [], "simpleTypes": []})
        structure[ns]["simpleTypes"].append(_build_simple_type(graph, type_uri))

    return structure


def build_declarations(graph: Graph) -> dict:
    declarations: dict[str, dict] = {}
    for kind_label, rdf_type in (
        ("Element", XSDO.ElementDeclaration),
        ("Attribute", XSDO.AttributeDeclaration),
    ):
        for uri in graph.subjects(RDF.type, rdf_type):
            type_ref = graph.value(uri, XSDO.type)
            default = graph.value(uri, XSDO.defaultValue)
            fixed = graph.value(uri, XSDO.fixedValue)
            declarations[str(uri)] = {
                "name": str(graph.value(uri, XSDO.name)),
                "kind": kind_label,
                "type": str(type_ref) if type_ref is not None else None,
                "default": str(default) if default is not None else None,
                "fixed": str(fixed) if fixed is not None else None,
                "documentation": _documentation_by_language(graph, uri),
            }
    return declarations


def build_documentation_texts(
    graph: Graph, occurrences: dict[str, list[str]], plausibility_issues: list
) -> dict:
    # Fix (real subject_uri now available on PlausibilityIssue, added
    # after the final review found 2 real subjects sharing the bare name
    # "WIdNr" -- MeldepflichtigeStelleType.@WIdNr and
    # IdMerkmalNNPType.@WIdNr -- with a real issue that could only be
    # correctly attributed to one of them). Keyed by the real subject
    # URI, not the ambiguous bare name, so no collision is possible.
    issues_by_uri: dict[str, list[dict]] = {}
    for issue in plausibility_issues:
        if not issue.subject_uri:
            continue  # a legacy/synthetic issue with no real URI to attach to
        issues_by_uri.setdefault(issue.subject_uri, []).append(
            {"kind": issue.kind, "detail": issue.detail}
        )
    # Fix 2 (final whole-branch review): plausibility_issues' own order is
    # itself non-deterministic (check_translation_plausibility, already
    # merged in extraction/, iterates a set()) -- sort each per-subject
    # group so a subject with 2+ real issues always lists them in the
    # same order.
    for issue_list in issues_by_uri.values():
        issue_list.sort(key=lambda i: (i["kind"], i["detail"]))

    matched, unmatched, ambiguous, english_only = [], [], [], []
    for subject in set(graph.subjects(XSDO.documentation, None)):
        uri = str(subject)
        name_literal = graph.value(subject, XSDO.name)
        name = str(name_literal) if name_literal is not None else uri
        # Every real language actually present on this subject -- not
        # hardcoded to exactly "de"/"en", so a real third language (a
        # native xml:lang tag some future module carries) is never
        # silently dropped from what the report shows.
        languages = _documentation_by_language(graph, subject)
        de = languages.get("de")
        en = languages.get("en")

        # Fix 1 (final whole-branch review): a subject can have real @en
        # documentation with no German at all (confirmed real: 3 such
        # subjects, including one whose English text is the literally
        # corrupted PDF artifact "Documentati on") -- these used to be
        # silently `continue`-past here, vanishing from §2 entirely even
        # though §3's coverage total (build_audit, via
        # CoverageReport.total_documented_subjects) counts every subject
        # with ANY xsdo:documentation triple, German or not. Giving them
        # their own group keeps §2's total subject count reconciled with
        # §3's.
        if de is None:
            if en is not None:
                english_only.append({"uri": uri, "name": name, "languages": languages})
            continue

        if en is not None:
            matched.append(
                {
                    "uri": uri, "name": name, "languages": languages,
                    "issues": issues_by_uri.get(uri, []),
                }
            )
            continue

        candidates = occurrences.get(name, [])
        if len(set(candidates)) > 1:
            ambiguous.append(
                {
                    "uri": uri, "name": name, "languages": languages,
                    "candidates": sorted(set(candidates)),
                }
            )
        else:
            unmatched.append({"uri": uri, "name": name, "languages": languages})

    # Fix 2: the subject universe above is walked via set(...), whose
    # iteration order depends on PYTHONHASHSEED -- sort every output list
    # deterministically so regenerating the report from identical inputs
    # never reorders its content (a stable, human-sensible reading order:
    # by name, then by URI to break ties between same-named subjects).
    matched.sort(key=lambda p: (p["name"], p["uri"]))
    unmatched.sort(key=lambda p: (p["name"], p["uri"]))
    ambiguous.sort(key=lambda p: (p["name"], p["uri"]))
    english_only.sort(key=lambda p: (p["name"], p["uri"]))

    return {
        "matched": matched,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
        "englishOnly": english_only,
    }


def build_audit(attachment, coverage, plausibility_issues: list) -> dict:
    return {
        "attachment": {
            "attached": len(attachment.attached),
            "ambiguous": len(attachment.ambiguous),
            "unmatched": len(attachment.unmatched),
        },
        "coverage": {
            "total": coverage.total_documented_subjects,
            "attached": coverage.attached,
            "ambiguous": coverage.ambiguous,
            "unmatched": coverage.unmatched,
        },
        # Fix 2 (final whole-branch review): check_translation_plausibility
        # (already merged in extraction/) iterates a set(), so
        # plausibility_issues' own order is non-deterministic across
        # process runs -- sort here so regenerating the report from
        # identical inputs never reorders §3's issue list.
        "issues": sorted(
            (
                {
                    "kind": i.kind, "subjectName": i.subject_name, "detail": i.detail,
                    # Real subject URI (added alongside the WIdNr fix) --
                    # lets the report link an issue back to its exact
                    # Documentation-Pairs entry instead of just naming it.
                    "subjectUri": i.subject_uri or None,
                }
                for i in plausibility_issues
            ),
            key=lambda i: (i["subjectName"], i["kind"]),
        ),
    }


def build_report_data(
    graph: Graph,
    occurrences: dict[str, list[str]],
    plausibility_issues: list,
    coverage,
    attachment,
) -> dict:
    return {
        "structure": build_structure(graph),
        "declarations": build_declarations(graph),
        "documentationTexts": build_documentation_texts(graph, occurrences, plausibility_issues),
        "audit": build_audit(attachment, coverage, plausibility_issues),
    }
