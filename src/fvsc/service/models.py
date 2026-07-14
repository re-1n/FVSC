"""Validated HTTP schemas for the thin local FVSC service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..interpretation import InterpretationProposal
from .runtime import RuntimeSearchHit, RuntimeStatus


class _StrictModel(BaseModel):
    model_config = {"extra": "forbid"}


class StatusResponse(_StrictModel):
    loaded: bool
    adapter: str | None
    cache_path: str
    source_count: int
    ledger_events: int
    active_events: int
    exact_judgments: int
    owner_feedback_events: int
    snapshot_id: str | None

    @classmethod
    def from_runtime(cls, status: RuntimeStatus) -> "StatusResponse":
        return cls(**status.to_dict())


class SearchRequest(_StrictModel):
    query: str = Field(min_length=1, max_length=8_192)
    top_k: int = Field(default=10, ge=1, le=100)
    context_depth: int = Field(default=1, ge=0, le=4)


class SearchHitResponse(_StrictModel):
    source_id: str
    source_revision: str
    observed_at: float
    source_kind: str
    score: float
    preview: str
    context_source_ids: list[str]
    evidence_event_ids: list[str]

    @classmethod
    def from_runtime(cls, hit: RuntimeSearchHit) -> "SearchHitResponse":
        return cls(**hit.to_dict())


class SearchResponse(_StrictModel):
    ranking: Literal["lexical-char-ngram-v1"] = "lexical-char-ngram-v1"
    semantic_reranking: bool = False
    hits: list[SearchHitResponse]


class SourceResponse(_StrictModel):
    source_id: str
    source_revision: str
    observed_at: float
    source_kind: str
    text: str


class FeedbackRequest(_StrictModel):
    target_event_id: str = Field(min_length=64, max_length=64)
    action: Literal["confirm", "reject", "contextualize"]
    context_tags: list[str] = Field(default_factory=list, max_length=64)
    observed_at: float | None = None


class FeedbackResponse(_StrictModel):
    event_id: str
    target_event_id: str
    action: Literal["confirm", "reject", "contextualize"]
    ledger_digest: str


class HealthResponse(_StrictModel):
    status: Literal["ok", "unconfigured"]
    configured: bool
    loaded: bool
    interpretation_configured: bool
    startup_error: Literal["cache_stale", "cache_invalid"] | None = None


class InterpretRequest(_StrictModel):
    question: str = Field(min_length=1, max_length=8_192)
    top_k: int = Field(default=5, ge=1, le=20)
    context_depth: int = Field(default=1, ge=0, le=4)


class ProposalCitationResponse(_StrictModel):
    citation_id: str
    source_id: str
    source_revision: str
    start: int
    end: int
    text_sha256: str
    evidence_event_ids: list[str]


class ProposalClaimResponse(_StrictModel):
    claim_id: str
    text: str
    citation_ids: list[str]
    support_level: str


class InterpretationProposalResponse(_StrictModel):
    proposal_id: str
    question: str
    answer: str
    claims: list[ProposalClaimResponse]
    citations: list[ProposalCitationResponse]
    output_type: str
    support_level: str
    interpretation_layer: int
    producer: str
    model: str | None
    prompt_version: str
    generated_at: float
    retrieval_method: str
    metadata: dict[str, Any]
    defeasible: bool

    @classmethod
    def from_proposal(
        cls,
        proposal: InterpretationProposal,
    ) -> "InterpretationProposalResponse":
        return cls(**proposal.to_dict())


class InterpretationBackendStatusResponse(_StrictModel):
    configured: bool
    backend_id: str | None
    model: str | None
    reachable: bool | None
    local_models: list[str]


__all__ = [
    "FeedbackRequest",
    "FeedbackResponse",
    "HealthResponse",
    "InterpretRequest",
    "InterpretationBackendStatusResponse",
    "InterpretationProposalResponse",
    "ProposalCitationResponse",
    "ProposalClaimResponse",
    "SearchHitResponse",
    "SearchRequest",
    "SearchResponse",
    "SourceResponse",
    "StatusResponse",
]
