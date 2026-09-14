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
  the real, official one (exact automaton-based proof, not sampling)
- `ingestion/` -- real filled documents (both directions) -> graph facts

**Status: skeleton only, no pipeline logic implemented yet.**

Licensed MIT.
