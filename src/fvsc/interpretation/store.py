"""Atomic local journal for proposals and owner assessments outside evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping
import uuid

from .assessments import AssessmentVerdict, OwnerProposalAssessment
from .proposals import InterpretationProposal


INTERPRETATION_JOURNAL_MAGIC = "fvsc-interpretation-journal"
INTERPRETATION_JOURNAL_VERSION = 1
DEFAULT_INTERPRETATION_JOURNAL_RELATIVE_PATH = Path(".fvsc") / "interpretations.json"
MAX_INTERPRETATION_JOURNAL_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class InterpretationJournal:
    proposals: tuple[InterpretationProposal, ...] = ()
    assessments: tuple[OwnerProposalAssessment, ...] = ()

    def __post_init__(self) -> None:
        proposal_ids = tuple(item.proposal_id for item in self.proposals)
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("interpretation journal contains duplicate proposals")
        assessment_ids = tuple(item.assessment_id for item in self.assessments)
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ValueError("interpretation journal contains duplicate assessments")
        proposals = {item.proposal_id: item for item in self.proposals}
        for assessment in self.assessments:
            proposal = proposals.get(assessment.proposal_id)
            if proposal is None:
                raise ValueError("assessment references an unknown journal proposal")
            assessment.verify(proposal)

    @property
    def digest(self) -> str:
        identities = [
            *(f"proposal:{item.proposal_id}" for item in self.proposals),
            *(f"assessment:{item.assessment_id}" for item in self.assessments),
        ]
        return hashlib.sha256("\n".join(identities).encode("ascii")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "magic": INTERPRETATION_JOURNAL_MAGIC,
            "version": INTERPRETATION_JOURNAL_VERSION,
            "digest": self.digest,
            "proposals": [item.to_dict() for item in self.proposals],
            "assessments": [item.to_dict() for item in self.assessments],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterpretationJournal":
        if value.get("magic") != INTERPRETATION_JOURNAL_MAGIC:
            raise ValueError("invalid interpretation journal magic")
        if value.get("version") != INTERPRETATION_JOURNAL_VERSION:
            raise ValueError("unsupported interpretation journal version")
        raw_proposals = value.get("proposals", [])
        raw_assessments = value.get("assessments", [])
        if not isinstance(raw_proposals, list) or not isinstance(raw_assessments, list):
            raise ValueError("journal proposals and assessments must be arrays")
        journal = cls(
            proposals=tuple(
                InterpretationProposal.from_dict(item) for item in raw_proposals
            ),
            assessments=tuple(
                OwnerProposalAssessment.from_dict(item) for item in raw_assessments
            ),
        )
        if value.get("digest") != journal.digest:
            raise ValueError("interpretation journal digest mismatch")
        return journal


def load_interpretation_journal(path: Path) -> InterpretationJournal:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular interpretation journal: {source}")
    if source.stat().st_size > MAX_INTERPRETATION_JOURNAL_BYTES:
        raise ValueError("interpretation journal exceeds its size limit")
    try:
        decoded = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("interpretation journal is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("interpretation journal must contain a JSON object")
    return InterpretationJournal.from_dict(decoded)


def _fsync_directory(directory: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_interpretation_journal(path: Path, journal: InterpretationJournal) -> None:
    if not isinstance(journal, InterpretationJournal):
        raise TypeError("journal must be an InterpretationJournal")
    target = Path(path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError(f"refusing non-regular interpretation journal target: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        journal.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(payload) > MAX_INTERPRETATION_JOURNAL_BYTES:
        raise ValueError("interpretation journal exceeds its size limit")
    temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


class InterpretationStore:
    """Single-process transactional facade over the local journal."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._journal = (
            load_interpretation_journal(self.path)
            if self.path.is_symlink() or self.path.exists()
            else InterpretationJournal()
        )

    @property
    def journal(self) -> InterpretationJournal:
        with self._lock:
            return self._journal

    def get_proposal(self, proposal_id: str) -> InterpretationProposal | None:
        requested = str(proposal_id).strip()
        with self._lock:
            return next(
                (item for item in self._journal.proposals if item.proposal_id == requested),
                None,
            )

    def append_proposal(self, proposal: InterpretationProposal) -> bool:
        if not isinstance(proposal, InterpretationProposal):
            raise TypeError("store accepts InterpretationProposal instances only")
        with self._lock:
            existing = self.get_proposal(proposal.proposal_id)
            if existing is not None:
                if existing != proposal:
                    raise ValueError("proposal id collision in interpretation journal")
                return False
            trial = InterpretationJournal(
                proposals=(*self._journal.proposals, proposal),
                assessments=self._journal.assessments,
            )
            save_interpretation_journal(self.path, trial)
            self._journal = trial
            return True

    def append_assessment(self, assessment: OwnerProposalAssessment) -> bool:
        if not isinstance(assessment, OwnerProposalAssessment):
            raise TypeError("store accepts OwnerProposalAssessment instances only")
        with self._lock:
            proposal = self.get_proposal(assessment.proposal_id)
            if proposal is None:
                raise ValueError("assessment references an unknown stored proposal")
            assessment.verify(proposal)
            for existing in self._journal.assessments:
                if existing.assessment_id == assessment.assessment_id:
                    if existing != assessment:
                        raise ValueError("assessment id collision in interpretation journal")
                    return False
            trial = InterpretationJournal(
                proposals=self._journal.proposals,
                assessments=(*self._journal.assessments, assessment),
            )
            save_interpretation_journal(self.path, trial)
            self._journal = trial
            return True

    def record_assessment(
        self,
        *,
        proposal_id: str,
        case_id: str,
        verdict: AssessmentVerdict,
        accepted_claim_ids: tuple[str, ...] = (),
        rejected_claim_ids: tuple[str, ...] = (),
        reason_tags: tuple[str, ...] = (),
        recorded_at: float,
    ) -> OwnerProposalAssessment:
        with self._lock:
            proposal = self.get_proposal(proposal_id)
            if proposal is None:
                raise ValueError("proposal is not present in the interpretation journal")
            assessment = OwnerProposalAssessment.create(
                proposal,
                case_id=case_id,
                verdict=verdict,
                accepted_claim_ids=accepted_claim_ids,
                rejected_claim_ids=rejected_claim_ids,
                reason_tags=reason_tags,
                recorded_at=recorded_at,
            )
            self.append_assessment(assessment)
            return assessment

    def latest_assessment(
        self,
        proposal_id: str,
    ) -> OwnerProposalAssessment | None:
        requested = str(proposal_id).strip()
        with self._lock:
            candidates = tuple(
                item
                for item in self._journal.assessments
                if item.proposal_id == requested
            )
            return (
                max(candidates, key=lambda item: (item.recorded_at, item.assessment_id))
                if candidates
                else None
            )


__all__ = [
    "DEFAULT_INTERPRETATION_JOURNAL_RELATIVE_PATH",
    "INTERPRETATION_JOURNAL_MAGIC",
    "INTERPRETATION_JOURNAL_VERSION",
    "InterpretationJournal",
    "InterpretationStore",
    "MAX_INTERPRETATION_JOURNAL_BYTES",
    "load_interpretation_journal",
    "save_interpretation_journal",
]
