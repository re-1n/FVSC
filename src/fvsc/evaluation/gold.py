"""Open-meaning gold schema with source and negative-link evaluation.

The schema classifies annotation mechanics, never the possible meaning of a
diary entry. Owner interpretation stays free text. Explicit ``separate`` links
and ``excluded`` composites are first-class data so abstention can be rewarded.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


CaseDecision = Literal["accepted", "split", "excluded", "open"]
EvidenceRole = Literal["primary", "support", "context", "negative"]
LinkDecision = Literal["linked", "context", "separate", "unknown"]
_CASE_DECISIONS = frozenset({"accepted", "split", "excluded", "open"})
_EVIDENCE_ROLES = frozenset({"primary", "support", "context", "negative"})
_LINK_DECISIONS = frozenset({"linked", "context", "separate", "unknown"})
MAX_GOLD_BYTES = 4 * 1024 * 1024


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class EvidenceRef:
    ref: str
    source_id: str | None
    role: EvidenceRole = "support"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", _nonempty(self.ref, field="evidence ref"))
        source = None if self.source_id is None else str(self.source_id).strip() or None
        object.__setattr__(self, "source_id", source)
        if self.role not in _EVIDENCE_ROLES:
            raise ValueError(f"unknown evidence role: {self.role!r}")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceRef":
        return cls(
            ref=value.get("ref", ""),
            source_id=value.get("source_id"),
            role=value.get("role", "support"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref, "source_id": self.source_id, "role": self.role}


@dataclass(frozen=True)
class GoldLink:
    left_ref: str
    right_ref: str
    decision: LinkDecision
    owner_note: str = ""

    def __post_init__(self) -> None:
        left = _nonempty(self.left_ref, field="left_ref")
        right = _nonempty(self.right_ref, field="right_ref")
        if left == right:
            raise ValueError("gold link endpoints must be different")
        if self.decision not in _LINK_DECISIONS:
            raise ValueError(f"unknown link decision: {self.decision!r}")
        object.__setattr__(self, "left_ref", left)
        object.__setattr__(self, "right_ref", right)
        object.__setattr__(self, "owner_note", str(self.owner_note).strip())

    @property
    def key(self) -> tuple[str, str]:
        return tuple(sorted((self.left_ref, self.right_ref)))  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GoldLink":
        return cls(
            left_ref=value.get("left_ref", ""),
            right_ref=value.get("right_ref", ""),
            decision=value.get("decision", "unknown"),
            owner_note=value.get("owner_note", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_ref": self.left_ref,
            "right_ref": self.right_ref,
            "decision": self.decision,
            "owner_note": self.owner_note,
        }


@dataclass(frozen=True)
class GoldCase:
    case_id: str
    title: str
    question: str
    decision: CaseDecision
    evidence: tuple[EvidenceRef, ...]
    links: tuple[GoldLink, ...] = ()
    owner_interpretation: str = ""
    rejected_interpretations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case_id"))
        object.__setattr__(self, "title", _nonempty(self.title, field="title"))
        object.__setattr__(self, "question", _nonempty(self.question, field="question"))
        if self.decision not in _CASE_DECISIONS:
            raise ValueError(f"unknown case decision: {self.decision!r}")
        refs = tuple(item.ref for item in self.evidence)
        if len(refs) != len(set(refs)):
            raise ValueError(f"case {self.case_id} has duplicate evidence refs")
        known = set(refs)
        link_keys: set[tuple[str, str]] = set()
        for link in self.links:
            if link.left_ref not in known or link.right_ref not in known:
                raise ValueError(f"case {self.case_id} link references unknown evidence")
            if link.key in link_keys:
                raise ValueError(f"case {self.case_id} has duplicate gold links")
            link_keys.add(link.key)
        object.__setattr__(self, "owner_interpretation", str(self.owner_interpretation).strip())
        object.__setattr__(
            self,
            "rejected_interpretations",
            tuple(str(value).strip() for value in self.rejected_interpretations if str(value).strip()),
        )

    @property
    def primary_source_ids(self) -> tuple[str, ...]:
        return tuple(
            item.source_id
            for item in self.evidence
            if item.role == "primary" and item.source_id is not None
        )

    @property
    def relevant_source_ids(self) -> tuple[str, ...]:
        return tuple(
            item.source_id
            for item in self.evidence
            if item.role in {"primary", "support"} and item.source_id is not None
        )

    @property
    def context_source_ids(self) -> tuple[str, ...]:
        return tuple(
            item.source_id
            for item in self.evidence
            if item.role == "context" and item.source_id is not None
        )

    @property
    def negative_source_ids(self) -> tuple[str, ...]:
        return tuple(
            item.source_id
            for item in self.evidence
            if item.role == "negative" and item.source_id is not None
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GoldCase":
        evidence = value.get("evidence", [])
        links = value.get("links", [])
        if not isinstance(evidence, list) or not isinstance(links, list):
            raise ValueError("gold evidence and links must be arrays")
        rejected = value.get("rejected_interpretations", [])
        if not isinstance(rejected, list):
            raise ValueError("rejected_interpretations must be an array")
        return cls(
            case_id=value.get("case_id", ""),
            title=value.get("title", ""),
            question=value.get("question", ""),
            decision=value.get("decision", "open"),
            evidence=tuple(EvidenceRef.from_dict(item) for item in evidence),
            links=tuple(GoldLink.from_dict(item) for item in links),
            owner_interpretation=value.get("owner_interpretation", ""),
            rejected_interpretations=tuple(rejected),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "question": self.question,
            "decision": self.decision,
            "evidence": [item.to_dict() for item in self.evidence],
            "links": [item.to_dict() for item in self.links],
            "owner_interpretation": self.owner_interpretation,
            "rejected_interpretations": list(self.rejected_interpretations),
        }


@dataclass(frozen=True)
class GoldSet:
    schema_version: int
    cases: tuple[GoldCase, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported gold schema version: {self.schema_version}")
        case_ids = tuple(item.case_id for item in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("gold set has duplicate case ids")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GoldSet":
        cases = value.get("cases", [])
        if not isinstance(cases, list):
            raise ValueError("gold cases must be an array")
        return cls(
            schema_version=value.get("schema_version", 0),
            cases=tuple(GoldCase.from_dict(item) for item in cases),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cases": [item.to_dict() for item in self.cases],
        }


def load_gold_set(path: Path) -> GoldSet:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular gold file: {source}")
    if source.stat().st_size > MAX_GOLD_BYTES:
        raise ValueError(f"gold file exceeds {MAX_GOLD_BYTES} bytes")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("gold file is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("gold file must contain an object")
    return GoldSet.from_dict(value)


@dataclass(frozen=True)
class RankedSources:
    case_id: str
    source_ids: tuple[str, ...] = ()
    abstained: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case_id"))
        normalized = tuple(str(value).strip() for value in self.source_ids if str(value).strip())
        if len(normalized) != len(set(normalized)):
            raise ValueError("ranked source ids must be unique")
        if self.abstained and normalized:
            raise ValueError("an abstained result cannot contain ranked sources")
        object.__setattr__(self, "source_ids", normalized)


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    reciprocal_rank: float | None
    recall_at_k: float | None
    context_recall_at_k: float | None
    negative_hits_at_k: int
    abstention_correct: bool | None


@dataclass(frozen=True)
class RetrievalEvaluation:
    cases: tuple[CaseEvaluation, ...]
    mean_reciprocal_rank: float | None
    mean_recall_at_k: float | None
    mean_context_recall_at_k: float | None
    negative_hits_at_k: int
    abstention_accuracy: float | None
    evaluated_answer_cases: int
    evaluated_abstention_cases: int
    top_k: int


def _mean(values: Sequence[float]) -> float | None:
    return None if not values else math.fsum(values) / len(values)


def evaluate_rankings(
    gold: GoldSet,
    rankings: Sequence[RankedSources],
    *,
    top_k: int = 10,
) -> RetrievalEvaluation:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    by_case = {item.case_id: item for item in rankings}
    if len(by_case) != len(rankings):
        raise ValueError("rankings contain duplicate case ids")

    results: list[CaseEvaluation] = []
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    context_recalls: list[float] = []
    abstentions: list[float] = []
    total_negative_hits = 0
    for case in gold.cases:
        ranking = by_case.get(case.case_id, RankedSources(case_id=case.case_id, abstained=True))
        top = ranking.source_ids[:top_k]
        if case.decision == "excluded":
            correct = ranking.abstained
            abstentions.append(float(correct))
            results.append(
                CaseEvaluation(
                    case_id=case.case_id,
                    reciprocal_rank=None,
                    recall_at_k=None,
                    context_recall_at_k=None,
                    negative_hits_at_k=0,
                    abstention_correct=correct,
                )
            )
            continue

        primary = set(case.primary_source_ids or case.relevant_source_ids)
        relevant = set(case.relevant_source_ids)
        context = set(case.context_source_ids)
        negatives = set(case.negative_source_ids)
        reciprocal_rank = 0.0
        if not ranking.abstained:
            for index, source_id in enumerate(top, start=1):
                if source_id in primary:
                    reciprocal_rank = 1.0 / index
                    break
        recall = None if not relevant else len(relevant & set(top)) / len(relevant)
        context_recall = None if not context else len(context & set(top)) / len(context)
        negative_hits = len(negatives & set(top))
        reciprocal_ranks.append(reciprocal_rank)
        if recall is not None:
            recalls.append(recall)
        if context_recall is not None:
            context_recalls.append(context_recall)
        total_negative_hits += negative_hits
        results.append(
            CaseEvaluation(
                case_id=case.case_id,
                reciprocal_rank=reciprocal_rank,
                recall_at_k=recall,
                context_recall_at_k=context_recall,
                negative_hits_at_k=negative_hits,
                abstention_correct=None,
            )
        )

    return RetrievalEvaluation(
        cases=tuple(results),
        mean_reciprocal_rank=_mean(reciprocal_ranks),
        mean_recall_at_k=_mean(recalls),
        mean_context_recall_at_k=_mean(context_recalls),
        negative_hits_at_k=total_negative_hits,
        abstention_accuracy=_mean(abstentions),
        evaluated_answer_cases=len(reciprocal_ranks),
        evaluated_abstention_cases=len(abstentions),
        top_k=top_k,
    )


__all__ = [
    "CaseDecision",
    "CaseEvaluation",
    "EvidenceRef",
    "EvidenceRole",
    "GoldCase",
    "GoldLink",
    "GoldSet",
    "LinkDecision",
    "MAX_GOLD_BYTES",
    "RankedSources",
    "RetrievalEvaluation",
    "evaluate_rankings",
    "load_gold_set",
]
