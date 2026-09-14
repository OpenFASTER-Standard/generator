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
