"""Combines report data with the static HTML/CSS/JS shell into one
self-contained HTML string -- no templating library: the shell's own
CSS/JS are inlined at generation time via plain string substitution,
and the report data is embedded as one JSON blob a small vanilla-JS
renderer (reporting/assets/report.js) reads client-side. This keeps
the generated file genuinely self-contained: it opens correctly from a
plain file:// path, no server, no external requests.
"""
from __future__ import annotations

import json
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent / "assets"


def render_report(data: dict) -> str:
    html = (_ASSETS_DIR / "report.html").read_text()
    css = (_ASSETS_DIR / "report.css").read_text()
    js = (_ASSETS_DIR / "report.js").read_text()

    # Escape a real, if rare, risk: documentation text containing a literal
    # "</script>" substring would otherwise prematurely close the embedding
    # <script> tag and corrupt the page. "<\/" is valid inside a JS/JSON
    # string and browsers render it back to "</" -- a standard, simple fix.
    data_json = json.dumps(data).replace("</", "<\\/")

    html = html.replace("/*__REPORT_CSS__*/", css)
    html = html.replace("/*__REPORT_JS__*/", js)
    html = html.replace("/*__REPORT_DATA__*/", data_json)
    return html
