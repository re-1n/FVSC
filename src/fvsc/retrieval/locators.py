"""Deterministic resolution of explicit logical source locators in queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterable, Literal
import unicodedata

from ..ingest import SourceDocument


LocatorStatus = Literal["resolved", "absent", "ambiguous"]
LocatorMatchKind = Literal["exact_namespace", "namespace_alias", "none"]

_LOCATOR_RE = re.compile(
    r"(?<![\w:/])(?P<namespace>[^\W\d_][\w.-]{0,63}):"
    r"(?P<local_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})",
    flags=re.UNICODE,
)
_RESERVED_NAMESPACES = frozenset({"http", "https", "ftp", "file", "urn"})


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).casefold().strip(" ._-")


def _namespace_tokens(value: str) -> frozenset[str]:
    normalized = _normalized(value)
    return frozenset(item for item in re.split(r"[._-]+", normalized) if item)


@dataclass(frozen=True)
class SourceLocator:
    namespace: str
    local_id: str
    raw: str

    def __post_init__(self) -> None:
        namespace = str(self.namespace).strip()
        local_id = str(self.local_id).strip()
        raw = str(self.raw).strip()
        if not namespace or not local_id or not raw:
            raise ValueError("source locator fields must not be empty")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "local_id", local_id)
        object.__setattr__(self, "raw", raw)


@dataclass(frozen=True)
class LocatorResolution:
    locator: SourceLocator
    status: LocatorStatus
    source_ids: tuple[str, ...] = ()
    match_kind: LocatorMatchKind = "none"

    def __post_init__(self) -> None:
        if self.status not in {"resolved", "absent", "ambiguous"}:
            raise ValueError(f"unknown locator status: {self.status!r}")
        source_ids = tuple(str(value).strip() for value in self.source_ids)
        if any(not value for value in source_ids) or source_ids != tuple(sorted(source_ids)):
            raise ValueError("locator source ids must be non-empty and sorted")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("locator source ids must be unique")
        if self.status == "resolved" and len(source_ids) != 1:
            raise ValueError("a resolved locator requires exactly one source")
        if self.status == "absent" and source_ids:
            raise ValueError("an absent locator cannot contain sources")
        if self.status == "ambiguous" and len(source_ids) < 2:
            raise ValueError("an ambiguous locator requires at least two sources")
        if self.status == "resolved" and self.match_kind == "none":
            raise ValueError("a resolved locator requires a match kind")
        if self.status != "resolved" and self.match_kind != "none":
            raise ValueError("only resolved locators have a match kind")
        object.__setattr__(self, "source_ids", source_ids)

    @property
    def source_id(self) -> str | None:
        return self.source_ids[0] if self.status == "resolved" else None


def parse_source_locators(query: str) -> tuple[SourceLocator, ...]:
    """Return unique locator tokens in query order; URL schemes are ignored."""
    value = str(query)
    locators: list[SourceLocator] = []
    seen: set[tuple[str, str]] = set()
    for match in _LOCATOR_RE.finditer(value):
        namespace = match.group("namespace")
        local_id = match.group("local_id").rstrip(".")
        key = (_normalized(namespace), _normalized(local_id))
        if not local_id or key[0] in _RESERVED_NAMESPACES or key in seen:
            continue
        seen.add(key)
        locators.append(
            SourceLocator(
                namespace=namespace,
                local_id=local_id,
                raw=match.group(0).rstrip("."),
            )
        )
    return tuple(locators)


def _telegram_coordinates(document: SourceDocument) -> tuple[str, str] | None:
    parts = PurePosixPath(document.source_id).parts
    if len(parts) < 4 or parts[0] != "telegram" or parts[2] != "messages":
        return None
    message_id = document.metadata.get("message_id")
    if message_id is None:
        return None
    local_id = str(message_id).strip()
    if not local_id:
        return None
    return parts[1], local_id


class SourceLocatorIndex:
    """Resolve explicit locators without semantic similarity or gold annotations."""

    def __init__(self, documents: Iterable[SourceDocument]) -> None:
        ordered = tuple(sorted(documents, key=lambda item: item.source_id))
        source_ids = tuple(item.source_id for item in ordered)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source locator documents must have unique ids")
        self.documents_by_id = {item.source_id: item for item in ordered}
        entries: list[tuple[str, str, str]] = []
        for document in ordered:
            coordinates = _telegram_coordinates(document)
            if coordinates is not None:
                namespace, local_id = coordinates
                entries.append((_normalized(namespace), _normalized(local_id), document.source_id))
        self.entries = tuple(entries)

    def resolve(self, locator: SourceLocator) -> LocatorResolution:
        namespace = _normalized(locator.namespace)
        local_id = _normalized(locator.local_id)
        exact = tuple(
            sorted(
                source_id
                for candidate_namespace, candidate_id, source_id in self.entries
                if candidate_namespace == namespace and candidate_id == local_id
            )
        )
        if len(exact) == 1:
            return LocatorResolution(locator, "resolved", exact, "exact_namespace")
        if len(exact) > 1:
            return LocatorResolution(locator, "ambiguous", exact)

        aliased = tuple(
            sorted(
                source_id
                for candidate_namespace, candidate_id, source_id in self.entries
                if namespace in _namespace_tokens(candidate_namespace)
                and candidate_id == local_id
            )
        )
        if len(aliased) == 1:
            return LocatorResolution(locator, "resolved", aliased, "namespace_alias")
        if len(aliased) > 1:
            return LocatorResolution(locator, "ambiguous", aliased)
        return LocatorResolution(locator, "absent")

    def resolve_query(self, query: str) -> tuple[LocatorResolution, ...]:
        return tuple(self.resolve(locator) for locator in parse_source_locators(query))

    def document(self, source_id: str) -> SourceDocument:
        return self.documents_by_id[source_id]


__all__ = [
    "LocatorMatchKind",
    "LocatorResolution",
    "LocatorStatus",
    "SourceLocator",
    "SourceLocatorIndex",
    "parse_source_locators",
]
