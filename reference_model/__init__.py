"""Format-agnostic source reference model: records exactly what real
source span (an XSD element, a PDF page region, ...) backs a fact, in a
way that's precise enough to re-locate later and cheap to extend to a new
source format. See docs/specs/2026-09-23-source-reference-model-design.md.

Deliberately does NOT import `reference_model.selectors` here: doing so
would force every built-in selector's dependencies (pdfplumber, shapely,
lxml, ...) onto any consumer that only wants the format-agnostic data
model (`Reference`/`Leaf`/`Union`) from `reference_model.model`. A
consumer that needs the built-in selectors registered imports
`reference_model.selectors` (or the specific selector module it needs)
itself -- each selector module registers itself as an import side effect,
same as it always has.
"""
