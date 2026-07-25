"""Deterministic token-budgeted compilation of reviewed semantic context.

This is a retrieval/compiler baseline, not a semantic model. It ranks immutable
semantic units with auditable Unicode character methods, then preserves explicitly
linked scope, voice, adoption and forbidden-claim guards in the rendered context.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Callable, Iterable, Literal, Mapping
import unicodedata


_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)
UnitKind = Literal["meaning", "group", "guard"]
RankingMethod = Literal["char_cosine", "char_tfidf", "external"]


def _ngrams(text: str, *, minimum: int = 3, maximum: int = 5) -> Counter[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    result: Counter[str] = Counter()
    for word in _WORD_RE.findall(normalized):
        padded = f" {word} "
        for width in range(minimum, maximum + 1):
            if len(padded) >= width:
                result.update(
                    padded[index : index + width]
                    for index in range(len(padded) - width + 1)
                )
    return result


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left.keys() & right.keys()
    dot = math.fsum(left[key] * right[key] for key in shared)
    left_norm = math.sqrt(math.fsum(value * value for value in left.values()))
    right_norm = math.sqrt(math.fsum(value * value for value in right.values()))
    return dot / (left_norm * right_norm)


def _tfidf(
    counts: Counter[str],
    *,
    document_frequency: Counter[str],
    document_count: int,
) -> Counter[str]:
    return Counter(
        {
            gram: (1.0 + math.log(frequency))
            * (
                math.log(
                    (1.0 + document_count)
                    / (1.0 + document_frequency[gram])
                )
                + 1.0
            )
            for gram, frequency in counts.items()
        }
    )


def approximate_tokens(text: str) -> int:
    """Conservative dependency-free estimate for mixed Cyrillic/ASCII prompts."""
    value = str(text)
    return 0 if not value else max(1, math.ceil(len(value) / 3.0))


@dataclass(frozen=True)
class SemanticContextUnit:
    unit_id: str
    text: str
    kind: UnitKind = "meaning"
    voice: str = "unknown"
    adoption: str = "unspecified"
    polarity: str = "positive"
    modality: str = "asserted"
    owner_decision: str = "not_reviewed"
    guard_ids: tuple[str, ...] = ()
    correction_ids: tuple[str, ...] = ()
    related_ids: tuple[str, ...] = ()
    retrieval_cues: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.unit_id.strip() or self.unit_id != self.unit_id.strip():
            raise ValueError("unit_id must be non-empty and trimmed")
        if not self.text.strip():
            raise ValueError("semantic unit text must be non-empty")
        if len(self.guard_ids) != len(set(self.guard_ids)):
            raise ValueError("guard_ids must be unique")
        if len(self.related_ids) != len(set(self.related_ids)):
            raise ValueError("related_ids must be unique")
        if len(self.correction_ids) != len(set(self.correction_ids)):
            raise ValueError("correction_ids must be unique")
        normalized_cues = tuple(cue.strip() for cue in self.retrieval_cues)
        if any(not cue for cue in normalized_cues):
            raise ValueError("retrieval_cues must be non-empty and trimmed")
        if normalized_cues != self.retrieval_cues:
            raise ValueError("retrieval_cues must be non-empty and trimmed")
        if len(normalized_cues) != len(set(normalized_cues)):
            raise ValueError("retrieval_cues must be unique")
        if self.unit_id in self.guard_ids:
            raise ValueError("a semantic unit cannot guard itself")
        if self.unit_id in self.related_ids:
            raise ValueError("a semantic unit cannot relate to itself")
        if self.unit_id in self.correction_ids:
            raise ValueError("a semantic unit cannot correct itself")
        if self.kind != "guard" and self.correction_ids:
            raise ValueError("only guard units may declare correction_ids")
        if self.kind == "guard" and not self.reason.strip():
            raise ValueError("guard units require a non-empty reason/correction")

    def render(self) -> str:
        metadata = (
            f"kind={self.kind}; voice={self.voice}; adoption={self.adoption}; "
            f"polarity={self.polarity}; modality={self.modality}; "
            f"owner_decision={self.owner_decision}"
        )
        if self.kind == "guard":
            return (
                f"[{self.unit_id}] {metadata}\n"
                f"PROHIBITED_CLAIM — NEVER REPEAT AS FACT: {self.text.strip()}\n"
                f"REASON_OR_CORRECTION: {self.reason.strip()}"
            )
        return f"[{self.unit_id}] {metadata}\n{self.text.strip()}"


@dataclass(frozen=True)
class CompiledContext:
    query: str
    ranking_method: str
    units: tuple[SemanticContextUnit, ...]
    scores: tuple[tuple[str, float], ...]
    rendered: str
    estimated_tokens: int
    token_budget: int
    omitted_ranked_ids: tuple[str, ...]
    below_threshold_ranked_ids: tuple[str, ...]


class SemanticContextCompiler:
    """Rank reviewed units and compile a guarded, fail-closed bounded context."""

    def __init__(
        self,
        units: Iterable[SemanticContextUnit],
        *,
        token_counter: Callable[[str], int] = approximate_tokens,
        guard_score_discount: float = 0.85,
    ) -> None:
        ordered = tuple(sorted(units, key=lambda item: item.unit_id))
        by_id = {item.unit_id: item for item in ordered}
        if len(by_id) != len(ordered):
            raise ValueError("semantic context units must have unique ids")
        for item in ordered:
            missing = set(item.guard_ids) - by_id.keys()
            if missing:
                raise ValueError(
                    f"semantic unit {item.unit_id} references missing guards: "
                    f"{sorted(missing)}"
                )
            if any(by_id[guard_id].kind != "guard" for guard_id in item.guard_ids):
                raise ValueError("guard_ids must reference units with kind='guard'")
            missing_related = set(item.related_ids) - by_id.keys()
            if missing_related:
                raise ValueError(
                    f"semantic unit {item.unit_id} references missing related units: "
                    f"{sorted(missing_related)}"
                )
            missing_corrections = set(item.correction_ids) - by_id.keys()
            if missing_corrections:
                raise ValueError(
                    f"semantic unit {item.unit_id} references missing corrections: "
                    f"{sorted(missing_corrections)}"
                )
            if any(
                by_id[correction_id].kind == "guard"
                for correction_id in item.correction_ids
            ):
                raise ValueError("correction_ids must reference positive meaning/group units")
        self.units = ordered
        self.by_id = by_id
        self.token_counter = token_counter
        if (
            isinstance(guard_score_discount, bool)
            or not isinstance(guard_score_discount, (int, float))
            or not 0.0 < float(guard_score_discount) <= 1.0
        ):
            raise ValueError("guard_score_discount must be in (0, 1]")
        self.guard_score_discount = float(guard_score_discount)
        self.vectors = {
            item.unit_id: _ngrams(f"{item.unit_id} {item.text}")
            for item in ordered
        }
        self.cued_vectors = {
            item.unit_id: _ngrams(
                " ".join((item.unit_id, item.text, *item.retrieval_cues))
            )
            for item in ordered
        }
        self.document_frequency: Counter[str] = Counter()
        self.cued_document_frequency: Counter[str] = Counter()
        for vector in self.vectors.values():
            self.document_frequency.update(vector.keys())
        for vector in self.cued_vectors.values():
            self.cued_document_frequency.update(vector.keys())
        self.tfidf_vectors = {
            unit_id: _tfidf(
                vector,
                document_frequency=self.document_frequency,
                document_count=len(self.units),
            )
            for unit_id, vector in self.vectors.items()
        }
        self.cued_tfidf_vectors = {
            unit_id: _tfidf(
                vector,
                document_frequency=self.cued_document_frequency,
                document_count=len(self.units),
            )
            for unit_id, vector in self.cued_vectors.items()
        }

    def compile(
        self,
        query: str,
        *,
        token_budget: int,
        top_k: int = 6,
        expand_related: bool = False,
        require_positive: bool = False,
        use_retrieval_cues: bool = False,
        ranking_method: RankingMethod = "char_cosine",
        minimum_score: float = 0.0,
        external_scores: Mapping[str, float] | None = None,
    ) -> CompiledContext:
        if isinstance(token_budget, bool) or not isinstance(token_budget, int) or token_budget <= 0:
            raise ValueError("token_budget must be a positive integer")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        query_value = str(query).strip()
        if not query_value:
            raise ValueError("query must be non-empty")
        if ranking_method not in ("char_cosine", "char_tfidf", "external"):
            raise ValueError(
                "ranking_method must be 'char_cosine', 'char_tfidf' or 'external'"
            )
        if ranking_method == "external":
            if external_scores is None:
                raise ValueError("external ranking requires external_scores")
            if set(external_scores) != set(self.by_id):
                raise ValueError(
                    "external_scores must contain exactly every semantic unit id"
                )
            normalized_external_scores: dict[str, float] = {}
            for unit_id, raw_score in external_scores.items():
                if (
                    isinstance(raw_score, bool)
                    or not isinstance(raw_score, (int, float))
                    or not math.isfinite(float(raw_score))
                    or not 0.0 <= float(raw_score) <= 1.0
                ):
                    raise ValueError(
                        "external_scores values must be finite and in [0, 1]"
                    )
                normalized_external_scores[unit_id] = float(raw_score)
        elif external_scores is not None:
            raise ValueError(
                "external_scores may be supplied only with external ranking"
            )
        if (
            isinstance(minimum_score, bool)
            or not isinstance(minimum_score, (int, float))
            or not math.isfinite(float(minimum_score))
            or not 0.0 <= float(minimum_score) <= 1.0
        ):
            raise ValueError("minimum_score must be finite and in [0, 1]")
        score_floor = float(minimum_score)

        query_vector = _ngrams(query_value)
        vectors = self.cued_vectors if use_retrieval_cues else self.vectors
        if ranking_method == "char_tfidf":
            document_frequency = (
                self.cued_document_frequency
                if use_retrieval_cues
                else self.document_frequency
            )
            document_count = len(self.units)
            query_vector = _tfidf(
                query_vector,
                document_frequency=document_frequency,
                document_count=document_count,
            )
            vectors = (
                self.cued_tfidf_vectors
                if use_retrieval_cues
                else self.tfidf_vectors
            )
        ranked = []
        for item in self.units:
            score = (
                normalized_external_scores[item.unit_id]
                if ranking_method == "external"
                else _cosine(query_vector, vectors[item.unit_id])
            )
            ranked.append(
                (
                    item,
                    score
                    * (self.guard_score_discount if item.kind == "guard" else 1.0),
                )
            )
        ranked.sort(key=lambda pair: (-pair[1], pair[0].unit_id))

        chosen: list[SemanticContextUnit] = []
        chosen_ids: set[str] = set()
        omitted: list[str] = []
        below_threshold: list[str] = []

        for item, score in ranked[:top_k]:
            if score < score_floor:
                below_threshold.append(item.unit_id)
                continue
            primary = [item]
            guard_ids = tuple(
                dict.fromkeys(
                    guard_id
                    for candidate in primary
                    for guard_id in candidate.guard_ids
                )
            )
            guards = [self.by_id[guard_id] for guard_id in guard_ids]
            corrections = [
                self.by_id[correction_id]
                for guard in ([item] if item.kind == "guard" else guards)
                for correction_id in guard.correction_ids
            ]
            mandatory = [
                candidate
                for candidate in [*primary, *guards, *corrections]
                if candidate.unit_id not in chosen_ids
            ]
            candidate_units = [*chosen, *mandatory]
            rendered = "\n\n".join(candidate.render() for candidate in candidate_units)
            if self.token_counter(rendered) > token_budget:
                omitted.append(item.unit_id)
                continue
            chosen.extend(mandatory)
            chosen_ids.update(candidate.unit_id for candidate in mandatory)

            if expand_related:
                for related_id in item.related_ids:
                    related = self.by_id[related_id]
                    optional = [
                        related,
                        *(self.by_id[guard_id] for guard_id in related.guard_ids),
                    ]
                    optional = [
                        candidate
                        for candidate in optional
                        if candidate.unit_id not in chosen_ids
                    ]
                    optional_units = [*chosen, *optional]
                    optional_rendered = "\n\n".join(
                        candidate.render() for candidate in optional_units
                    )
                    if self.token_counter(optional_rendered) <= token_budget:
                        chosen.extend(optional)
                        chosen_ids.update(candidate.unit_id for candidate in optional)

        rendered = "\n\n".join(item.render() for item in chosen)
        if require_positive and not any(item.kind != "guard" for item in chosen):
            rendered = ""
            chosen = []
        return CompiledContext(
            query=query_value,
            ranking_method=(
                "unicode-char-tfidf-with-reviewed-cues-v1"
                if ranking_method == "char_tfidf" and use_retrieval_cues
                else "external-scores-v1"
                if ranking_method == "external"
                else "unicode-char-tfidf-v1"
                if ranking_method == "char_tfidf"
                else "unicode-char-ngram-with-reviewed-cues-v1"
                if use_retrieval_cues
                else "unicode-char-ngram-v1"
            ),
            units=tuple(chosen),
            scores=tuple((item.unit_id, score) for item, score in ranked),
            rendered=rendered,
            estimated_tokens=self.token_counter(rendered),
            token_budget=token_budget,
            omitted_ranked_ids=tuple(omitted),
            below_threshold_ranked_ids=tuple(below_threshold),
        )


__all__ = [
    "CompiledContext",
    "RankingMethod",
    "SemanticContextCompiler",
    "SemanticContextUnit",
    "approximate_tokens",
]
