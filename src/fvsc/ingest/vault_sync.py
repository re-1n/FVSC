"""Thin local orchestration for Obsidian vault -> ledger -> snapshot -> cache."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Sequence

from ..evidence.ledger import EvidenceLedger
from ..runtime.materializer import MaterializedSnapshot
from ..runtime.vault_cache import (
    DEFAULT_CACHE_RELATIVE_PATH,
    VaultCache,
    load_vault_cache,
    save_vault_cache,
)
from .document_ingest import (
    SourceLifecycleReport,
    build_evidence_batch,
    materialize_evidence_ledger,
    reconcile_evidence_batch,
)
from .parser import DEFAULT_STOPWORDS_RU_EN, ParseConfig
from .vault_ingest import OBSIDIAN_VAULT_ADAPTER, VaultScan, scan_vault


def _default_parser_config() -> ParseConfig:
    return ParseConfig(
        window=4,
        min_freq=2,
        max_concepts=1200,
        min_token_len=2,
        stopwords=DEFAULT_STOPWORDS_RU_EN,
    )


@dataclass(frozen=True)
class VaultSyncConfig:
    parser_config: ParseConfig = field(default_factory=_default_parser_config)
    materializer_dim: int = 64
    exclude_dirs: frozenset[str] = frozenset()
    min_clean_chars: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.parser_config, ParseConfig):
            raise TypeError("parser_config must be a ParseConfig")
        if (
            isinstance(self.materializer_dim, bool)
            or not isinstance(self.materializer_dim, int)
            or self.materializer_dim <= 0
        ):
            raise ValueError("materializer_dim must be a positive integer")
        if (
            isinstance(self.min_clean_chars, bool)
            or not isinstance(self.min_clean_chars, int)
            or self.min_clean_chars < 0
        ):
            raise ValueError("min_clean_chars must be a non-negative integer")
        object.__setattr__(
            self,
            "exclude_dirs",
            frozenset(str(name) for name in self.exclude_dirs),
        )


@dataclass(frozen=True)
class VaultSyncResult:
    cache_path: Path
    cache: VaultCache
    scan: VaultScan
    lifecycle: SourceLifecycleReport
    loaded_existing_cache: bool

    @property
    def ledger(self) -> EvidenceLedger:
        return self.cache.ledger

    @property
    def snapshot(self) -> MaterializedSnapshot:
        return self.cache.snapshot


def sync_vault(
    vault_dir: Path,
    *,
    cache_path: Path | None = None,
    config: VaultSyncConfig | None = None,
    sync_time: float | None = None,
) -> VaultSyncResult:
    """Synchronize one complete vault scan into append-only local state.

    Existing cache validation happens before scanning or mutating the in-memory
    ledger. Invalid/corrupt cache state is never silently discarded.
    """
    settings = config or VaultSyncConfig()
    requested_root = Path(vault_dir).expanduser()
    target = (
        Path(cache_path).expanduser()
        if cache_path is not None
        else requested_root / DEFAULT_CACHE_RELATIVE_PATH
    )

    loaded_existing = target.is_symlink() or target.exists()
    if loaded_existing:
        previous = load_vault_cache(target)
        if previous.adapter != OBSIDIAN_VAULT_ADAPTER:
            raise ValueError(
                f"cache adapter {previous.adapter!r} cannot be used for an Obsidian vault"
            )
        ledger = previous.ledger
    else:
        ledger = EvidenceLedger()

    scan = scan_vault(
        requested_root,
        exclude_dirs=settings.exclude_dirs,
        min_clean_chars=settings.min_clean_chars,
    )
    batch = build_evidence_batch(
        scan.documents,
        config=settings.parser_config,
        adapter=OBSIDIAN_VAULT_ADAPTER,
    )
    lifecycle = reconcile_evidence_batch(ledger, batch, sync_time=sync_time)
    snapshot = materialize_evidence_ledger(ledger, dim=settings.materializer_dim)
    cache = VaultCache(
        adapter=batch.adapter,
        ledger=ledger,
        snapshot=snapshot,
        materializer_dim=settings.materializer_dim,
        source_revisions=batch.source_revisions,
        source_observed_at=batch.source_observed_at,
        source_kinds=batch.source_kinds,
        semantic_input=batch.semantic_input,
        silent_pool=batch.silent_pool,
        file_count=batch.source_count,
        raw_chars=batch.raw_chars,
        cleaned_chars=batch.cleaned_chars,
    )
    save_vault_cache(target, cache)
    return VaultSyncResult(
        cache_path=target,
        cache=cache,
        scan=scan,
        lifecycle=lifecycle,
        loaded_existing_cache=loaded_existing,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize an Obsidian vault into a local FVSC evidence cache.",
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=os.environ.get("FVSC_VAULT_PATH"),
        help="Obsidian vault path (or set FVSC_VAULT_PATH)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Cache path (default: <vault>/.fvsc/cache.json)",
    )
    parser.add_argument("--dim", type=int, default=64, help="Materializer dimension")
    parser.add_argument("--min-freq", type=int, default=2, help="Minimum global token frequency")
    parser.add_argument("--max-concepts", type=int, default=1200, help="Maximum concepts")
    parser.add_argument("--min-clean-chars", type=int, default=0)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional directory segment to exclude (repeatable)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.vault is None:
        parser.error("--vault or FVSC_VAULT_PATH is required")
    parser_config = ParseConfig(
        window=4,
        min_freq=args.min_freq,
        max_concepts=args.max_concepts,
        min_token_len=2,
        stopwords=DEFAULT_STOPWORDS_RU_EN,
    )
    result = sync_vault(
        args.vault,
        cache_path=args.cache,
        config=VaultSyncConfig(
            parser_config=parser_config,
            materializer_dim=args.dim,
            exclude_dirs=frozenset(args.exclude),
            min_clean_chars=args.min_clean_chars,
        ),
    )
    print(
        json.dumps(
            {
                "active_events": result.ledger.active_count,
                "asserted": result.lifecycle.asserted_count,
                "cache": str(result.cache_path),
                "concepts": result.snapshot.concept_count,
                "deleted_sources": list(result.lifecycle.deleted_sources),
                "files": result.scan.file_count,
                "ledger_events": result.ledger.event_count,
                "retracted": result.lifecycle.retracted_count,
                "snapshot_id": result.snapshot.snapshot_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["VaultSyncConfig", "VaultSyncResult", "main", "sync_vault"]
