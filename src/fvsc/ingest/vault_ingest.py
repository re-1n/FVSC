"""Deterministic, local-only source scanning for Obsidian vaults.

This module stops at ``SourceDocument`` records. It has no ledger, semantic
backend, cache, HTTP, plugin, visualization, or LLM dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, Literal, Mapping, cast


SourceKind = Literal["owner_reflection", "dream_report", "external_fact", "unknown"]
SOURCE_KINDS = frozenset({"owner_reflection", "dream_report", "external_fact", "unknown"})
OBSIDIAN_VAULT_ADAPTER = "obsidian-vault"

# Callers may add exclusions but cannot remove these safety-critical defaults.
DEFAULT_VAULT_EXCLUDE_DIRS = frozenset(
    {
        ".fvsc",
        ".obsidian",
        ".trash",
        "_fvsc_concepts",
        "attachments",
        "вложения",
    }
)

_SHA256_HEX_LENGTH = 64
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<header>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
    flags=re.DOTALL,
)
_FRONTMATTER_FIELD_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$")
_FENCED_CODE_RE = re.compile(r"(?ms)^\s*(?:```|~~~).*?^\s*(?:```|~~~)\s*$")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_OBSIDIAN_EMBED_RE = re.compile(r"!\[\[[^\]]+\]\]")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]*\)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]*\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_RE = re.compile(r"(?m)^\s*#{1,6}\s+")
_BLOCK_PREFIX_RE = re.compile(r"(?m)^\s*(?:>\s*|[-+*]\s+|\d+[.)]\s+)")
_HORIZONTAL_RULE_RE = re.compile(r"(?m)^\s*[-=*_]{3,}\s*$")
_MARKUP_RE = re.compile(r"[|*_~]")


def _canonical_metadata(value: Mapping[str, Any] | None) -> str:
    try:
        return json.dumps(
            dict(value or {}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("source metadata must contain JSON values") from exc


def _validate_source_id(value: str) -> str:
    source_id = str(value).strip()
    if not source_id or "\\" in source_id:
        raise ValueError("source_id must be a non-empty POSIX-relative path")
    path = PurePosixPath(source_id)
    if path.is_absolute() or ".." in path.parts or source_id.endswith("/"):
        raise ValueError("source_id must be a safe POSIX-relative path")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("source_id must identify a file")
    return normalized


@dataclass(frozen=True)
class SourceDocument:
    """One transient source document ready for parser ingestion."""

    source_id: str
    source_revision: str
    observed_at: float
    text: str
    adapter: str
    source_kind: SourceKind = "unknown"
    raw_chars: int = 0
    metadata_json: str = "{}"

    def __post_init__(self) -> None:
        source_id = _validate_source_id(self.source_id)
        revision = str(self.source_revision).strip()
        if len(revision) != _SHA256_HEX_LENGTH or any(
            char not in "0123456789abcdef" for char in revision
        ):
            raise ValueError("source_revision must be a lowercase SHA-256 digest")
        observed_at = float(self.observed_at)
        if not math.isfinite(observed_at):
            raise ValueError("observed_at must be finite")
        if not isinstance(self.text, str):
            raise TypeError("source document text must be a string")
        adapter = str(self.adapter).strip()
        if not adapter:
            raise ValueError("source adapter must not be empty")
        source_kind = str(self.source_kind).strip()
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"unknown source kind: {source_kind!r}")
        if isinstance(self.raw_chars, bool):
            raise ValueError("raw_chars must be a non-negative integer")
        raw_chars = int(self.raw_chars)
        if raw_chars < 0 or raw_chars != self.raw_chars:
            raise ValueError("raw_chars must be a non-negative integer")
        try:
            metadata = json.loads(self.metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError("metadata_json must contain a JSON object") from exc
        if not isinstance(metadata, dict):
            raise ValueError("metadata_json must contain a JSON object")

        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_revision", revision)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "raw_chars", raw_chars)
        object.__setattr__(self, "metadata_json", _canonical_metadata(metadata))

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_revision: str,
        observed_at: float,
        text: str,
        adapter: str,
        source_kind: SourceKind = "unknown",
        raw_chars: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> "SourceDocument":
        return cls(
            source_id=source_id,
            source_revision=source_revision,
            observed_at=observed_at,
            text=text,
            adapter=adapter,
            source_kind=source_kind,
            raw_chars=raw_chars,
            metadata_json=_canonical_metadata(metadata),
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


@dataclass(frozen=True)
class VaultScan:
    """Deterministically ordered vault source records and non-sensitive stats."""

    documents: tuple[SourceDocument, ...]
    folder_stats: Mapping[str, Mapping[str, int]]

    def __post_init__(self) -> None:
        source_ids = tuple(document.source_id for document in self.documents)
        if source_ids != tuple(sorted(source_ids)):
            raise ValueError("vault documents must be sorted by source_id")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("vault documents must have unique source_ids")

    @property
    def file_count(self) -> int:
        return len(self.documents)

    @property
    def raw_chars(self) -> int:
        return sum(document.raw_chars for document in self.documents)

    @property
    def cleaned_chars(self) -> int:
        return sum(len(document.text) for document in self.documents)

    @property
    def source_revisions(self) -> dict[str, str]:
        return {document.source_id: document.source_revision for document in self.documents}

    @property
    def files_by_path(self) -> dict[str, str]:
        return {document.source_id: document.text for document in self.documents}


def _split_frontmatter(text: str) -> tuple[str, dict[str, str]]:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return text, {}
    metadata: dict[str, str] = {}
    for line in match.group("header").splitlines():
        field = _FRONTMATTER_FIELD_RE.match(line)
        if field is None:
            continue
        key = field.group(1).casefold()
        value = field.group(2).strip().strip("\"'")
        metadata[key] = value
    return text[match.end() :], metadata


def _wikilink_text(match: re.Match[str]) -> str:
    target, alias = match.group(1), match.group(2)
    return alias or target


def normalize_markdown(text: str) -> tuple[str, SourceKind]:
    """Return parser text and an explicitly declared source kind.

    The normalizer preserves words from every script. It removes presentation
    syntax, code, embeds, and link destinations without applying a
    language-specific vocabulary filter.
    """
    body, frontmatter = _split_frontmatter(text)
    source_kind_value = frontmatter.get(
        "fvsc_source_kind",
        frontmatter.get("source_kind", "unknown"),
    ).strip().casefold()
    if source_kind_value not in SOURCE_KINDS:
        raise ValueError(f"unknown source kind: {source_kind_value!r}")

    body = _FENCED_CODE_RE.sub(" ", body)
    body = _INLINE_CODE_RE.sub(" ", body)
    body = _OBSIDIAN_EMBED_RE.sub(" ", body)
    body = _IMAGE_RE.sub(" ", body)
    body = _WIKILINK_RE.sub(_wikilink_text, body)
    body = _MARKDOWN_LINK_RE.sub(r"\1", body)
    body = _HTML_TAG_RE.sub(" ", body)
    body = _HEADING_RE.sub("", body)
    body = _BLOCK_PREFIX_RE.sub("", body)
    body = _HORIZONTAL_RULE_RE.sub("", body)
    body = _MARKUP_RE.sub(" ", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r" *\n *", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip(), cast(SourceKind, source_kind_value)


def _decode_markdown(raw: bytes) -> tuple[str, str]:
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1251"), "cp1251"


def scan_vault(
    vault_dir: Path,
    *,
    exclude_dirs: set[str] | frozenset[str] | None = None,
    min_clean_chars: int = 0,
) -> VaultScan:
    """Scan regular Markdown files without following source-file symlinks."""
    if isinstance(min_clean_chars, bool) or not isinstance(min_clean_chars, int):
        raise ValueError("min_clean_chars must be a non-negative integer")
    if min_clean_chars < 0:
        raise ValueError("min_clean_chars must be a non-negative integer")

    requested_root = Path(vault_dir).expanduser()
    if requested_root.is_symlink():
        raise ValueError(f"refusing symlink vault root: {requested_root}")
    if not requested_root.is_dir():
        raise FileNotFoundError(f"vault directory does not exist: {requested_root}")
    root = requested_root.resolve()

    excluded = {name.casefold() for name in DEFAULT_VAULT_EXCLUDE_DIRS}
    if exclude_dirs:
        excluded.update(str(name).casefold() for name in exclude_dirs)

    candidates: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix.casefold() != ".md":
            continue
        relative = path.relative_to(root)
        if any(part.casefold() in excluded for part in relative.parts[:-1]):
            continue
        candidates.append((relative.as_posix(), path))
    candidates.sort(key=lambda item: item[0])

    documents: list[SourceDocument] = []
    folder_stats: dict[str, dict[str, int]] = {}
    for source_id, path in candidates:
        raw = path.read_bytes()
        decoded, encoding = _decode_markdown(raw)
        cleaned, source_kind = normalize_markdown(decoded)
        if len(cleaned) < min_clean_chars:
            continue
        stat = path.stat()
        document = SourceDocument.create(
            source_id=source_id,
            source_revision=hashlib.sha256(raw).hexdigest(),
            observed_at=stat.st_mtime_ns / 1_000_000_000,
            text=cleaned,
            adapter=OBSIDIAN_VAULT_ADAPTER,
            source_kind=source_kind,
            raw_chars=len(decoded),
            metadata={"encoding": encoding, "format": "obsidian-markdown"},
        )
        documents.append(document)

        relative = PurePosixPath(source_id)
        top = relative.parts[0] if len(relative.parts) > 1 else "_root"
        stats = folder_stats.setdefault(top, {"files": 0, "raw_chars": 0, "cleaned_chars": 0})
        stats["files"] += 1
        stats["raw_chars"] += document.raw_chars
        stats["cleaned_chars"] += len(document.text)

    return VaultScan(documents=tuple(documents), folder_stats=folder_stats)


__all__ = [
    "DEFAULT_VAULT_EXCLUDE_DIRS",
    "OBSIDIAN_VAULT_ADAPTER",
    "SOURCE_KINDS",
    "SourceDocument",
    "SourceKind",
    "VaultScan",
    "normalize_markdown",
    "scan_vault",
]
