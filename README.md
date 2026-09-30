# OpenFASTER Generator

Part of [OpenFASTER](https://openfaster.org). Built from scratch against
real [`ontologies`](https://github.com/OpenFASTER-Standard/ontologies)
source material (Germany's MiKaDiv-FM regulatory schema: XSDs + BZSt
guidance PDFs) and externally researched prior art -- not built on or
migrating from any prior code in this repo's own history. See
`docs/specs/` for the full design record, one sub-project at a time.

## Layout

- `annotation_model/` -- the core model: turns a citation of a real
  source span into a W3C Web Annotation + PROV-O + SHACL property
  shape, committed as Turtle to an explicitly-required git-backed target
  store (never a default). See
  `docs/specs/2026-09-30-core-semantic-annotation-model-design.md`.
  `annotation_model/transform/` turns a registered `(SPARQL query,
  renderer, min_rows)` transformation into rendered output (Jinja2 text
  or an `openpyxl` workbook) by querying a graph built from the shapes
  above. See
  `docs/specs/2026-09-30-declarative-transformation-design.md`.
- `alignment/` -- connects a real `annotation_model` property shape to a
  real concept in the separately-governed `institutional-ontology` repo
  via a hand-rolled SSSOM (Simple Standard for Sharing Ontology
  Mappings) reader/validator, so one stored fact can back multiple
  outputs instead of being duplicated per standard. Real mapping data
  lives in `alignments/`. See
  `docs/specs/2026-09-30-alignment-layer-design.md`.

An earlier, now-removed parallel stack (`reference_model`,
`references_catalog`, `review_recording`, `review_consultation`,
`review_surfacing`, `review_workflow`, `citation_workflow`,
`staleness_sweep`, `discovery`, `generator_errors`, `webapp`, and
`process_workflow`) predated `annotation_model` and was never unified
with it -- two independent citation stacks in one repo, with the older
one already marked "dead code pending a follow-up migration plan" for
some time before that migration ever happened. Removed outright rather
than migrated: git history has the full record if any of it is ever
needed again.

Licensed MIT.
