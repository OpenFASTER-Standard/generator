// Human-readable labels for the four documentation-coverage buckets
// build_documentation_texts (reporting/data.py) classifies every subject
// into. Shared between GraphView's filter checkboxes and LivingTextView's
// section headings so the wording never drifts between the two places a
// user sees it.
//
// Important: these buckets describe TRANSLATION coverage (does a subject
// have German text, English text, or both, and -- if only German --
// could its English equivalent be found unambiguously in the PDF), not
// CITATION completeness. A "Translated" entry can still legitimately show
// "No source recorded" for one of its languages (e.g. German text on a
// locally-scoped XSD declaration, which this corpus's citation-capture
// logic doesn't yet locate) -- that's a real, separate limitation, not
// this bucket lying about its own name.
export type DocStatus = "matched" | "unmatched" | "ambiguous" | "englishOnly"

export const DOC_STATUS_LABELS: Record<DocStatus, { label: string; description: string }> = {
  matched: {
    label: "Translated",
    description: "Has both German and English documentation text.",
  },
  unmatched: {
    label: "Needs English",
    description: "Has German text only -- no matching English translation was found in the PDF.",
  },
  ambiguous: {
    label: "Ambiguous match",
    description: "Has German text only -- multiple different English candidates were found; needs a human pick.",
  },
  englishOnly: {
    label: "English only",
    description: "Has English text only -- no German documentation exists for this subject.",
  },
}
