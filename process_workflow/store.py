"""Real per-instance persistence for process_workflow -- one JSON file
per pending process instance, matching webapp/app.py's own
DEFAULT_CATALOG_PATH/DEFAULT_REVIEWS_DIR convention exactly. Written
into the separate `ontologies` corpus repo's own working tree (like
`references.json`/`reviews/` already are) -- not committed to git
there, matching that repo's own transient/generated-data conventions.
"""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from SpiffWorkflow.bpmn import BpmnWorkflow

from generator_errors import GeneratorError
from process_workflow.engine import deserialize, serialize

DEFAULT_PROCESS_INSTANCES_DIR = "/work/ontologies/mikadiv-fm/process_instances"


def process_instances_dir() -> Path:
    # Read at call time, not import time -- matching webapp/app.py's
    # _corpus_root() exactly.
    return Path(os.environ.get("MIKADIV_PROCESS_INSTANCES_DIR", DEFAULT_PROCESS_INSTANCES_DIR))


class CorruptedInstanceError(GeneratorError):
    """Raised when a persisted process instance file exists but fails to
    deserialize, or its own recorded identity doesn't match the identity
    it was loaded under -- never a bare json.JSONDecodeError/KeyError
    with no indication of which file broke, and never a silently wrong
    workflow handed back under someone else's identity."""

    http_status = 500


@dataclass(frozen=True)
class CorrectionIdentity:
    fact_key: str
    leaf_reference_id: str
    drift_kind: str
    fingerprint: str


def _instance_filename(identity: CorrectionIdentity) -> str:
    # Hash each field independently (after Unicode-normalizing to NFC,
    # so a re-typed accented fact_key hashes the same regardless of
    # which normalization form the input arrived in), THEN join the
    # fixed-length (64 hex char) digests -- joining the raw fields with
    # "|" first is a real, live-confirmed collision: identity(fact_key=
    # "alice|bob", leaf_reference_id="ref-1", ...) and identity(fact_key=
    # "alice", leaf_reference_id="bob|ref-1", ...) join to the identical
    # string "alice|bob|ref-1|...", because fact_key is arbitrary
    # user-supplied content (per webapp/app.py's AddCitationRequest) and
    # can itself contain the separator. Hashing per-field first removes
    # the ambiguity: two different field values can never produce the
    # same 64-hex-char digest in the same position, regardless of what
    # separator characters either field happens to contain.
    field_digests = [
        hashlib.sha256(unicodedata.normalize("NFC", field).encode("utf-8")).hexdigest()
        for field in (identity.fact_key, identity.leaf_reference_id, identity.drift_kind, identity.fingerprint)
    ]
    return hashlib.sha256("".join(field_digests).encode("utf-8")).hexdigest() + ".json"


def save_instance(
    identity: CorrectionIdentity, workflow: BpmnWorkflow, *, instances_dir: Path | None = None
) -> None:
    directory = instances_dir if instances_dir is not None else process_instances_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _instance_filename(identity)

    # Records which identity this file represents (I2) -- otherwise
    # nothing on disk says what correction a given file is for, and a
    # future filename-scheme bug (like the one this module's own tests
    # already caught once) could silently hand back the wrong workflow
    # instead of failing loudly. `workflow`'s own serialization is
    # parsed back into a plain dict so the whole payload is one real
    # JSON document, not a JSON string nested inside JSON.
    payload = {"identity": asdict(identity), "workflow": json.loads(serialize(workflow))}

    # Write to a sibling temp file, then rename over the target (I3) --
    # matches references_catalog/catalog.py's own established atomic
    # write pattern exactly: os.replace() is atomic on POSIX, so a
    # process killed mid-write leaves the original file untouched.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def load_instance(
    identity: CorrectionIdentity, *, instances_dir: Path | None = None
) -> BpmnWorkflow | None:
    directory = instances_dir if instances_dir is not None else process_instances_dir()
    path = directory / _instance_filename(identity)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_identity = CorrectionIdentity(**payload["identity"])
        if stored_identity != identity:
            raise ValueError(
                f"stored identity {stored_identity!r} does not match requested identity {identity!r}"
            )
        return deserialize(json.dumps(payload["workflow"]))
    except Exception as exc:
        raise CorruptedInstanceError(f"{path}: could not deserialize process instance: {exc}") from exc


def delete_instance(identity: CorrectionIdentity, *, instances_dir: Path | None = None) -> None:
    directory = instances_dir if instances_dir is not None else process_instances_dir()
    (directory / _instance_filename(identity)).unlink(missing_ok=True)
