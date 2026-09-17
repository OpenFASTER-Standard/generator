"""Correction proposals and maker-checker decisions over HTTP -- thin
wrappers around review.corrections, whose own SHACL-backed writes are
where the real integrity guarantees (valid target, no self-approval)
already live. A correction's own URI is opaque to callers -- passed back
verbatim from the propose response for use in the approve/reject path,
base64-encoded only because it's a full URI embedded in a URL path
segment.

`review.corrections` signals every integrity failure it enforces (an
unknown or already-decided correction, a self-approval, any other
SHACL-rejected write) as a `ValueError`, which `webapp.errors` -- installed
once on the app -- translates to a 400 for every endpoint here uniformly.
That replaces the per-route `try/except ValueError` this module used to
carry on approve/reject only, which is precisely why propose was missing
the same guard.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel
from rdflib import Literal

from review.corrections import decide_correction, propose_correction
from webapp.errors import validated_iri

router = APIRouter(prefix="/api")


class ProposeCorrectionBody(BaseModel):
    targetSubject: str
    targetPredicate: str
    targetLanguage: str
    proposedValue: str
    priorValue: str
    reason: str


class DecideCorrectionBody(BaseModel):
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _decode(correction_uri_b64: str) -> str:
    # Both failure modes here already raise a ValueError subclass
    # (binascii.Error for malformed base64, UnicodeDecodeError for
    # non-UTF-8 bytes), so webapp.errors' ValueError rule turns a
    # garbage path segment into a 400 with no extra handling needed.
    return base64.urlsafe_b64decode(correction_uri_b64.encode()).decode()


@router.post("/corrections")
def propose(request: Request, body: ProposeCorrectionBody, x_reviewer: str = Header(...)):
    correction_uri = propose_correction(
        request.app.state.dataset,
        graph_uri=request.app.state.corrections_graph_uri,
        target_subject=validated_iri(body.targetSubject, "targetSubject"),
        target_predicate=validated_iri(body.targetPredicate, "targetPredicate"),
        target_language=body.targetLanguage,
        proposed_value=body.proposedValue,
        prior_value=Literal(body.priorValue, lang=body.targetLanguage),
        proposer=x_reviewer,
        reason=body.reason,
        generated_at=_now(),
    )
    return {"correctionUri": correction_uri}


def _decide(request: Request, correction_uri_b64: str, outcome: str, reason: str, decider: str) -> dict:
    decision_uri = decide_correction(
        request.app.state.dataset, graph_uri=request.app.state.corrections_graph_uri,
        correction_uri=_decode(correction_uri_b64), outcome=outcome,
        decider=decider, reason=reason, generated_at=_now(),
    )
    return {"decisionUri": decision_uri}


@router.post("/corrections/{correction_uri_b64}/approve")
def approve(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    return _decide(request, correction_uri_b64, "approved", body.reason, x_reviewer)


@router.post("/corrections/{correction_uri_b64}/reject")
def reject(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    return _decide(request, correction_uri_b64, "rejected", body.reason, x_reviewer)
