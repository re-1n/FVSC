"""Deterministic policies for derived views over canonical evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .events import EvidenceEvent


@dataclass(frozen=True)
class EvidencePolicy:
    """Select active assertions without changing or copying the ledger.

    ``None`` means unrestricted for a dimension; an empty set means allow none.
    Policies are derived-view controls, not evidence and not a topic taxonomy.
    """

    source_kinds: frozenset[str] | None = None
    extractors: frozenset[str] | None = None
    derivations: frozenset[str] | None = None
    confirmation_statuses: frozenset[str] | None = None
    max_interpretation_layer: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "source_kinds",
            "extractors",
            "derivations",
            "confirmation_statuses",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, (str, bytes)):
                raise TypeError(f"{field_name} must be an iterable of strings or None")
            object.__setattr__(
                self,
                field_name,
                frozenset(str(item).strip() for item in value if str(item).strip()),
            )
        layer = self.max_interpretation_layer
        if layer is not None:
            if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0:
                raise ValueError("max_interpretation_layer must be non-negative or None")

    @staticmethod
    def _field_allowed(value: str | None, allowed: frozenset[str] | None) -> bool:
        if allowed is None:
            return True
        return value is not None and value in allowed

    def allows(self, event: EvidenceEvent) -> bool:
        if event.event_kind not in {"assertion", "supersession"}:
            return False
        if (
            self.max_interpretation_layer is not None
            and event.interpretation_layer > self.max_interpretation_layer
        ):
            return False
        if not self._field_allowed(event.extractor, self.extractors):
            return False

        context = event.context
        source_kind = context.get("source_kind")
        if not self._field_allowed(
            source_kind if isinstance(source_kind, str) else None,
            self.source_kinds,
        ):
            return False
        derivation = context.get("derivation")
        if not self._field_allowed(
            derivation if isinstance(derivation, str) else None,
            self.derivations,
        ):
            return False

        judgment = context.get("judgment")
        judgment_context = judgment if isinstance(judgment, dict) else {}
        raw_status = judgment_context.get("confirmation_status", "unreviewed")
        status = raw_status if isinstance(raw_status, str) else None
        if not self._field_allowed(status, self.confirmation_statuses):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        def values(value: frozenset[str] | None) -> list[str] | None:
            return None if value is None else sorted(value)

        return {
            "source_kinds": values(self.source_kinds),
            "extractors": values(self.extractors),
            "derivations": values(self.derivations),
            "confirmation_statuses": values(self.confirmation_statuses),
            "max_interpretation_layer": self.max_interpretation_layer,
        }

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["EvidencePolicy"]
