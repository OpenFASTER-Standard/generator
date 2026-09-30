"""A Jinja2-based text renderer -- one of two renderer kinds proven to
work through apply_transformation()'s single Callable[[list[dict]], Any]
contract (see annotation_model/transform/apply.py and the design spec).

Writing a template: access a row by item (`row['property']`), not
attribute (`row.property`) -- Jinja's attribute lookup tries a real dict
method first, so a column named e.g. "values" (a realistic SPARQL
variable name: a code list's allowed values) would silently resolve to
`dict.values` instead of the row's own value under attribute access.
"""
from __future__ import annotations

from typing import Any, Callable

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

# StrictUndefined: a misspelled column must raise, not silently render as
# empty -- the same "loud failure over silent" principle min_rows exists
# to enforce, one layer down (see apply.py).
#
# SandboxedEnvironment: not a defense against today's transformation
# author (who registers a renderer by calling register() from Python, so
# could already supply an arbitrary callable) -- it matters the moment a
# template becomes third-party *data* rather than trusted code, which the
# design spec's own Open Questions name as a real future direction (a
# bank registering its own private transformation, roadmap task 6).
# Free today (verified to render this module's own tests identically
# either way); expensive to retrofit once real user-authored templates
# already exist.
_ENV = SandboxedEnvironment(undefined=StrictUndefined)


def jinja_text_renderer(template_source: str) -> Callable[[list[dict]], str]:
    # Compiles eagerly, at call time -- a malformed template raises
    # jinja2.TemplateSyntaxError here, immediately, rather than the first
    # time the returned renderer actually runs. Deliberate: failing at
    # the module that defines the transformation is more useful than
    # failing deep inside a later apply_transformation() call.
    template = _ENV.from_string(template_source)

    def render(rows: list[dict[str, Any]]) -> str:
        return template.render(rows=rows)

    return render
