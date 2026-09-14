# OpenFASTER Generator

Part of [OpenFASTER](https://openfaster.org). The generation/extraction/
equivalence-checking/ingestion pipeline that turns
[`ontologies`](https://github.com/OpenFASTER-Standard/ontologies) content
into real artifacts (XSD, XLSX, PDF, the Bikeshed-sourced spec site, XML
instances) and real submitted documents back into graph facts. Depends on
`ontologies` as input; never the reverse.

## Layout

- `extraction/` -- real XSD -> `XSDO:`-shaped facts
- `generation/` -- graph -> XSD / XLSX / PDF / Bikeshed `.bs` / XML
- `equivalence/` -- proves a generated XSD is behaviorally equivalent to
  an official one, via bounded-exhaustive/pairwise structural testing
  and exact leaf-facet checking (not document sampling, not a formal
  completeness proof either -- see `docs/specs/2026-09-14-equivalence-checker-design.md`
  for the exact confidence characterization). Public interface:
  `check_equivalence`, `Report`, `Divergence`, `UnsupportedConstructError`.
- `ingestion/` -- real filled documents (both directions) -> graph facts

**Status: `equivalence/` is implemented; `extraction/`, `generation/`, and `ingestion/` are not yet.**

Licensed MIT.
