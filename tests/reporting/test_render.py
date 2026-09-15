"""Tests for render_report's substitution/escaping logic, against small,
controlled fixture asset files (not the real, full assets -- those are
presentation content, not unit-testable line by line; this test proves
the substitution mechanism itself is correct, including the real
</script>-in-data edge case)."""
import json

import reporting.render as render_module
from reporting.render import render_report


def test_render_report_embeds_css_js_and_data(tmp_path, monkeypatch):
    (tmp_path / "report.html").write_text(
        "<html><style>/*__REPORT_CSS__*/</style>"
        "<script id=\"report-data\" type=\"application/json\">/*__REPORT_DATA__*/</script>"
        "<script>/*__REPORT_JS__*/</script></html>"
    )
    (tmp_path / "report.css").write_text("body { color: red; }")
    (tmp_path / "report.js").write_text("console.log('hi');")
    monkeypatch.setattr(render_module, "_ASSETS_DIR", tmp_path)

    data = {"structure": {}, "note": "plain"}
    html = render_report(data)

    assert "body { color: red; }" in html
    assert "console.log('hi');" in html
    assert json.dumps(data) in html


def test_render_report_escapes_closing_script_tags_in_data(tmp_path, monkeypatch):
    (tmp_path / "report.html").write_text(
        "<script id=\"report-data\" type=\"application/json\">/*__REPORT_DATA__*/</script>"
    )
    (tmp_path / "report.css").write_text("")
    (tmp_path / "report.js").write_text("")
    monkeypatch.setattr(render_module, "_ASSETS_DIR", tmp_path)

    data = {"documentationPairs": {"matched": [{"de": "Enthält </script> Text."}]}}
    html = render_report(data)

    assert "</script> Text" not in html  # the raw, unescaped form must not appear
    # The embedded JSON must still round-trip to the exact original data once
    # the escape is reversed, proving no real data was lost or corrupted.
    start = html.index('type="application/json">') + len('type="application/json">')
    end = html.index("</script>", start)
    embedded = html[start:end].replace("<\\/", "</")
    assert json.loads(embedded) == data
