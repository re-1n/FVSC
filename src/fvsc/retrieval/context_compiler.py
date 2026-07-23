"""Deterministic token-budgeted compilation of reviewed semantic context.

This is a retrieval/compiler baseline, not a semantic model. It ranks immutable
semantic units with Unicode character n-gram similarity, then preserves explicitly
linked scope, voice, adoption and forbidden-claim guards in the rendered context.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Callable, Iterable, Literal
import unicodedata


_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)
UnitKind = Literal["meaning", "group", "guard"]


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
    units: tuple[SemanticContextUnit, ...]
    scores: tuple[tuple[str, float], ...]
    rendered: str
    estimated_tokens: int
    token_budget: int
    omitted_ranked_ids: tuple[str, ...]


class SemanticContextCompiler:
    """Rank reviewed units and compile a guarded context within a hard budget."""

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

    def compile(
        self,
        query: str,
        *,
        token_budget: int,
        top_k: int = 6,
        expand_related: bool = False,
        require_positive: bool = False,
    ) -> CompiledContext:
        if isinstance(token_budget, bool) or not isinstance(token_budget, int) or token_budget <= 0:
            raise ValueError("token_budget must be a positive integer")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        query_value = str(query).strip()
        if not query_value:
            raise ValueError("query must be non-empty")

        query_vector = _ngrams(query_value)
        ranked = [
            (
                item,
                _cosine(query_vector, self.vectors[item.unit_id])
                * (self.guard_score_discount if item.kind == "guard" else 1.0),
            )
            for item in self.units
        ]
        ranked.sort(key=lambda pair: (-pair[1], pair[0].unit_id))

        chosen: list[SemanticContextUnit] = []
        chosen_ids: set[str] = set()
        omitted: list[str] = []

        for item, _score in ranked[:top_k]:
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
            units=tuple(chosen),
            scores=tuple((item.unit_id, score) for item, score in ranked),
            rendered=rendered,
            estimated_tokens=self.token_counter(rendered),
            token_budget=token_budget,
            omitted_ranked_ids=tuple(omitted),
        )


__all__ = [
    "CompiledContext",
    "SemanticContextCompiler",
    "SemanticContextUnit",
    "approximate_tokens",
]
