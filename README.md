# OpenFASTER Generator

Part of [OpenFASTER](https://openfaster.org). Built from scratch against
real [`ontologies`](https://github.com/OpenFASTER-Standard/ontologies)
source material (Germany's MiKaDiv-FM regulatory schema: XSDs + BZSt
guidance PDFs) and externally researched prior art -- not built on or
migrating from any prior code in this repo's own history. See
`docs/specs/` for the full design record, one sub-project at a time.

## Layout

- `reference_model/` -- a format-agnostic `Reference` (citation) model:
  records exactly what real source span (an XSD element, a PDF page
  region) backs a fact, precise enough to re-locate later and soundly
  flag when it may have changed. See
  `docs/specs/2026-09-23-source-reference-model-design.md`.
- `staleness_sweep/` -- batches `reference_model`'s own `check_reference()`
  across many `Reference`s at once against the real, snapshot-versioned
  `ontologies` corpus. See `docs/specs/2026-09-23-staleness-sweep-design.md`.

Licensed MIT.
