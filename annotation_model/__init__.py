"""Public surface of the annotation_model package.

Internal module layout (annotation_model.selectors.xpath,
annotation_model.rdf, annotation_model.transform.apply, ...) is free to
reshuffle as long as these names keep resolving from here.
"""
from annotation_model.drift import DriftResult, check_drift, check_svg_drift, check_xpath_drift
from annotation_model.outcomes import ResolutionOutcome, Status
from annotation_model.rdf import annotate_svg, annotate_xpath
from annotation_model.store import TargetStore, TargetStoreError
from annotation_model.transform.apply import TransformationError, apply_transformation
from annotation_model.transform.jinja import jinja_text_renderer
from annotation_model.transform.registry import Transformation
from annotation_model.transform.registry import get as get_transformation
from annotation_model.transform.registry import register as register_transformation

__all__ = [
    "DriftResult",
    "ResolutionOutcome",
    "Status",
    "TargetStore",
    "TargetStoreError",
    "Transformation",
    "TransformationError",
    "annotate_svg",
    "annotate_xpath",
    "apply_transformation",
    "check_drift",
    "check_svg_drift",
    "check_xpath_drift",
    "get_transformation",
    "jinja_text_renderer",
    "register_transformation",
]
