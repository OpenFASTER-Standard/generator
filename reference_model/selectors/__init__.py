"""Importing this package registers every built-in selector type.
Adding a new format means adding a module here and importing it below --
nothing else changes."""
from reference_model.selectors import svg_selector, xpath_selector  # noqa: F401
