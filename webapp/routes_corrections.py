"""Correction proposals and maker-checker decisions over HTTP -- thin
wrappers around review.corrections, whose own SHACL-backed writes are
where the real integrity guarantees (valid target, no self-approval)
already live. A correction's own URI is opaque to callers -- passed back
verbatim from the propose response for use in the approve/reject path,
base64-encoded only because it's a full URI embedded in a URL path
segment.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from rdflib import Literal, URIRef

from review.corrections import decide_correction, propose_correction

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
    return base64.urlsafe_b64decode(correction_uri_b64.encode()).decode()


@router.post("/corrections")
def propose(request: Request, body: ProposeCorrectionBody, x_reviewer: str = Header(...)):
    correction_uri = propose_correction(
        request.app.state.dataset,
        graph_uri=request.app.state.corrections_graph_uri,
        target_subject=URIRef(body.targetSubject),
        target_predicate=URIRef(body.targetPredicate),
        target_language=body.targetLanguage,
        proposed_value=body.proposedValue,
        prior_value=Literal(body.priorValue, lang=body.targetLanguage),
        proposer=x_reviewer,
        reason=body.reason,
        generated_at=_now(),
    )
    return {"correctionUri": correction_uri}


@router.post("/corrections/{correction_uri_b64}/approve")
def approve(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    try:
        decision_uri = decide_correction(
            request.app.state.dataset, graph_uri=request.app.state.corrections_graph_uri,
            correction_uri=_decode(correction_uri_b64), outcome="approved",
            decider=x_reviewer, reason=body.reason, generated_at=_now(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"decisionUri": decision_uri}


@router.post("/corrections/{correction_uri_b64}/reject")
def reject(request: Request, correction_uri_b64: str, body: DecideCorrectionBody, x_reviewer: str = Header(...)):
    try:
        decision_uri = decide_correction(
            request.app.state.dataset, graph_uri=request.app.state.corrections_graph_uri,
            correction_uri=_decode(correction_uri_b64), outcome="rejected",
            decider=x_reviewer, reason=body.reason, generated_at=_now(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"decisionUri": decision_uri}
