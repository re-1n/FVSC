"""Portable Telegram JSON -> ``SourceDocument`` adapter.

The research module also wrote an Obsidian vault and materialized a legacy
semantic backend. Stage 4d.1 intentionally keeps only message-level source
decoding and normalization. No personal channel map, output path, HTTP, plugin,
LLM, or semantic representation is imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .source_provenance import ActorRole, ExpressionSpan, SourceAttribution, source_attribution
from .vault_ingest import SOURCE_KINDS, SourceDocument, SourceKind


TELEGRAM_EXPORT_ADAPTER = "telegram-export"
MAX_TELEGRAM_EXPORT_BYTES = 256 * 1024 * 1024

_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<!\w)@[\w.]+", flags=re.UNICODE)
_CODE_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", flags=re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_NAMESPACE_RE = re.compile(r"[^\w.-]+", flags=re.UNICODE)


@dataclass(frozen=True)
class _TelegramMessage:
    message_id: str
    observed_at: float
    dated: bool
    text: str
    raw_chars: int
    raw_text_sha256: str
    author_key: str
    owner_authored: bool
    forwarded: bool
    forward_source_key: str | None
    reply_to_message_id: str | None
    media_kind: str | None
    locators: tuple[str, ...]
    attribution: SourceAttribution


@dataclass(frozen=True)
class TelegramExportResult:
    """Transient, deterministic adapter result without the raw export payload."""

    namespace: str
    documents: tuple[SourceDocument, ...]
    message_count: int
    text_message_count: int
    deferred_message_count: int
    skipped_message_count: int

    def __post_init__(self) -> None:
        if not self.namespace or "/" in self.namespace or "\\" in self.namespace:
            raise ValueError("Telegram export namespace must be one safe path segment")
        source_ids = tuple(document.source_id for document in self.documents)
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("Telegram documents must be sorted by source_id")
        if any(document.adapter != TELEGRAM_EXPORT_ADAPTER for document in self.documents):
            raise ValueError("Telegram result contains a document from another adapter")
        if (
            self.message_count < 0
            or self.text_message_count < 0
            or self.deferred_message_count < 0
            or self.skipped_message_count < 0
        ):
            raise ValueError("Telegram message counts must be non-negative")
        represented = sum(int(document.metadata["message_count"]) for document in self.documents)
        if represented != self.message_count:
            raise ValueError("Telegram document message counts do not match the result")
        if self.text_message_count + self.deferred_message_count != self.message_count:
            raise ValueError("Telegram text/deferred counts do not match the result")


def _flatten_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, list):
        return ""
    parts: list[str] = []
    for item in raw:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            value = item.get("text", "")
            if isinstance(value, str):
                parts.append(value)
    return "".join(parts)


def _mapped_substitution(
    text: str,
    raw_offsets: tuple[int | None, ...],
    pattern: re.Pattern[str],
    replacement: str,
) -> tuple[str, tuple[int | None, ...]]:
    characters = list(text)
    offsets = list(raw_offsets)
    for match in reversed(tuple(pattern.finditer(text))):
        source_offset = next(
            (value for value in offsets[match.start() : match.end()] if value is not None),
            None,
        )
        characters[match.start() : match.end()] = replacement
        offsets[match.start() : match.end()] = [source_offset] * len(replacement)
    return "".join(characters), tuple(offsets)


def _clean_external_text_with_offsets(text: str) -> tuple[str, tuple[int | None, ...]]:
    cleaned = text
    offsets: tuple[int | None, ...] = tuple(range(len(text)))
    for pattern, replacement in (
        (_CODE_BLOCK_RE, " "),
        (_INLINE_CODE_RE, " "),
        (_URL_RE, " "),
        (_MENTION_RE, " "),
        (_WHITESPACE_RE, " "),
        (re.compile(r" *\n *"), "\n"),
        (re.compile(r"\n{3,}"), "\n\n"),
    ):
        cleaned, offsets = _mapped_substitution(cleaned, offsets, pattern, replacement)

    start = 0
    end = len(cleaned)
    while start < end and cleaned[start].isspace():
        start += 1
    while end > start and cleaned[end - 1].isspace():
        end -= 1
    return cleaned[start:end], offsets[start:end]


def clean_external_text(text: str) -> str:
    """Remove transport/code noise without deleting any language or script."""
    return _clean_external_text_with_offsets(text)[0]


def _actor_role(value: str, owner_ids: frozenset[str]) -> ActorRole:
    if value == "unknown":
        return "unknown"
    return "owner" if value in owner_ids else "non_owner"


def _explicit_expression_spans(
    message: dict[str, Any],
    *,
    flattened: str,
    cleaned: str,
    raw_offsets: tuple[int | None, ...],
    owner_adopted: bool,
) -> tuple[ExpressionSpan, ...]:
    raw_entities = message.get("text_entities")
    if raw_entities is None:
        return ()
    if not isinstance(raw_entities, list):
        raise ValueError("Telegram text_entities must be an array")

    cursor = 0
    quote_ranges: list[tuple[int, int]] = []
    entity_text: list[str] = []
    for entity in raw_entities:
        if not isinstance(entity, dict) or not isinstance(entity.get("text"), str):
            raise ValueError("Telegram text_entities contain an invalid entity")
        value = entity["text"]
        start = cursor
        cursor += len(value)
        entity_text.append(value)
        if entity.get("type") == "blockquote" and value:
            quote_ranges.append((start, cursor))
    if "".join(entity_text) != flattened:
        raise ValueError("Telegram text_entities do not match message text")

    spans: list[ExpressionSpan] = []
    for raw_start, raw_end in quote_ranges:
        indexes = tuple(
            index
            for index, raw_offset in enumerate(raw_offsets)
            if raw_offset is not None and raw_start <= raw_offset < raw_end
        )
        if not indexes:
            continue
        start = indexes[0]
        end = indexes[-1] + 1
        while start < end and cleaned[start].isspace():
            start += 1
        while end > start and cleaned[end - 1].isspace():
            end -= 1
        if start == end:
            continue
        spans.append(
            ExpressionSpan.from_text(
                cleaned,
                start=start,
                end=end,
                kind="quotation",
                origin_status="unresolved",
                owner_relation="adopted" if owner_adopted else "not_adopted",
                derivation="telegram:text-entity:blockquote:v1",
            )
        )
    return tuple(spans)


def _valid_timestamp(value: float) -> bool:
    if not math.isfinite(value):
        return False
    try:
        datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return False
    return True


def _observed_at(
    message: dict[str, Any],
    *,
    fallback: float,
) -> tuple[float, bool]:
    unix_value = message.get("date_unixtime")
    if unix_value not in (None, ""):
        try:
            timestamp = float(unix_value)
        except (TypeError, ValueError):
            timestamp = math.nan
        if _valid_timestamp(timestamp):
            return timestamp, True

    date_value = message.get("date")
    if isinstance(date_value, str) and date_value.strip():
        candidate = date_value.strip()
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = parsed.timestamp()
            if _valid_timestamp(timestamp):
                return timestamp, True
    return fallback, False


def _safe_namespace(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    normalized = _NAMESPACE_RE.sub("-", normalized).strip(".-")
    if not normalized or normalized in {".", ".."}:
        raise ValueError("source_namespace must contain a safe path segment")
    return normalized


def _opaque_namespace(label: str) -> str:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
    return f"export-{digest}"


def _opaque_actor_key(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]
    return f"actor-{digest}"


def _message_segment(value: str) -> str:
    message_id = str(value).strip()
    if (
        message_id
        and message_id not in {".", ".."}
        and re.fullmatch(r"[A-Za-z0-9._-]+", message_id)
    ):
        return message_id
    digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:24]
    return f"id-{digest}"


def _message_source_id(namespace: str, message_id: str) -> str:
    return f"telegram/{namespace}/messages/message-{_message_segment(message_id)}.json"


def _actor_value(message: dict[str, Any]) -> str:
    value = message.get("from_id", message.get("from", "unknown"))
    return str(value).strip() or "unknown"


def _forward_source_value(message: dict[str, Any]) -> str | None:
    if "forwarded_from_id" in message:
        value = message.get("forwarded_from_id")
    elif "forwarded_from" in message:
        value = message.get("forwarded_from")
    else:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _media_kind(message: dict[str, Any]) -> str | None:
    value = message.get("media_type")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if message.get("photo"):
        return "photo"
    if message.get("file"):
        return "file"
    if message.get("sticker_emoji"):
        return "sticker"
    return None


def _locators(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(_URL_RE.findall(text))))


def _message_record(message: _TelegramMessage) -> dict[str, Any]:
    return {
        "author_key": message.author_key,
        "forward_source_key": message.forward_source_key,
        "forwarded": message.forwarded,
        "id": message.message_id,
        "locators": list(message.locators),
        "media_kind": message.media_kind,
        "observed_at": message.observed_at,
        "reply_to_message_id": message.reply_to_message_id,
        "raw_text_sha256": message.raw_text_sha256,
        "text": message.text,
        "source_attribution": message.attribution.to_dict(),
    }


def load_telegram_export(
    path: Path,
    *,
    source_kind: SourceKind | None = None,
    source_namespace: str | None = None,
    owner_author_ids: Iterable[str] = (),
    display_timezone: str = "UTC",
    temporal_context_seconds: int | None = 30 * 60,
) -> TelegramExportResult:
    """Decode Telegram Desktop JSON into independent message source documents.

    ``owner_author_ids`` is transient caller configuration. Raw actor ids and
    display names never enter document metadata; only opaque actor keys do.
    Forwarding is retained as origin metadata and never overrides authorship.
    """
    if source_kind is not None and source_kind not in SOURCE_KINDS:
        raise ValueError(f"unknown source kind: {source_kind!r}")
    if isinstance(owner_author_ids, (str, bytes)):
        raise TypeError("owner_author_ids must be an iterable of actor ids")
    owner_ids = frozenset(
        value
        for raw_value in owner_author_ids
        if (value := str(raw_value).strip())
    )
    timezone_name = str(display_timezone).strip()
    if not timezone_name:
        raise ValueError("display_timezone must be a non-empty IANA timezone")
    try:
        display_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown display timezone: {timezone_name!r}") from exc
    if temporal_context_seconds is not None:
        if (
            isinstance(temporal_context_seconds, bool)
            or not isinstance(temporal_context_seconds, int)
            or temporal_context_seconds < 0
        ):
            raise ValueError("temporal_context_seconds must be a non-negative integer or None")

    export_path = Path(path)
    if export_path.is_symlink() or not export_path.is_file():
        raise ValueError(f"refusing non-regular Telegram export: {export_path}")
    if export_path.stat().st_size > MAX_TELEGRAM_EXPORT_BYTES:
        raise ValueError(f"Telegram export exceeds {MAX_TELEGRAM_EXPORT_BYTES} bytes")
    raw_bytes = export_path.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Telegram export is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        raise ValueError("Telegram export must contain a messages array")

    label = str(payload.get("id") or payload.get("name") or export_path.parent.name)
    namespace = (
        _safe_namespace(source_namespace)
        if source_namespace is not None
        else _opaque_namespace(label)
    )
    fallback = export_path.stat().st_mtime_ns / 1_000_000_000

    messages: list[_TelegramMessage] = []
    message_ids: set[str] = set()
    skipped = 0
    for index, raw_message in enumerate(payload["messages"]):
        if not isinstance(raw_message, dict) or raw_message.get("type") != "message":
            skipped += 1
            continue
        flattened = _flatten_text(raw_message.get("text", "")).strip()
        cleaned, raw_offsets = _clean_external_text_with_offsets(flattened)
        observed_at, dated = _observed_at(raw_message, fallback=fallback)
        message_id = str(raw_message.get("id", index)).strip() or str(index)
        if message_id in message_ids:
            raise ValueError(f"Telegram export contains duplicate message id: {message_id!r}")
        message_ids.add(message_id)
        actor_value = _actor_value(raw_message)
        forward_value = _forward_source_value(raw_message)
        owner_authored = actor_value in owner_ids
        forwarded = forward_value is not None
        attribution = source_attribution(
            transport_author_role=_actor_role(actor_value, owner_ids),
            owner_adopted_expression=owner_authored,
            text_origin_status="unresolved",
            forwarded=forwarded,
            forward_origin_role=(
                _actor_role(forward_value, owner_ids) if forward_value is not None else None
            ),
            expression_spans=_explicit_expression_spans(
                raw_message,
                flattened=flattened,
                cleaned=cleaned,
                raw_offsets=raw_offsets,
                owner_adopted=owner_authored,
            ),
        )
        attribution.verify(cleaned)
        raw_reply = raw_message.get("reply_to_message_id")
        reply_to_message_id = (
            str(raw_reply).strip()
            if raw_reply not in (None, "")
            else None
        )
        messages.append(
            _TelegramMessage(
                message_id=message_id,
                observed_at=observed_at,
                dated=dated,
                text=cleaned,
                raw_chars=len(flattened),
                raw_text_sha256=hashlib.sha256(flattened.encode("utf-8")).hexdigest(),
                author_key=_opaque_actor_key(actor_value),
                owner_authored=owner_authored,
                forwarded=forwarded,
                forward_source_key=(
                    _opaque_actor_key(forward_value)
                    if forward_value is not None
                    else None
                ),
                reply_to_message_id=reply_to_message_id,
                media_kind=_media_kind(raw_message),
                locators=_locators(flattened),
                attribution=attribution,
            )
        )
    messages.sort(key=lambda item: (item.observed_at, item.message_id, item.text))

    documents: list[SourceDocument] = []
    previous: _TelegramMessage | None = None
    for message in messages:
        canonical = json.dumps(
            _message_record(message),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        source_id = _message_source_id(namespace, message.message_id)
        display_time = None
        period = "undated"
        if message.dated:
            displayed = datetime.fromtimestamp(message.observed_at, tz=timezone.utc).astimezone(
                display_zone
            )
            display_time = displayed.isoformat()
            period = displayed.strftime("%Y-%m")

        temporal_context: dict[str, Any] | None = None
        if previous is not None and temporal_context_seconds is not None:
            gap_seconds = message.observed_at - previous.observed_at
            if (
                message.dated
                and previous.dated
                and 0.0 <= gap_seconds <= temporal_context_seconds
            ):
                temporal_context = {
                    "gap_seconds": gap_seconds,
                    "heuristic": True,
                    "previous_source_id": _message_source_id(
                        namespace,
                        previous.message_id,
                    ),
                    "threshold_seconds": temporal_context_seconds,
                }

        if message.text:
            ingest_status = "text"
        elif message.locators:
            ingest_status = "locator_only"
        elif message.media_kind is not None:
            ingest_status = "deferred_media"
        else:
            ingest_status = "empty"
        effective_source_kind: SourceKind = (
            source_kind
            if source_kind is not None
            else ("owner_reflection" if message.owner_authored else "unknown")
        )
        documents.append(
            SourceDocument.create(
                source_id=source_id,
                source_revision=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                observed_at=message.observed_at,
                text=message.text,
                adapter=TELEGRAM_EXPORT_ADAPTER,
                source_kind=effective_source_kind,
                raw_chars=message.raw_chars,
                metadata={
                    "author_key": message.author_key,
                    "date_status": "dated" if message.dated else "undated",
                    "display_time": display_time,
                    "display_timezone": timezone_name,
                    "format": "telegram-json",
                    "forward_source_key": message.forward_source_key,
                    "forwarded": message.forwarded,
                    "ingest_status": ingest_status,
                    "locators": list(message.locators),
                    "media_deferred": message.media_kind is not None and not message.text,
                    "media_kind": message.media_kind,
                    "message_count": 1,
                    "message_id": message.message_id,
                    "owner_adopted_expression": message.owner_authored,
                    "owner_authored": message.owner_authored,
                    "period": period,
                    "reply_to_message_id": message.reply_to_message_id,
                    "reply_to_source_id": (
                        _message_source_id(namespace, message.reply_to_message_id)
                        if message.reply_to_message_id is not None
                        else None
                    ),
                    "source_attribution": message.attribution.to_dict(),
                    "temporal_context": temporal_context,
                },
            )
        )
        previous = message

    documents.sort(key=lambda document: document.source_id)
    text_message_count = sum(bool(document.text) for document in documents)

    return TelegramExportResult(
        namespace=namespace,
        documents=tuple(documents),
        message_count=len(documents),
        text_message_count=text_message_count,
        deferred_message_count=len(documents) - text_message_count,
        skipped_message_count=skipped,
    )


__all__ = [
    "MAX_TELEGRAM_EXPORT_BYTES",
    "TELEGRAM_EXPORT_ADAPTER",
    "TelegramExportResult",
    "clean_external_text",
    "load_telegram_export",
]
