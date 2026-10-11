"""Language-neutral, source-addressed linguistic frontend results.

These records are derived parser output, never canonical owner evidence. They retain
only source offsets and digests for surface forms so persisted artifacts do not copy
private source text.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..ingest.vault_ingest import SourceDocument


LINGUISTIC_FRONTEND_SCHEMA = "fvsc.linguistic-frontend/v1"
_SHA256_LENGTH = 64


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if len(result) != _SHA256_LENGTH or any(
        char not in "0123456789abcdef" for char in result
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _confidence(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError("token confidence must be finite and in [0, 1]")
    return result


@dataclass(frozen=True)
class LinguisticToken:
    """One token anchored to a half-open character span in a source revision."""

    token_id: str
    sentence_id: str
    index: int
    start: int
    end: int
    text_sha256: str
    lemma: str | None = None
    upos: str | None = None
    features: tuple[tuple[str, str], ...] = ()
    head_token_id: str | None = None
    dependency_relation: str | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_id", _nonempty(self.token_id, field="token_id"))
        object.__setattr__(
            self,
            "sentence_id",
            _nonempty(self.sentence_id, field="sentence_id"),
        )
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 1:
            raise ValueError("token index must be a positive integer")
        if (
            isinstance(self.start, bool)
            or isinstance(self.end, bool)
            or not isinstance(self.start, int)
            or not isinstance(self.end, int)
            or self.start < 0
            or self.end <= self.start
        ):
            raise ValueError("token offsets must be a non-empty half-open range")
        object.__setattr__(
            self,
            "text_sha256",
            _digest(self.text_sha256, field="token text_sha256"),
        )
        lemma = None if self.lemma is None else str(self.lemma).strip() or None
        upos = None if self.upos is None else str(self.upos).strip() or None
        head = (
            None
            if self.head_token_id is None
            else str(self.head_token_id).strip() or None
        )
        relation = (
            None
            if self.dependency_relation is None
            else str(self.dependency_relation).strip() or None
        )
        features = tuple(
            sorted(
                (
                    _nonempty(key, field="feature name"),
                    _nonempty(value, field="feature value"),
                )
                for key, value in self.features
            )
        )
        if len(features) != len({key for key, _ in features}):
            raise ValueError("token features must have unique names")
        object.__setattr__(self, "lemma", lemma)
        object.__setattr__(self, "upos", upos)
        object.__setattr__(self, "head_token_id", head)
        object.__setattr__(self, "dependency_relation", relation)
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "confidence", _confidence(self.confidence))

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        token_id: str,
        sentence_id: str,
        index: int,
        start: int,
        end: int,
        **kwargs: Any,
    ) -> "LinguisticToken":
        if end > len(text) or end <= start:
            raise ValueError("token span extends beyond source text")
        return cls(
            token_id=token_id,
            sentence_id=sentence_id,
            index=index,
            start=start,
            end=end,
            text_sha256=hashlib.sha256(text[start:end].encode("utf-8")).hexdigest(),
            **kwargs,
        )

    def verify(self, text: str) -> None:
        if self.end > len(text):
            raise ValueError("token span extends beyond source text")
        digest = hashlib.sha256(text[self.start : self.end].encode("utf-8")).hexdigest()
        if digest != self.text_sha256:
            raise ValueError("token span does not match source text")

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "dependency_relation": self.dependency_relation,
            "end": self.end,
            "features": [[key, value] for key, value in self.features],
            "head_token_id": self.head_token_id,
            "index": self.index,
            "lemma": self.lemma,
            "sentence_id": self.sentence_id,
            "start": self.start,
            "text_sha256": self.text_sha256,
            "token_id": self.token_id,
            "upos": self.upos,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LinguisticToken":
        raw_features = value.get("features", [])
        if not isinstance(raw_features, list):
            raise ValueError("token features must be an array")
        features: list[tuple[str, str]] = []
        for item in raw_features:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError("each token feature must be a [name, value] pair")
            features.append((item[0], item[1]))
        return cls(
            token_id=value.get("token_id", ""),
            sentence_id=value.get("sentence_id", ""),
            index=value.get("index", 0),
            start=value.get("start", -1),
            end=value.get("end", -1),
            text_sha256=value.get("text_sha256", ""),
            lemma=value.get("lemma"),
            upos=value.get("upos"),
            features=tuple(features),
            head_token_id=value.get("head_token_id"),
            dependency_relation=value.get("dependency_relation"),
            confidence=value.get("confidence", 0.0),
        )


@dataclass(frozen=True)
class LinguisticFrontendResult:
    """Deterministic output of one replaceable language-specific frontend."""

    source_id: str
    source_revision: str
    language_tag: str
    frontend: str
    frontend_version: str
    tokens: tuple[LinguisticToken, ...]
    schema: str = LINGUISTIC_FRONTEND_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != LINGUISTIC_FRONTEND_SCHEMA:
            raise ValueError("unsupported linguistic frontend schema")
        object.__setattr__(self, "source_id", _nonempty(self.source_id, field="source_id"))
        object.__setattr__(
            self,
            "source_revision",
            _digest(self.source_revision, field="source_revision"),
        )
        object.__setattr__(
            self,
            "language_tag",
            _nonempty(self.language_tag, field="language_tag"),
        )
        object.__setattr__(self, "frontend", _nonempty(self.frontend, field="frontend"))
        object.__setattr__(
            self,
            "frontend_version",
            _nonempty(self.frontend_version, field="frontend_version"),
        )
        ordered = tuple(
            sorted(self.tokens, key=lambda item: (item.start, item.end, item.token_id))
        )
        if ordered != self.tokens:
            raise ValueError("linguistic tokens must be sorted by source offset")
        token_ids = tuple(item.token_id for item in ordered)
        if len(token_ids) != len(set(token_ids)):
            raise ValueError("linguistic token ids must be unique")
        sentence_positions = tuple((item.sentence_id, item.index) for item in ordered)
        if len(sentence_positions) != len(set(sentence_positions)):
            raise ValueError("token indexes must be unique inside each sentence")
        for previous, current in zip(ordered, ordered[1:]):
            if current.start < previous.end:
                raise ValueError("linguistic token spans must not overlap")
        by_id = {item.token_id: item for item in ordered}
        for item in ordered:
            if item.head_token_id is None:
                continue
            head = by_id.get(item.head_token_id)
            if head is None:
                raise ValueError("token dependency head must exist in the frontend result")
            if head.sentence_id != item.sentence_id:
                raise ValueError("token dependency head must be in the same sentence")

    def verify(self, document: "SourceDocument") -> None:
        if document.source_id != self.source_id:
            raise ValueError("frontend result source_id does not match document")
        if document.source_revision != self.source_revision:
            raise ValueError("frontend result source_revision does not match document")
        for token in self.tokens:
            token.verify(document.text)

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontend": self.frontend,
            "frontend_version": self.frontend_version,
            "language_tag": self.language_tag,
            "schema": self.schema,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "tokens": [item.to_dict() for item in self.tokens],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LinguisticFrontendResult":
        raw_tokens = value.get("tokens", [])
        if not isinstance(raw_tokens, list):
            raise ValueError("linguistic frontend tokens must be an array")
        return cls(
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            language_tag=value.get("language_tag", ""),
            frontend=value.get("frontend", ""),
            frontend_version=value.get("frontend_version", ""),
            tokens=tuple(LinguisticToken.from_dict(item) for item in raw_tokens),
            schema=value.get("schema", ""),
        )


__all__ = [
    "LINGUISTIC_FRONTEND_SCHEMA",
    "LinguisticFrontendResult",
    "LinguisticToken",
]
