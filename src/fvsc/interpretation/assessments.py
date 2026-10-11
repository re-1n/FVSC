"""Explicit owner assessments for generated interpretation claims."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal, Mapping

from .proposals import InterpretationProposal


AssessmentVerdict = Literal[
    "accepted",
    "partially_accepted",
    "rejected",
    "needs_revision",
]
_VERDICTS = frozenset(
    {"accepted", "partially_accepted", "rejected", "needs_revision"}
)
_SHA256_HEX_LENGTH = 64


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if len(result) != _SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in result
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _content_id(payload: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("assessment payload must contain JSON values") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OwnerProposalAssessment:
    """Append-only owner decision; not itself a canonical evidence event."""

    assessment_id: str
    proposal_id: str
    case_id: str
    verdict: AssessmentVerdict
    accepted_claim_ids: tuple[str, ...]
    rejected_claim_ids: tuple[str, ...]
    reason_tags: tuple[str, ...]
    recorded_at: float
    assessor_role: Literal["owner"] = "owner"

    def __post_init__(self) -> None:
        proposal_id = _digest(self.proposal_id, field="proposal_id")
        case_id = _nonempty(self.case_id, field="case_id")
        if self.verdict not in _VERDICTS:
            raise ValueError(f"unknown assessment verdict: {self.verdict!r}")
        if self.assessor_role != "owner":
            raise ValueError("proposal assessments must be made by the owner")
        accepted = tuple(
            _digest(value, field="accepted claim id")
            for value in self.accepted_claim_ids
        )
        rejected = tuple(
            _digest(value, field="rejected claim id")
            for value in self.rejected_claim_ids
        )
        if len(accepted) != len(set(accepted)) or len(rejected) != len(set(rejected)):
            raise ValueError("assessment claim ids must be unique")
        if set(accepted) & set(rejected):
            raise ValueError("a claim cannot be both accepted and rejected")
        reason_tags = tuple(
            _nonempty(value, field="reason tag") for value in self.reason_tags
        )
        if len(reason_tags) != len(set(reason_tags)):
            raise ValueError("assessment reason tags must be unique")
        recorded_at = float(self.recorded_at)
        if not math.isfinite(recorded_at):
            raise ValueError("recorded_at must be finite")
        payload = {
            "accepted_claim_ids": list(accepted),
            "assessor_role": "owner",
            "case_id": case_id,
            "proposal_id": proposal_id,
            "reason_tags": list(reason_tags),
            "recorded_at": recorded_at,
            "rejected_claim_ids": list(rejected),
            "verdict": self.verdict,
        }
        if self.assessment_id != _content_id(payload):
            raise ValueError("assessment_id does not match the canonical assessment payload")
        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "accepted_claim_ids", accepted)
        object.__setattr__(self, "rejected_claim_ids", rejected)
        object.__setattr__(self, "reason_tags", reason_tags)
        object.__setattr__(self, "recorded_at", recorded_at)

    @classmethod
    def create(
        cls,
        proposal: InterpretationProposal,
        *,
        case_id: str,
        verdict: AssessmentVerdict,
        accepted_claim_ids: tuple[str, ...] = (),
        rejected_claim_ids: tuple[str, ...] = (),
        reason_tags: tuple[str, ...] = (),
        recorded_at: float,
    ) -> "OwnerProposalAssessment":
        payload = {
            "accepted_claim_ids": list(accepted_claim_ids),
            "assessor_role": "owner",
            "case_id": str(case_id).strip(),
            "proposal_id": proposal.proposal_id,
            "reason_tags": [str(value).strip() for value in reason_tags],
            "recorded_at": float(recorded_at),
            "rejected_claim_ids": list(rejected_claim_ids),
            "verdict": verdict,
        }
        assessment = cls(
            assessment_id=_content_id(payload),
            proposal_id=proposal.proposal_id,
            case_id=payload["case_id"],
            verdict=verdict,
            accepted_claim_ids=accepted_claim_ids,
            rejected_claim_ids=rejected_claim_ids,
            reason_tags=tuple(payload["reason_tags"]),
            recorded_at=payload["recorded_at"],
        )
        assessment.verify(proposal)
        return assessment

    def verify(self, proposal: InterpretationProposal) -> None:
        if proposal.proposal_id != self.proposal_id:
            raise ValueError("assessment does not target this proposal")
        known = {claim.claim_id for claim in proposal.claims}
        accepted = set(self.accepted_claim_ids)
        rejected = set(self.rejected_claim_ids)
        if not accepted | rejected <= known:
            raise ValueError("assessment references an unknown proposal claim")
        if self.verdict == "accepted" and (accepted != known or rejected):
            raise ValueError("accepted verdict must accept every claim")
        if self.verdict == "rejected" and (rejected != known or accepted):
            raise ValueError("rejected verdict must reject every claim")
        if self.verdict == "partially_accepted" and (
            not accepted or accepted == known
        ):
            raise ValueError("partial verdict must accept a proper non-empty claim subset")
        if self.verdict == "needs_revision" and accepted == known:
            raise ValueError("needs_revision cannot accept every claim")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "proposal_id": self.proposal_id,
            "case_id": self.case_id,
            "verdict": self.verdict,
            "accepted_claim_ids": list(self.accepted_claim_ids),
            "rejected_claim_ids": list(self.rejected_claim_ids),
            "reason_tags": list(self.reason_tags),
            "recorded_at": self.recorded_at,
            "assessor_role": self.assessor_role,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OwnerProposalAssessment":
        accepted = value.get("accepted_claim_ids", [])
        rejected = value.get("rejected_claim_ids", [])
        reason_tags = value.get("reason_tags", [])
        if not isinstance(accepted, list) or not isinstance(rejected, list):
            raise ValueError("assessment claim ids must be arrays")
        if not isinstance(reason_tags, list):
            raise ValueError("assessment reason_tags must be an array")
        return cls(
            assessment_id=value.get("assessment_id", ""),
            proposal_id=value.get("proposal_id", ""),
            case_id=value.get("case_id", ""),
            verdict=value.get("verdict", "needs_revision"),
            accepted_claim_ids=tuple(accepted),
            rejected_claim_ids=tuple(rejected),
            reason_tags=tuple(reason_tags),
            recorded_at=value.get("recorded_at", float("nan")),
            assessor_role=value.get("assessor_role", "owner"),
        )


__all__ = ["AssessmentVerdict", "OwnerProposalAssessment"]
