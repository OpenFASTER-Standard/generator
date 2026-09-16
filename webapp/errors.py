"""The single place every `webapp/routes_*.py` module's error handling
lives -- registered once by `webapp.main.create_app`, never repeated
per route.

Why one app-level handler rather than a `try/except` in each endpoint:
the store/extraction layer this service wraps (`store.runs`,
`review.corrections`, `xmlschema`, `pdfplumber`) raises the *same*
handful of exception types from many different call sites, and every
route module reaches at least one of them. Stating the
exception-to-status mapping exactly once means the four route modules
already here -- and every route Plan D's frontend still needs -- get
identical, correct behaviour for free, instead of four hand-maintained
`except` ladders that drift apart (which is exactly how the four
raw-500 paths this module exists to close came about in the first
place).

Registration order does not matter: Starlette resolves a handler by
walking `type(exc).__mro__` and taking the first *registered* class it
finds, so a subclass registered alongside its own base (e.g.
`XMLSchemaKeyError` next to `XMLSchemaException`, `JSONDecodeError`
next to `ValueError`) is well-defined, not ambiguous -- the more
specific one always wins.

One deliberate non-4xx entry: `json.JSONDecodeError`. It is a
`ValueError` subclass, so the generic `ValueError -> 400` rule would
otherwise catch it -- but the only way it reaches a route is
`store.runs.read_run_audit` finding no audit artifacts for the run the
*server* selected (never something the caller passed in), which is a
server-state inconsistency and must not be reported as the client's
fault. It gets its own explicit 500 with an honest message instead.
"""
from __future__ import annotations

import json

import xmlschema.exceptions
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pdfplumber.utils.exceptions import PdfminerException
from rdflib import URIRef


def validated_iri(value: str, field: str) -> URIRef:
    """Reject a `subject`/`predicate` HTTP parameter that rdflib cannot
    serialize as a real IRI, at the route boundary, with a clean 400.

    Defense in depth, deliberately kept even though it is not closing a
    live vulnerability. Plan A's final review already established (and
    this plan's own final review re-confirmed live, over HTTP, with real
    payloads) that the string-interpolated SPARQL in `provenance.record`
    and `review.corrections` is not actually exploitable: every real
    injection attempt is rejected first by rdflib's own IRI
    serialization, before any query text is built. Two reasons to check
    here anyway:

    1. Without it, that rejection surfaces as a raw HTTP 500 -- rdflib
       raises a *bare* ``Exception`` ("... does not look like a valid
       URI, I cannot serialize this as N3/Turtle"), which no sane
       type-based handler can catch without also swallowing every
       genuine internal bug. A malformed IRI is caller error and must
       read as 400.
    2. It makes the security property explicit and testable at this
       service's own boundary, instead of leaving it as an unstated
       dependency on an implementation detail of a third-party
       serializer three layers down.

    Validation is delegated to rdflib itself (construct, then attempt
    `.n3()`) rather than a hand-rolled regex, so this can never drift
    from what the downstream code actually accepts.
    """
    term = URIRef(value)
    try:
        term.n3()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"{field}={value!r} is not a valid IRI"
        ) from exc
    return term


def _handler(status_code: int, message: str):
    def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": f"{message}: {exc}"})

    return handle


# Most specific first, purely for readability -- see this module's own
# docstring on why the actual resolution order is MRO-based, not
# registration-order-based.
_HANDLERS: tuple[tuple[type[Exception], int, str], ...] = (
    # A citation asked for an XSD component (`type_qname`) that this
    # schema does not define -- the named resource genuinely is not there.
    (xmlschema.exceptions.XMLSchemaKeyError, 404, "unknown XSD component"),
    # Any other xmlschema failure reachable from a route is caused by the
    # caller's own `file` parameter: a path that does not exist
    # (XMLResourceOSError) or is not a well-formed schema
    # (XMLResourceParseError).
    (xmlschema.exceptions.XMLSchemaException, 400, "invalid XSD source"),
    # pdfplumber on a file that exists but is not a PDF.
    (PdfminerException, 400, "invalid PDF source"),
    # pdfplumber/pdfminer on a path that does not exist at all.
    (FileNotFoundError, 404, "source file not found"),
    (OSError, 400, "source file could not be read"),
    # See this module's docstring -- must be registered ahead of the
    # ValueError rule below, and is deliberately a 500.
    (json.JSONDecodeError, 500, "run has no stored audit artifacts"),
    # The project's own house error type for caller-supplied nonsense:
    # an unknown run_id (store.runs), an out-of-range page or inverted
    # bbox (citations.pdf_citation), a SHACL-rejected correction or
    # decision (review.corrections), a malformed language tag (rdflib).
    (ValueError, 400, "invalid request"),
    # review.corrections/provenance.record reject a BNode target with
    # TypeError; also any mistyped term reaching those APIs.
    (TypeError, 400, "invalid request"),
)


def install_error_handlers(app: FastAPI) -> None:
    for exception_type, status_code, message in _HANDLERS:
        app.add_exception_handler(exception_type, _handler(status_code, message))
