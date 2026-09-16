"""Smoke test: every pipeline subpackage must be importable on its own,
with no cross-import at module-load time (extraction/generation/
equivalence/ingestion stay independent until a later sub-project actually
wires them together)."""
import importlib
import tomllib
from pathlib import Path


def test_all_pipeline_subpackages_are_importable():
    for module_name in ("extraction", "generation", "equivalence", "ingestion"):
        module = importlib.import_module(module_name)
        assert module is not None


def test_subpackages_have_no_cross_imports_yet():
    import ast
    import pathlib

    repo_root = pathlib.Path(__file__).parent.parent

    for module_name in ("extraction", "generation", "equivalence", "ingestion"):
        init_path = repo_root / module_name / "__init__.py"
        tree = ast.parse(init_path.read_text())
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split(".")[0])
        other_pipeline_modules = {"extraction", "generation", "equivalence", "ingestion"} - {module_name}
        assert not (imported_names & other_pipeline_modules), (
            f"{module_name} imports {imported_names & other_pipeline_modules} "
            "before any sub-project has wired the pipeline together"
        )


def test_every_existing_package_in_pyproject_include_list_has_an_init_py():
    """Regression test for citations/__init__.py existing on disk but never
    being `git add`ed (confirmed live: `git ls-files citations/` only listed
    the two modules, not the package's own __init__.py) -- a gap that made
    `citations` importable only by accident, via pytest's own sys.path
    injection, not via a real `pip install -e .`. This reads pyproject.toml's
    own [tool.setuptools.packages.find] include list directly, so it can't
    drift from the real package list, and for every entry whose top-level
    directory actually exists on disk (some, like `review`/`webapp`, are
    future/plan-B+ packages that don't exist yet), asserts that directory
    has an __init__.py file.
    """
    repo_root = Path(__file__).parent.parent
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    include_patterns = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    checked = []
    for pattern in include_patterns:
        package_name = pattern.rstrip("*")
        package_dir = repo_root / package_name
        if not package_dir.is_dir():
            continue
        checked.append(package_name)
        init_file = package_dir / "__init__.py"
        assert init_file.is_file(), (
            f"{package_dir} is a top-level package directory from pyproject.toml's "
            f"[tool.setuptools.packages.find] include list but has no __init__.py "
            f"-- it would be silently excluded from `pip install -e .`'s installed "
            f"packages while still importable under pytest via sys.path injection"
        )

    # Sanity: make sure this test actually checked something real, not an
    # empty list due to a path-resolution mistake.
    assert "citations" in checked
    assert "store" in checked
    assert "provenance" in checked
