"""CLI: python -m reporting <xsd_path> <pdf_path> -o report.html

Runs the real generator pipeline end to end (extract -> attach English
documentation -> coverage/plausibility audit) and writes one
self-contained HTML report. No flags beyond -o/--output -- YAGNI on
configurability until a real second use case demands it.
"""
from __future__ import annotations

import argparse

from extraction.annex_pdf import attach_english_documentation, extract_name_occurrences
from extraction.extract import extract
from extraction.translation_plausibility import (
    check_translation_coverage,
    check_translation_plausibility,
)

from reporting.data import build_report_data
from reporting.render import render_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the generator-output visual verification report."
    )
    parser.add_argument("xsd_path", help="Path to the real XSD entry point")
    parser.add_argument("pdf_path", help="Path to the real Annex PDF")
    parser.add_argument("-o", "--output", default="report.html")
    args = parser.parse_args()

    graph = extract(args.xsd_path)
    attachment = attach_english_documentation(graph, args.pdf_path)
    occurrences = extract_name_occurrences(args.pdf_path)
    coverage = check_translation_coverage(graph, occurrences)
    plausibility_issues = check_translation_plausibility(graph)

    data = build_report_data(graph, occurrences, plausibility_issues, coverage, attachment)
    html = render_report(data)

    with open(args.output, "w") as f:
        f.write(html)
    print(f"Wrote {args.output} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
