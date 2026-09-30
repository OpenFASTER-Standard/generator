"""Real per-instance persistence for process_workflow -- one JSON file
per pending process instance, matching webapp/app.py's own
DEFAULT_CATALOG_PATH/DEFAULT_REVIEWS_DIR convention exactly (runtime
data lives in the separate `ontologies` corpus repo, not committed
inside `generator`'s own git history).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from SpiffWorkflow.bpmn import BpmnWorkflow

from process_workflow.engine import deserialize, serialize

DEFAULT_PROCESS_INSTANCES_DIR = "/work/ontologies/mikadiv-fm/process_instances"


def process_instances_dir() -> Path:
    # Read at call time, not import time -- matching webapp/app.py's
    # _corpus_root() exactly.
    return Path(os.environ.get("MIKADIV_PROCESS_INSTANCES_DIR", DEFAULT_PROCESS_INSTANCES_DIR))


class CorruptedInstanceError(Exception):
    """Raised when a persisted process instance file exists but fails to
    deserialize -- never a bare json.JSONDecodeError/KeyError with no
    indication of which file broke."""


@dataclass(frozen=True)
class CorrectionIdentity:
    fact_key: str
    leaf_reference_id: str
    drift_kind: str
    fingerprint: str


def _instance_filename(identity: CorrectionIdentity) -> str:
    # Hash each field independently, THEN join the fixed-length (64 hex
    # char) digests -- joining the raw fields with "|" first (matching
    # reference_model/model.py's compute_union_reference_id at first
    # glance) is a real, live-confirmed collision: identity(fact_key=
    # "alice|bob", leaf_reference_id="ref-1", ...) and identity(fact_key=
    # "alice", leaf_reference_id="bob|ref-1", ...) join to the identical
    # string "alice|bob|ref-1|...", because fact_key is arbitrary
    # user-supplied content (per webapp/app.py's AddCitationRequest) and
    # can itself contain the separator. Hashing per-field first removes
    # the ambiguity: two different field values can never produce the
    # same 64-hex-char digest in the same position, regardless of what
    # separator characters either field happens to contain.
    field_digests = [
        hashlib.sha256(field.encode("utf-8")).hexdigest()
        for field in (identity.fact_key, identity.leaf_reference_id, identity.drift_kind, identity.fingerprint)
    ]
    return hashlib.sha256("".join(field_digests).encode("utf-8")).hexdigest() + ".json"


def save_instance(identity: CorrectionIdentity, workflow: BpmnWorkflow) -> None:
    process_instances_dir().mkdir(parents=True, exist_ok=True)
    path = process_instances_dir() / _instance_filename(identity)
    path.write_text(serialize(workflow), encoding="utf-8")


def load_instance(identity: CorrectionIdentity) -> BpmnWorkflow | None:
    path = process_instances_dir() / _instance_filename(identity)
    if not path.exists():
        return None
    try:
        return deserialize(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CorruptedInstanceError(f"{path}: could not deserialize process instance: {exc}") from exc


def delete_instance(identity: CorrectionIdentity) -> None:
    (process_instances_dir() / _instance_filename(identity)).unlink(missing_ok=True)
