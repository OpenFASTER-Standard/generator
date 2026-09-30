"""Safety net (Important #6, roadmap task 5's final review): any test
anywhere in this suite that ends up calling submit_review() with a
REJECTED verdict writes a real process-instance file to
MIKADIV_PROCESS_INSTANCES_DIR -- without this, that default is the
real, git-tracked /work/ontologies/mikadiv-fm/process_instances, and a
test author who doesn't already know to set the env var themselves
would silently write into the real corpus checkout. Point it at a fresh
per-test tmp_path by default; a test that needs a specific value (or
one shared with a subprocess) still overrides it via its own
monkeypatch.setenv call, and last-write-wins.
"""
import pytest


@pytest.fixture(autouse=True)
def _default_process_instances_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIKADIV_PROCESS_INSTANCES_DIR", str(tmp_path / "process_instances"))
