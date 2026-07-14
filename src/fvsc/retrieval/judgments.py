"""Source-cited retrieval over extracted judgments, without raw document text."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
import unicodedata

from ..evidence import EvidenceLedger, EvidencePolicy, FeedbackState
from ..ingest.russian_judgments import Morphology, Pymorphy3Morphology


_WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", flags=re.UNICODE)
_CONTENT_POS = frozenset(
    {"NOUN", "VERB", "INFN", "ADJF", "ADJS", "PRTF", "PRTS", "ADVB"}
)
_QUERY_STOPWORDS = frozenset(
    {
        "быть",
        "в",
        "и",
        "из",
        "как",
        "какой",
        "который",
        "мой",
        "на",
        "не",
        "но",
        "о",
        "он",
        "она",
        "они",
        "роль",
        "с",
        "такой",
        "то",
        "что",
        "это",
    }
)


@dataclass(frozen=True)
class JudgmentHit:
    source_id: str
    score: float
    evidence_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.source_id).strip():
            raise ValueError("judgment hit source_id must not be empty")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0 + 1e-12:
            raise ValueError("judgment hit score must be finite and in [0, 1]")
        if not self.evidence_event_ids:
            raise ValueError("judgment hit requires evidence event ids")


def _character_ngrams(term: str, *, minimum: int = 3, maximum: int = 5) -> Counter[str]:
    normalized = unicodedata.normalize("NFKC", term).casefold()
    padded = f" {normalized} "
    result: Counter[str] = Counter()
    for size in range(minimum, maximum + 1):
        if len(padded) >= size:
            result.update(
                padded[index : index + size]
                for index in range(len(padded) - size + 1)
            )
    return result


def _add_term(features: dict[str, float], term: str, *, weight: float) -> None:
    normalized = " ".join(unicodedata.normalize("NFKC", term).casefold().split())
    if not normalized:
        return
    features[f"term:{normalized}"] = features.get(f"term:{normalized}", 0.0) + weight
    for gram, frequency in _character_ngrams(normalized).items():
        key = f"char:{gram}"
        features[key] = features.get(key, 0.0) + 0.12 * weight * frequency


def _add_relation(features: dict[str, float], relation: str, *, weight: float) -> None:
    normalized = relation.casefold().strip()
    if not normalized:
        return
    features[f"rel:{normalized}"] = features.get(f"rel:{normalized}", 0.0) + weight
    if ":" not in normalized:
        _add_term(features, normalized, weight=0.5 * weight)


def _query_features(query: str, morphology: Morphology) -> dict[str, float]:
    features: dict[str, float] = {}
    for match in _WORD_RE.finditer(unicodedata.normalize("NFKC", query)):
        analysis = morphology.analyze(match.group())
        lemma = analysis.lemma.casefold().strip()
        if analysis.pos not in _CONTENT_POS or lemma in _QUERY_STOPWORDS or len(lemma) < 2:
            continue
        _add_term(features, lemma, weight=1.0)
        if analysis.pos in {"VERB", "INFN"}:
            features[f"rel:{lemma}"] = features.get(f"rel:{lemma}", 0.0) + 1.25
    return features


def _tfidf(
    features: dict[str, float],
    *,
    document_frequency: Counter[str],
    document_count: int,
) -> dict[str, float]:
    return {
        key: (1.0 + math.log(max(value, 1e-12)))
        * (math.log((1.0 + document_count) / (1.0 + document_frequency[key])) + 1.0)
        for key, value in features.items()
        if value > 0.0
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    left_norm = math.sqrt(math.fsum(value * value for value in left.values()))
    right_norm = math.sqrt(math.fsum(value * value for value in right.values()))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = math.fsum(value * right.get(key, 0.0) for key, value in left.items())
    return min(max(dot / (left_norm * right_norm), 0.0), 1.0)


class JudgmentSearchIndex:
    """Reusable in-memory index over policy-selected judgment events."""

    def __init__(
        self,
        ledger: EvidenceLedger,
        *,
        morphology: Morphology | None = None,
        policy: EvidencePolicy | None = None,
    ) -> None:
        self.morphology = morphology or Pymorphy3Morphology()
        self.policy = policy
        feedback = FeedbackState.from_ledger(ledger)
        source_features: dict[str, dict[str, float]] = {}
        evidence_ids: dict[str, set[str]] = {}
        for event in sorted(ledger.active_events, key=lambda item: item.event_id):
            if event.subject is None or event.relation is None or event.object is None:
                continue
            status = feedback.confirmation_status_for(event.event_id)
            if policy is not None and not policy.allows(
                event,
                confirmation_status=status,
            ):
                continue
            if event.context.get("structural_role") is not None:
                continue
            weight = event.modality * event.intensity * event.confidence
            if weight <= 0.0:
                continue
            features = source_features.setdefault(event.source_id, {})
            _add_term(features, event.subject, weight=weight)
            _add_relation(features, event.relation, weight=1.2 * weight)
            _add_term(features, event.object, weight=weight)
            evidence_ids.setdefault(event.source_id, set()).add(event.event_id)

        document_frequency: Counter[str] = Counter()
        for features in source_features.values():
            document_frequency.update(features.keys())
        self.document_frequency = document_frequency
        self.document_count = len(source_features)
        self.source_vectors = {
            source_id: _tfidf(
                features,
                document_frequency=document_frequency,
                document_count=self.document_count,
            )
            for source_id, features in source_features.items()
        }
        self.evidence_ids = {
            source_id: tuple(sorted(values))
            for source_id, values in evidence_ids.items()
        }

    def search(self, query: str, *, top_k: int = 10) -> tuple[JudgmentHit, ...]:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        query_value = str(query).strip()
        if not query_value or not self.source_vectors:
            return ()
        features = _query_features(query_value, self.morphology)
        if not features:
            return ()
        query_vector = _tfidf(
            features,
            document_frequency=self.document_frequency,
            document_count=self.document_count,
        )
        hits = [
            JudgmentHit(
                source_id=source_id,
                score=score,
                evidence_event_ids=self.evidence_ids[source_id],
            )
            for source_id, vector in self.source_vectors.items()
            if (score := _cosine(vector, query_vector)) > 0.0
        ]
        hits.sort(key=lambda item: (-item.score, item.source_id))
        return tuple(hits[:top_k])


def search_judgment_evidence(
    ledger: EvidenceLedger,
    query: str,
    *,
    morphology: Morphology | None = None,
    policy: EvidencePolicy | None = None,
    top_k: int = 10,
) -> tuple[JudgmentHit, ...]:
    """Compatibility wrapper for one-off source-cited judgment searches."""
    return JudgmentSearchIndex(
        ledger,
        morphology=morphology,
        policy=policy,
    ).search(query, top_k=top_k)


__all__ = ["JudgmentHit", "JudgmentSearchIndex", "search_judgment_evidence"]
