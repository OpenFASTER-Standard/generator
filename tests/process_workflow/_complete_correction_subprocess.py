"""Invoked via `subprocess.run([sys.executable, __file__, ...])` by
test_end_to_end.py -- runs in a genuinely separate Python process so
that loading a persisted process instance here proves real cross-process
resumability, not just that one Python object survived a round-trip in
the same interpreter.

Usage: python _complete_correction_subprocess.py <fact_key>
       <leaf_reference_id> <drift_kind> <fingerprint> <corrected_fact_key>

Prints "True" or "False" (the real return value of
complete_pending_correction) to stdout.
"""
import sys

from process_workflow.orchestration import complete_pending_correction
from process_workflow.store import CorrectionIdentity

if __name__ == "__main__":
    fact_key, leaf_reference_id, drift_kind, fingerprint, corrected_fact_key = sys.argv[1:6]
    identity = CorrectionIdentity(
        fact_key=fact_key, leaf_reference_id=leaf_reference_id,
        drift_kind=drift_kind, fingerprint=fingerprint,
    )
    result = complete_pending_correction(identity, corrected_fact_key=corrected_fact_key)
    print(result)
