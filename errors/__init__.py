"""GeneratorError: the shared base every domain error in this system
derives from, so the webapp's HTTP layer can map any of them to the
right status code uniformly (via one exception handler keyed on this
base class) instead of enumerating each concrete error type at every
endpoint that might raise it. See
docs/specs/2026-09-29-webapp-react-rebuild-design.md (2026-09-29 audit
finding on webapp/app.py's inconsistent error->HTTP mapping).

A subclass sets `http_status` to say what a reasonable person hitting
this error over the API should see: 400 for a bad request the caller
sent (a family/xpath/verdict that doesn't exist or doesn't parse), 500
for the server's own data being unreadable (a malformed catalog, corpus,
or reviews directory) -- something no amount of retrying with different
input fixes.
"""
from __future__ import annotations


class GeneratorError(Exception):
    http_status: int = 500
