"""Portable Telegram JSON -> ``SourceDocument`` adapter.

The research module also wrote an Obsidian vault and materialized a legacy
semantic backend. Stage 4d intentionally keeps only source decoding and
normalization. No personal channel map, output path, HTTP, plugin, LLM, or
semantic representation is imported here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
import unicodedata

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
    bucket: str
    text: str
    raw_chars: int


@dataclass(frozen=True)
class TelegramExportResult:
    """Transient, deterministic adapter result without the raw export payload."""

    namespace: str
    documents: tuple[SourceDocument, ...]
    message_count: int
    skipped_message_count: int

    def __post_init__(self) -> None:
        if not self.namespace or "/" in self.namespace or "\\" in self.namespace:
            raise ValueError("Telegram export namespace must be one safe path segment")
        source_ids = tuple(document.source_id for document in self.documents)
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("Telegram documents must be sorted by source_id")
        if any(document.adapter != TELEGRAM_EXPORT_ADAPTER for document in self.documents):
            raise ValueError("Telegram result contains a document from another adapter")
        if self.message_count < 0 or self.skipped_message_count < 0:
            raise ValueError("Telegram message counts must be non-negative")
        represented = sum(int(document.metadata["message_count"]) for document in self.documents)
        if represented != self.message_count:
            raise ValueError("Telegram document message counts do not match the result")


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


def clean_external_text(text: str) -> str:
    """Remove transport/code noise without deleting any language or script."""
    cleaned = _CODE_BLOCK_RE.sub(" ", text)
    cleaned = _INLINE_CODE_RE.sub(" ", cleaned)
    cleaned = _URL_RE.sub(" ", cleaned)
    cleaned = _MENTION_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _month_bucket(timestamp: float) -> str | None:
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m")
    except (OverflowError, OSError, ValueError):
        return None


def _observed_at_and_bucket(
    message: dict[str, Any],
    *,
    fallback: float,
) -> tuple[float, str]:
    unix_value = message.get("date_unixtime")
    if unix_value not in (None, ""):
        try:
            timestamp = float(unix_value)
        except (TypeError, ValueError):
            timestamp = math.nan
        bucket = _month_bucket(timestamp) if math.isfinite(timestamp) else None
        if bucket is not None:
            return timestamp, bucket

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
            bucket = _month_bucket(timestamp) if math.isfinite(timestamp) else None
            if bucket is not None:
                return timestamp, bucket
    return fallback, "undated"


def _safe_namespace(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    normalized = _NAMESPACE_RE.sub("-", normalized).strip(".-")
    if not normalized or normalized in {".", ".."}:
        raise ValueError("source_namespace must contain a safe path segment")
    return normalized


def _opaque_namespace(label: str) -> str:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]
    return f"export-{digest}"


def _message_record(message: _TelegramMessage) -> dict[str, Any]:
    return {
        "id": message.message_id,
        "observed_at": message.observed_at,
        "text": message.text,
    }


def load_telegram_export(
    path: Path,
    *,
    source_kind: SourceKind = "unknown",
    source_namespace: str | None = None,
) -> TelegramExportResult:
    """Decode a Telegram Desktop result.json into monthly source documents."""
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"unknown source kind: {source_kind!r}")
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

    accepted: list[_TelegramMessage] = []
    skipped = 0
    for index, raw_message in enumerate(payload["messages"]):
        if not isinstance(raw_message, dict) or raw_message.get("type") != "message":
            skipped += 1
            continue
        flattened = _flatten_text(raw_message.get("text", "")).strip()
        cleaned = clean_external_text(flattened)
        if not cleaned:
            skipped += 1
            continue
        observed_at, bucket_name = _observed_at_and_bucket(raw_message, fallback=fallback)
        message_id = str(raw_message.get("id", index)).strip() or str(index)
        accepted.append(
            _TelegramMessage(
                message_id=message_id,
                observed_at=observed_at,
                bucket=bucket_name,
                text=cleaned,
                raw_chars=len(flattened),
            )
        )
    accepted.sort(key=lambda item: (item.bucket, item.observed_at, item.message_id, item.text))

    grouped: dict[str, list[_TelegramMessage]] = defaultdict(list)
    for message in accepted:
        grouped[message.bucket].append(message)

    documents: list[SourceDocument] = []
    for bucket_name in sorted(grouped):
        messages = grouped[bucket_name]
        canonical = json.dumps(
            [_message_record(message) for message in messages],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        documents.append(
            SourceDocument.create(
                source_id=f"telegram/{namespace}/{bucket_name}.json",
                source_revision=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                observed_at=max(message.observed_at for message in messages),
                text="\n\n".join(message.text for message in messages),
                adapter=TELEGRAM_EXPORT_ADAPTER,
                source_kind=source_kind,
                raw_chars=sum(message.raw_chars for message in messages),
                metadata={
                    "format": "telegram-json",
                    "message_count": len(messages),
                    "period": bucket_name,
                },
            )
        )

    return TelegramExportResult(
        namespace=namespace,
        documents=tuple(documents),
        message_count=len(accepted),
        skipped_message_count=skipped,
    )


__all__ = [
    "MAX_TELEGRAM_EXPORT_BYTES",
    "TELEGRAM_EXPORT_ADAPTER",
    "TelegramExportResult",
    "clean_external_text",
    "load_telegram_export",
]
