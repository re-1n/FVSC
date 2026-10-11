"""Append-only ledger for immutable FVSC evidence events."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import hashlib
from typing import Any

from .events import EvidenceEvent


class EvidenceLedger:
    """Ordered append-only history with a materialized active-event view.

    Assertions and supersessions are active semantic evidence. Retractions and
    supersessions deactivate their target without deleting history. Batch append
    validates on a temporary ledger first, so failure cannot leave partial state.
    """

    def __init__(self, events: Iterable[EvidenceEvent] = ()) -> None:
        self._events: list[EvidenceEvent] = []
        self._by_id: dict[str, EvidenceEvent] = {}
        self._active: dict[str, EvidenceEvent] = {}
        self.append_many(events)

    @property
    def events(self) -> tuple[EvidenceEvent, ...]:
        return tuple(self._events)

    @property
    def active_events(self) -> tuple[EvidenceEvent, ...]:
        return tuple(self._active.values())

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def active_count(self) -> int:
        return len(self._active)

    def get(self, event_id: str) -> EvidenceEvent | None:
        return self._by_id.get(event_id)

    def is_active(self, event_id: str) -> bool:
        return event_id in self._active

    def append(self, event: EvidenceEvent) -> bool:
        """Append one event; return ``False`` for an exact idempotent replay."""
        if not isinstance(event, EvidenceEvent):
            raise TypeError("ledger accepts EvidenceEvent instances only")

        existing = self._by_id.get(event.event_id)
        if existing is not None:
            if existing != event:
                raise ValueError("event_id collision with different event content")
            return False

        if event.event_kind == "assertion":
            self._active[event.event_id] = event
        else:
            target_id = event.target_event_id
            if target_id is None:
                raise ValueError("lifecycle event is missing target_event_id")
            if target_id not in self._by_id:
                raise ValueError(f"target event does not exist: {target_id}")
            if target_id not in self._active:
                raise ValueError(f"target event is not active: {target_id}")
            self._active.pop(target_id)
            if event.event_kind == "supersession":
                self._active[event.event_id] = event

        self._events.append(event)
        self._by_id[event.event_id] = event
        return True

    def append_many(self, events: Iterable[EvidenceEvent]) -> int:
        """Atomically append a sequence and return the number of new events."""
        incoming = tuple(events)
        if not incoming:
            return 0

        trial = EvidenceLedger.__new__(EvidenceLedger)
        trial._events = list(self._events)
        trial._by_id = dict(self._by_id)
        trial._active = dict(self._active)

        added = 0
        for event in incoming:
            added += int(trial.append(event))

        self._events = trial._events
        self._by_id = trial._by_id
        self._active = trial._active
        return added

    def active_for_source(self, source_id: str) -> tuple[EvidenceEvent, ...]:
        source = str(source_id).strip()
        return tuple(event for event in self._active.values() if event.source_id == source)

    def to_records(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, Any]]) -> "EvidenceLedger":
        return cls(EvidenceEvent.from_dict(record) for record in records)

    @property
    def digest(self) -> str:
        """Content digest of ordered event identities."""
        payload = "\n".join(event.event_id for event in self._events)
        return hashlib.sha256(payload.encode("ascii")).hexdigest()
