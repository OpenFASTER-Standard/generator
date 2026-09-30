"""Public surface of the annotation_model package.

Internal module layout (annotation_model.selectors.xpath,
annotation_model.rdf, ...) is free to reshuffle as long as these
names keep resolving from here.
"""
from annotation_model.drift import DriftResult, check_drift, check_svg_drift, check_xpath_drift
from annotation_model.outcomes import ResolutionOutcome, Status
from annotation_model.rdf import annotate_svg, annotate_xpath
from annotation_model.store import TargetStore, TargetStoreError

__all__ = [
    "DriftResult",
    "ResolutionOutcome",
    "Status",
    "TargetStore",
    "TargetStoreError",
    "annotate_svg",
    "annotate_xpath",
    "check_drift",
    "check_svg_drift",
    "check_xpath_drift",
]
