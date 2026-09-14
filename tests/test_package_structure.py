"""Smoke test: every pipeline subpackage must be importable on its own,
with no cross-import at module-load time (extraction/generation/
equivalence/ingestion stay independent until a later sub-project actually
wires them together)."""
import importlib


def test_all_pipeline_subpackages_are_importable():
    for module_name in ("extraction", "generation", "equivalence", "ingestion"):
        module = importlib.import_module(module_name)
        assert module is not None


def test_subpackages_have_no_cross_imports_yet():
    import ast
    import pathlib

    for module_name in ("extraction", "generation", "equivalence", "ingestion"):
        init_path = pathlib.Path(module_name) / "__init__.py"
        tree = ast.parse(init_path.read_text())
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        other_pipeline_modules = {"extraction", "generation", "equivalence", "ingestion"} - {module_name}
        assert not (imported_names & other_pipeline_modules), (
            f"{module_name} imports {imported_names & other_pipeline_modules} "
            "before any sub-project has wired the pipeline together"
        )
