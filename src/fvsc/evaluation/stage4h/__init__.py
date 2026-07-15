"""Controlled Stage 4h attribution-test contracts and orchestration."""

from .contracts import (
    STAGE4H_REQUIRED_ARMS,
    CandidateRole,
    ClaimReviewVerdict,
    FrozenCandidate,
    FrozenCandidateSet,
    Stage4hArm,
    Stage4hCitationReview,
    Stage4hClaimReview,
    Stage4hModelConfig,
    Stage4hOwnerReview,
    Stage4hRunSpec,
    Stage4hThresholds,
    canonical_json,
    content_digest,
    file_sha256,
)

__all__ = [
    "STAGE4H_REQUIRED_ARMS",
    "CandidateRole",
    "ClaimReviewVerdict",
    "FrozenCandidate",
    "FrozenCandidateSet",
    "Stage4hArm",
    "Stage4hCitationReview",
    "Stage4hClaimReview",
    "Stage4hModelConfig",
    "Stage4hOwnerReview",
    "Stage4hRunSpec",
    "Stage4hThresholds",
    "canonical_json",
    "content_digest",
    "file_sha256",
]
