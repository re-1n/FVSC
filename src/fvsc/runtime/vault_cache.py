"""Versioned atomic JSON persistence for local vault-ingest state.

The cache contains personal derived data and is trusted local application state,
but unlike the research pickle it never executes objects while loading. Canonical
history remains the serialized ``EvidenceLedger``; the semantic snapshot is
re-materialized and checked against stored digests.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
import uuid

from ..evidence.ledger import EvidenceLedger
from ..ingest.document_ingest import materialize_evidence_ledger
from ..ingest.vault_ingest import SOURCE_KINDS, SourceKind
from .materializer import MaterializedSnapshot


CACHE_MAGIC = "fvsc-vault-cache"
CACHE_VERSION = 1
DEFAULT_CACHE_RELATIVE_PATH = Path(".fvsc") / "cache.json"
MAX_CACHE_BYTES = 256 * 1024 * 1024


def _json_copy(value: Any, *, field_name: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON values") from exc
    return json.loads(encoded)


def _safe_source_id(value: str) -> str:
    source_id = str(value).strip()
    path = PurePosixPath(source_id)
    if (
        not source_id
        or "\\" in source_id
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() in {"", "."}
    ):
        raise ValueError("cache source ids must be safe POSIX-relative paths")
    return path.as_posix()


def _sha256(value: str, *, field_name: str) -> str:
    digest = str(value).strip()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return digest


def _non_negative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer") from exc
    if integer < 0 or integer != value:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return integer


def _finite_float(value: Any, *, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


@dataclass(frozen=True)
class VaultCache:
    """Validated in-memory state represented by one cache envelope."""

    adapter: str
    ledger: EvidenceLedger
    snapshot: MaterializedSnapshot
    materializer_dim: int
    source_revisions: Mapping[str, str]
    source_observed_at: Mapping[str, float]
    source_kinds: Mapping[str, SourceKind]
    semantic_input: Mapping[str, Mapping]
    silent_pool: Mapping[str, Mapping]
    file_count: int
    raw_chars: int
    cleaned_chars: int

    def __post_init__(self) -> None:
        adapter = str(self.adapter).strip()
        if not adapter:
            raise ValueError("cache adapter must not be empty")
        if not isinstance(self.ledger, EvidenceLedger):
            raise TypeError("cache ledger must be an EvidenceLedger")
        if not isinstance(self.snapshot, MaterializedSnapshot):
            raise TypeError("cache snapshot must be a MaterializedSnapshot")
        if self.snapshot.ledger_digest != self.ledger.digest:
            raise ValueError("cache snapshot does not match the ledger digest")
        for event in self.ledger.events:
            _safe_source_id(event.source_id)
        if isinstance(self.materializer_dim, bool) or not isinstance(self.materializer_dim, int):
            raise ValueError("materializer_dim must be a positive integer")
        if self.materializer_dim <= 0:
            raise ValueError("materializer_dim must be a positive integer")

        revisions = {_safe_source_id(key): _sha256(value, field_name="source revision")
                     for key, value in self.source_revisions.items()}
        observed: dict[str, float] = {}
        for key, value in self.source_observed_at.items():
            source_id = _safe_source_id(key)
            observed[source_id] = _finite_float(value, field_name="source observed_at")
        kinds: dict[str, SourceKind] = {}
        for key, value in self.source_kinds.items():
            source_id = _safe_source_id(key)
            kind = str(value).strip()
            if kind not in SOURCE_KINDS:
                raise ValueError(f"unknown source kind: {kind!r}")
            kinds[source_id] = kind  # type: ignore[assignment]
        if set(revisions) != set(observed) or set(revisions) != set(kinds):
            raise ValueError("cache source metadata keys must match")

        file_count = _non_negative_int(self.file_count, field_name="file_count")
        raw_chars = _non_negative_int(self.raw_chars, field_name="raw_chars")
        cleaned_chars = _non_negative_int(self.cleaned_chars, field_name="cleaned_chars")
        if file_count != len(revisions):
            raise ValueError("file_count must equal the number of current source revisions")

        semantic_input = _json_copy(dict(self.semantic_input), field_name="semantic_input")
        silent_pool = _json_copy(dict(self.silent_pool), field_name="silent_pool")
        if not isinstance(semantic_input, dict) or not isinstance(silent_pool, dict):
            raise ValueError("semantic_input and silent_pool must be JSON objects")

        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "source_revisions", revisions)
        object.__setattr__(self, "source_observed_at", observed)
        object.__setattr__(self, "source_kinds", kinds)
        object.__setattr__(self, "semantic_input", semantic_input)
        object.__setattr__(self, "silent_pool", silent_pool)
        object.__setattr__(self, "file_count", file_count)
        object.__setattr__(self, "raw_chars", raw_chars)
        object.__setattr__(self, "cleaned_chars", cleaned_chars)


def _materializer_record(snapshot: MaterializedSnapshot, *, dim: int) -> dict[str, Any]:
    return {
        "concept_count": snapshot.concept_count,
        "dim": dim,
        "ledger_digest": snapshot.ledger_digest,
        "materializer_version": snapshot.materializer_version,
        "snapshot_id": snapshot.snapshot_id,
        "state_digest": snapshot.state_digest,
    }


def _validate_materializer(cache: VaultCache) -> MaterializedSnapshot:
    rebuilt = materialize_evidence_ledger(cache.ledger, dim=cache.materializer_dim)
    expected = _materializer_record(cache.snapshot, dim=cache.materializer_dim)
    actual = _materializer_record(rebuilt, dim=cache.materializer_dim)
    if actual != expected:
        raise ValueError("cache snapshot metadata is not reproducible from the ledger")
    return rebuilt


def _envelope(cache: VaultCache) -> dict[str, Any]:
    snapshot = _validate_materializer(cache)
    sources = {
        source_id: {
            "observed_at": cache.source_observed_at[source_id],
            "revision": cache.source_revisions[source_id],
            "source_kind": cache.source_kinds[source_id],
        }
        for source_id in sorted(cache.source_revisions)
    }
    return {
        "magic": CACHE_MAGIC,
        "version": CACHE_VERSION,
        "data": {
            "adapter": cache.adapter,
            "ledger": {
                "digest": cache.ledger.digest,
                "events": cache.ledger.to_records(),
            },
            "materializer": _materializer_record(snapshot, dim=cache.materializer_dim),
            "semantic_input": cache.semantic_input,
            "silent_pool": cache.silent_pool,
            "sources": sources,
            "stats": {
                "cleaned_chars": cache.cleaned_chars,
                "file_count": cache.file_count,
                "raw_chars": cache.raw_chars,
            },
        },
    }


def _require_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def _decode_cache(blob: Any) -> VaultCache:
    envelope = _require_mapping(blob, field_name="cache envelope")
    if envelope.get("magic") != CACHE_MAGIC:
        raise ValueError("invalid vault cache magic")
    if envelope.get("version") != CACHE_VERSION:
        raise ValueError(f"unsupported vault cache version: {envelope.get('version')!r}")
    data = _require_mapping(envelope.get("data"), field_name="cache data")

    ledger_data = _require_mapping(data.get("ledger"), field_name="cache ledger")
    records = ledger_data.get("events")
    if not isinstance(records, list):
        raise ValueError("cache ledger events must be a JSON array")
    ledger = EvidenceLedger.from_records(records)
    stored_ledger_digest = _sha256(ledger_data.get("digest", ""), field_name="ledger digest")
    if ledger.digest != stored_ledger_digest:
        raise ValueError("cache ledger digest mismatch")

    sources_data = _require_mapping(data.get("sources"), field_name="cache sources")
    revisions: dict[str, str] = {}
    observed: dict[str, float] = {}
    kinds: dict[str, SourceKind] = {}
    for raw_source_id, raw_metadata in sources_data.items():
        source_id = _safe_source_id(raw_source_id)
        metadata = _require_mapping(raw_metadata, field_name=f"source {source_id}")
        revisions[source_id] = _sha256(metadata.get("revision", ""), field_name="source revision")
        observed[source_id] = _finite_float(
            metadata.get("observed_at"),
            field_name="source observed_at",
        )
        kind = str(metadata.get("source_kind", "")).strip()
        if kind not in SOURCE_KINDS:
            raise ValueError(f"unknown source kind: {kind!r}")
        kinds[source_id] = kind  # type: ignore[assignment]

    materializer = _require_mapping(data.get("materializer"), field_name="materializer")
    dim = _non_negative_int(materializer.get("dim"), field_name="materializer dim")
    if dim <= 0:
        raise ValueError("materializer dim must be positive")
    snapshot = materialize_evidence_ledger(ledger, dim=dim)
    stored_materializer = {
        "concept_count": _non_negative_int(
            materializer.get("concept_count"),
            field_name="materializer concept_count",
        ),
        "dim": dim,
        "ledger_digest": _sha256(
            materializer.get("ledger_digest", ""),
            field_name="materializer ledger_digest",
        ),
        "materializer_version": str(materializer.get("materializer_version", "")),
        "snapshot_id": _sha256(
            materializer.get("snapshot_id", ""),
            field_name="materializer snapshot_id",
        ),
        "state_digest": _sha256(
            materializer.get("state_digest", ""),
            field_name="materializer state_digest",
        ),
    }
    if stored_materializer != _materializer_record(snapshot, dim=dim):
        raise ValueError("cache materializer metadata mismatch")

    stats = _require_mapping(data.get("stats"), field_name="cache stats")
    semantic_input = _require_mapping(data.get("semantic_input"), field_name="semantic_input")
    silent_pool = _require_mapping(data.get("silent_pool"), field_name="silent_pool")
    return VaultCache(
        adapter=str(data.get("adapter", "")),
        ledger=ledger,
        snapshot=snapshot,
        materializer_dim=dim,
        source_revisions=revisions,
        source_observed_at=observed,
        source_kinds=kinds,
        semantic_input=semantic_input,
        silent_pool=silent_pool,
        file_count=_non_negative_int(stats.get("file_count"), field_name="file_count"),
        raw_chars=_non_negative_int(stats.get("raw_chars"), field_name="raw_chars"),
        cleaned_chars=_non_negative_int(
            stats.get("cleaned_chars"),
            field_name="cleaned_chars",
        ),
    )


def load_vault_cache(path: Path) -> VaultCache:
    """Load and fully validate one regular local JSON cache file."""
    cache_path = Path(path)
    if cache_path.is_symlink() or not cache_path.is_file():
        raise ValueError(f"refusing non-regular vault cache file: {cache_path}")
    size = cache_path.stat().st_size
    if size > MAX_CACHE_BYTES:
        raise ValueError(f"vault cache exceeds {MAX_CACHE_BYTES} bytes")
    try:
        decoded = json.loads(cache_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("vault cache is not valid UTF-8 JSON") from exc
    return _decode_cache(decoded)


def save_vault_cache(path: Path, cache: VaultCache) -> None:
    """Validate and atomically write a versioned local cache envelope."""
    if not isinstance(cache, VaultCache):
        raise TypeError("cache must be a VaultCache")
    cache_path = Path(path)
    if cache_path.is_symlink() or (cache_path.exists() and not cache_path.is_file()):
        raise ValueError(f"refusing non-regular vault cache target: {cache_path}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        _envelope(cache),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    temporary = cache_path.parent / f".{cache_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, cache_path)
        _fsync_directory(cache_path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _fsync_directory(directory: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "CACHE_MAGIC",
    "CACHE_VERSION",
    "DEFAULT_CACHE_RELATIVE_PATH",
    "MAX_CACHE_BYTES",
    "VaultCache",
    "load_vault_cache",
    "save_vault_cache",
]
