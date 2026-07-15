"""Deterministically freeze Stage 4h source candidates before generation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping, Protocol, Sequence

from ...ingest import SourceDocument
from ...retrieval import LexicalSearchIndex, expand_source_context
from ..gold import GoldCase
from .contracts import (
    FrozenCandidate,
    FrozenCandidateSet,
    Stage4hRunSpec,
    content_digest,
)


class StructuralHit(Protocol):
    source_id: str
    score: float
    evidence_event_ids: tuple[str, ...]


class StructuralSearchIndex(Protocol):
    def search(self, query: str, *, top_k: int = 10) -> Sequence[StructuralHit]: ...


def corpus_digest(documents: Iterable[SourceDocument]) -> str:
    """Identify one transient corpus without serializing any source body."""
    ordered = tuple(sorted(documents, key=lambda item: item.source_id))
    source_ids = tuple(item.source_id for item in ordered)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Stage 4h corpus source ids must be unique")
    return content_digest(
        {
            "documents": [
                {
                    "adapter": item.adapter,
                    "observed_at": item.observed_at,
                    "source_id": item.source_id,
                    "source_kind": item.source_kind,
                    "source_revision": item.source_revision,
                }
                for item in ordered
            ],
            "schema_version": 1,
        }
    )


def _document_index(
    documents: Iterable[SourceDocument],
) -> tuple[tuple[SourceDocument, ...], dict[str, SourceDocument]]:
    ordered = tuple(sorted(documents, key=lambda item: item.source_id))
    by_id = {item.source_id: item for item in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("Stage 4h documents must have unique source ids")
    return ordered, by_id


def _append_context(
    *,
    candidates: list[FrozenCandidate],
    ranked_source_ids: tuple[str, ...],
    documents: tuple[SourceDocument, ...],
    by_id: Mapping[str, SourceDocument],
    max_depth: int,
    cap: int,
) -> None:
    if max_depth == 0 or len(candidates) >= cap:
        return
    known = {item.source_id for item in candidates}
    for parent_source_id in ranked_source_ids:
        for document in expand_source_context(
            documents,
            parent_source_id,
            max_depth=max_depth,
        ):
            if document.source_id in known:
                continue
            if document.source_id not in by_id:
                raise AssertionError("context expansion returned an unknown document")
            candidates.append(
                FrozenCandidate(
                    rank=len(candidates) + 1,
                    source_id=document.source_id,
                    source_revision=document.source_revision,
                    role="context",
                    expanded_from_source_id=parent_source_id,
                )
            )
            known.add(document.source_id)
            if len(candidates) >= cap:
                return


def _lexical_candidates(
    *,
    case: GoldCase,
    spec: Stage4hRunSpec,
    documents: tuple[SourceDocument, ...],
    by_id: Mapping[str, SourceDocument],
    index: LexicalSearchIndex,
) -> tuple[FrozenCandidate, ...]:
    hits = index.search(case.question, top_k=spec.top_k)
    candidates: list[FrozenCandidate] = []
    for hit in hits:
        document = by_id.get(hit.source_id)
        if document is None or document.source_revision != hit.document.source_revision:
            raise ValueError(
                "lexical index does not match the preregistered Stage 4h corpus"
            )
        candidates.append(
            FrozenCandidate(
                rank=len(candidates) + 1,
                source_id=hit.source_id,
                source_revision=document.source_revision,
                role="ranked",
                score=hit.score,
            )
        )
    _append_context(
        candidates=candidates,
        ranked_source_ids=tuple(hit.source_id for hit in hits),
        documents=documents,
        by_id=by_id,
        max_depth=spec.context_depth,
        cap=spec.prompt_source_cap,
    )
    return tuple(candidates)


def _oracle_candidates(
    *,
    case: GoldCase,
    spec: Stage4hRunSpec,
    by_id: Mapping[str, SourceDocument],
) -> tuple[FrozenCandidate, ...]:
    selected = tuple(
        item
        for item in case.evidence
        if item.role in {"primary", "support", "context"} and item.source_id is not None
    )
    if len(selected) > spec.prompt_source_cap:
        raise ValueError(
            f"case {case.case_id} oracle evidence exceeds prompt_source_cap; "
            "do not silently truncate owner gold"
        )
    candidates: list[FrozenCandidate] = []
    seen: set[str] = set()
    for item in selected:
        source_id = item.source_id
        assert source_id is not None
        if source_id in seen:
            raise ValueError(f"case {case.case_id} repeats one oracle source id")
        document = by_id.get(source_id)
        if document is None:
            raise ValueError(
                f"case {case.case_id} oracle source is absent from the frozen corpus: "
                f"{source_id}"
            )
        candidates.append(
            FrozenCandidate(
                rank=len(candidates) + 1,
                source_id=source_id,
                source_revision=document.source_revision,
                role="context" if item.role == "context" else "oracle",
            )
        )
        seen.add(source_id)
    return tuple(candidates)


def _structural_candidates(
    *,
    case: GoldCase,
    spec: Stage4hRunSpec,
    documents: tuple[SourceDocument, ...],
    by_id: Mapping[str, SourceDocument],
    index: StructuralSearchIndex,
) -> tuple[FrozenCandidate, ...]:
    hits = tuple(index.search(case.question, top_k=spec.top_k))
    candidates: list[FrozenCandidate] = []
    for hit in hits:
        document = by_id.get(hit.source_id)
        if document is None:
            raise ValueError(
                f"structural retrieval returned source outside the corpus: {hit.source_id}"
            )
        candidates.append(
            FrozenCandidate(
                rank=len(candidates) + 1,
                source_id=hit.source_id,
                source_revision=document.source_revision,
                role="ranked",
                score=hit.score,
                evidence_event_ids=tuple(hit.evidence_event_ids),
            )
        )
    ranked_source_ids = tuple(item.source_id for item in candidates)
    _append_context(
        candidates=candidates,
        ranked_source_ids=ranked_source_ids,
        documents=documents,
        by_id=by_id,
        max_depth=spec.context_depth,
        cap=spec.prompt_source_cap,
    )
    return tuple(candidates)


@dataclass(frozen=True)
class FrozenCandidateBundle:
    bundle_id: str
    run_id: str
    candidate_sets: tuple[FrozenCandidateSet, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported frozen-candidate bundle version")
        if any(item.run_id != self.run_id for item in self.candidate_sets):
            raise ValueError("candidate bundle contains another run id")
        keys = tuple((item.case_id, item.arm) for item in self.candidate_sets)
        if len(keys) != len(set(keys)):
            raise ValueError("candidate bundle contains duplicate case/arm pairs")
        if keys != tuple(sorted(keys)):
            raise ValueError("candidate bundle must be sorted by case and arm")
        payload = self._payload()
        if self.bundle_id != content_digest(payload):
            raise ValueError("bundle_id does not match the frozen candidate bundle")

    def _payload(self) -> dict[str, Any]:
        return {
            "candidate_sets": [item.to_dict() for item in self.candidate_sets],
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        spec: Stage4hRunSpec,
        candidate_sets: Iterable[FrozenCandidateSet],
    ) -> "FrozenCandidateBundle":
        ordered = tuple(sorted(candidate_sets, key=lambda item: (item.case_id, item.arm)))
        actual = {(item.case_id, item.arm) for item in ordered}
        expected = {(case_id, arm) for case_id in spec.case_ids for arm in spec.arms}
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"candidate bundle does not cover the run; missing={missing}, extra={extra}"
            )
        payload = {
            "candidate_sets": [item.to_dict() for item in ordered],
            "run_id": spec.run_id,
            "schema_version": 1,
        }
        return cls(
            bundle_id=content_digest(payload),
            run_id=spec.run_id,
            candidate_sets=ordered,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_id": self.bundle_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenCandidateBundle":
        raw_sets = value.get("candidate_sets", [])
        if not isinstance(raw_sets, list):
            raise ValueError("candidate_sets must be an array")
        return cls(
            bundle_id=value.get("bundle_id", ""),
            run_id=value.get("run_id", ""),
            candidate_sets=tuple(FrozenCandidateSet.from_dict(item) for item in raw_sets),
            schema_version=value.get("schema_version", 0),
        )

    def for_case_arm(self, case_id: str, arm: str) -> FrozenCandidateSet:
        for item in self.candidate_sets:
            if item.case_id == case_id and item.arm == arm:
                return item
        raise KeyError((case_id, arm))


def freeze_stage4h_candidates(
    *,
    spec: Stage4hRunSpec,
    cases: Iterable[GoldCase],
    documents: Iterable[SourceDocument],
    lexical_index: LexicalSearchIndex,
    structural_index: StructuralSearchIndex,
    lexical_method: str = "lexical-char-tfidf-v1",
    structural_method: str = "judgment-char-tfidf-v1",
) -> FrozenCandidateBundle:
    """Freeze A0/A1/A2/A4 candidates with no hidden cross-arm fallback."""
    ordered_documents, by_id = _document_index(documents)
    actual_corpus_digest = corpus_digest(ordered_documents)
    if actual_corpus_digest != spec.corpus_sha256:
        raise ValueError("Stage 4h corpus does not match the preregistered digest")
    case_values = tuple(cases)
    by_case = {case.case_id: case for case in case_values}
    if len(by_case) != len(case_values):
        raise ValueError("Stage 4h cases must have unique ids")
    selected: list[GoldCase] = []
    for case_id in spec.case_ids:
        case = by_case.get(case_id)
        if case is None:
            raise ValueError(f"Stage 4h case is missing: {case_id}")
        missing_sources = sorted(
            {
                item.source_id
                for item in case.evidence
                if item.source_id is not None and item.source_id not in by_id
            }
        )
        if missing_sources:
            raise ValueError(
                f"case {case.case_id} gold sources are absent from the frozen corpus: "
                f"{missing_sources}"
            )
        selected.append(case)

    frozen: list[FrozenCandidateSet] = []
    for case in selected:
        lexical = _lexical_candidates(
            case=case,
            spec=spec,
            documents=ordered_documents,
            by_id=by_id,
            index=lexical_index,
        )
        oracle = _oracle_candidates(case=case, spec=spec, by_id=by_id)
        structural = _structural_candidates(
            case=case,
            spec=spec,
            documents=ordered_documents,
            by_id=by_id,
            index=structural_index,
        )
        candidates_by_arm = {
            "A0": (lexical_method, lexical),
            "A1": (lexical_method, lexical),
            "A2": ("owner-gold-oracle-v1", oracle),
            "A3": (lexical_method, lexical),
            "A4": (structural_method, structural),
        }
        for arm in spec.arms:
            method, arm_candidates = candidates_by_arm[arm]
            frozen.append(
                FrozenCandidateSet.create(
                    run_id=spec.run_id,
                    case_id=case.case_id,
                    arm=arm,
                    retrieval_method=method,
                    candidates=arm_candidates,
                )
            )
    return FrozenCandidateBundle.create(spec=spec, candidate_sets=frozen)


def candidate_bundle_json(bundle: FrozenCandidateBundle) -> str:
    return json.dumps(
        bundle.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


__all__ = [
    "FrozenCandidateBundle",
    "StructuralSearchIndex",
    "candidate_bundle_json",
    "corpus_digest",
    "freeze_stage4h_candidates",
]
