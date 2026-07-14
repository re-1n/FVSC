"""Thread-safe local application runtime over accepted FVSC contracts.

The runtime owns orchestration only.  Ingest, lifecycle, materialization,
retrieval, and feedback remain implemented in their domain modules.  Source
text is rescanned into memory and is never copied into the persistent cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any

from ..evidence import EvidenceEvent, EvidenceLedger, FeedbackAction, create_owner_feedback
from ..evidence.feedback import OWNER_FEEDBACK_EXTRACTOR
from ..ingest.document_ingest import materialize_evidence_ledger
from ..ingest.judgment_events import JUDGMENT_EVENT_EXTRACTOR
from ..ingest.vault_ingest import (
    OBSIDIAN_VAULT_ADAPTER,
    SourceDocument,
    SourceKind,
    scan_vault,
)
from ..ingest.vault_sync import VaultSyncConfig, sync_vault
from ..retrieval import (
    JudgmentSearchIndex,
    LexicalSearchIndex,
    expand_source_context,
)
from ..runtime.vault_cache import (
    DEFAULT_CACHE_RELATIVE_PATH,
    VaultCache,
    load_vault_cache,
    save_vault_cache,
)


class RuntimeNotLoadedError(RuntimeError):
    """Raised when a query needs a synchronized runtime state."""


class StaleSourceStateError(RuntimeError):
    """Raised when current source revisions no longer match the cache."""


@dataclass(frozen=True)
class RuntimeStatus:
    loaded: bool
    adapter: str | None
    cache_path: str
    source_count: int
    ledger_events: int
    active_events: int
    exact_judgments: int
    owner_feedback_events: int
    snapshot_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "adapter": self.adapter,
            "cache_path": self.cache_path,
            "source_count": self.source_count,
            "ledger_events": self.ledger_events,
            "active_events": self.active_events,
            "exact_judgments": self.exact_judgments,
            "owner_feedback_events": self.owner_feedback_events,
            "snapshot_id": self.snapshot_id,
        }


@dataclass(frozen=True)
class RuntimeSearchHit:
    source_id: str
    source_revision: str
    observed_at: float
    source_kind: SourceKind
    score: float
    preview: str
    context_source_ids: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "observed_at": self.observed_at,
            "source_kind": self.source_kind,
            "score": self.score,
            "preview": self.preview,
            "context_source_ids": list(self.context_source_ids),
            "evidence_event_ids": list(self.evidence_event_ids),
        }


def _preview(text: str, *, limit: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


class VaultRuntime:
    """One local Obsidian vault backed by a canonical ``EvidenceLedger``."""

    def __init__(
        self,
        vault_dir: Path,
        *,
        cache_path: Path | None = None,
        sync_config: VaultSyncConfig | None = None,
    ) -> None:
        self.vault_dir = Path(vault_dir).expanduser()
        self.cache_path = (
            Path(cache_path).expanduser()
            if cache_path is not None
            else self.vault_dir / DEFAULT_CACHE_RELATIVE_PATH
        )
        self.sync_config = sync_config or VaultSyncConfig(
            enable_russian_judgments=True
        )
        self._lock = threading.RLock()
        self._cache: VaultCache | None = None
        self._documents: tuple[SourceDocument, ...] = ()
        self._documents_by_id: dict[str, SourceDocument] = {}
        self._lexical_index: LexicalSearchIndex | None = None
        self._judgment_index: JudgmentSearchIndex | None = None

    @property
    def ledger(self) -> EvidenceLedger:
        with self._lock:
            # Do not expose the live mutable ledger around atomic persistence.
            return EvidenceLedger(self._require_cache().ledger.events)

    @property
    def documents(self) -> tuple[SourceDocument, ...]:
        with self._lock:
            self._require_cache()
            return self._documents

    def _require_cache(self) -> VaultCache:
        if self._cache is None:
            raise RuntimeNotLoadedError("vault runtime is not loaded; sync or load it first")
        return self._cache

    def _install(self, cache: VaultCache, documents: tuple[SourceDocument, ...]) -> None:
        document_ids = tuple(document.source_id for document in documents)
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("runtime source documents must have unique ids")
        revisions = {document.source_id: document.source_revision for document in documents}
        if revisions != dict(cache.source_revisions):
            raise StaleSourceStateError(
                "vault source revisions do not match the validated cache; synchronize first"
            )
        documents_by_id = {document.source_id: document for document in documents}
        lexical_index = LexicalSearchIndex(documents)
        has_judgments = any(
            event.extractor == JUDGMENT_EVENT_EXTRACTOR
            for event in cache.ledger.active_events
        )
        judgment_index = (
            JudgmentSearchIndex(cache.ledger) if has_judgments else None
        )
        self._cache = cache
        self._documents = documents
        self._documents_by_id = documents_by_id
        self._lexical_index = lexical_index
        self._judgment_index = judgment_index

    def _display_cache_path(self) -> str:
        try:
            return self.cache_path.relative_to(self.vault_dir).as_posix()
        except ValueError:
            return "<configured-cache>"

    def sync(self, *, sync_time: float | None = None) -> RuntimeStatus:
        with self._lock:
            result = sync_vault(
                self.vault_dir,
                cache_path=self.cache_path,
                config=self.sync_config,
                sync_time=sync_time,
            )
            self._install(result.cache, result.scan.documents)
            return self.status()

    def load(self) -> RuntimeStatus:
        """Load a cache only when it exactly matches the current vault revision set."""
        with self._lock:
            cache = load_vault_cache(self.cache_path)
            if cache.adapter != OBSIDIAN_VAULT_ADAPTER:
                raise ValueError(
                    f"cache adapter {cache.adapter!r} cannot back an Obsidian runtime"
                )
            scan = scan_vault(
                self.vault_dir,
                exclude_dirs=self.sync_config.exclude_dirs,
                min_clean_chars=self.sync_config.min_clean_chars,
            )
            self._install(cache, scan.documents)
            return self.status()

    def status(self) -> RuntimeStatus:
        with self._lock:
            cache = self._cache
            if cache is None:
                return RuntimeStatus(
                    loaded=False,
                    adapter=None,
                    cache_path=self._display_cache_path(),
                    source_count=0,
                    ledger_events=0,
                    active_events=0,
                    exact_judgments=0,
                    owner_feedback_events=0,
                    snapshot_id=None,
                )
            active = cache.ledger.active_events
            return RuntimeStatus(
                loaded=True,
                adapter=cache.adapter,
                cache_path=self._display_cache_path(),
                source_count=len(self._documents),
                ledger_events=cache.ledger.event_count,
                active_events=cache.ledger.active_count,
                exact_judgments=sum(
                    event.extractor == JUDGMENT_EVENT_EXTRACTOR for event in active
                ),
                owner_feedback_events=sum(
                    event.extractor == OWNER_FEEDBACK_EXTRACTOR for event in active
                ),
                snapshot_id=cache.snapshot.snapshot_id,
            )

    def source_document(self, source_id: str) -> SourceDocument:
        with self._lock:
            self._require_cache()
            source = str(source_id).strip()
            try:
                return self._documents_by_id[source]
            except KeyError as exc:
                raise KeyError(f"unknown source document: {source}") from exc

    def source_documents_for_query(
        self,
        query: str,
        *,
        top_k: int = 5,
        context_depth: int = 1,
    ) -> tuple[SourceDocument, ...]:
        """Return lexical hits followed by unique structural context documents."""
        with self._lock:
            self._require_cache()
            if self._lexical_index is None:
                raise RuntimeNotLoadedError("lexical index is unavailable")
            hits = self._lexical_index.search(query, top_k=top_k)
            ordered: list[SourceDocument] = []
            seen: set[str] = set()
            for hit in hits:
                context = expand_source_context(
                    self._documents,
                    hit.source_id,
                    max_depth=context_depth,
                )
                by_id = {item.source_id: item for item in context}
                for item in (hit.document, *context):
                    document = by_id.get(item.source_id, item)
                    if document.source_id not in seen:
                        seen.add(document.source_id)
                        ordered.append(document)
            return tuple(ordered)

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        context_depth: int = 1,
    ) -> tuple[RuntimeSearchHit, ...]:
        """Search original sources lexically; exact evidence annotates but never reranks."""
        with self._lock:
            self._require_cache()
            if self._lexical_index is None:
                raise RuntimeNotLoadedError("lexical index is unavailable")
            lexical_hits = self._lexical_index.search(query, top_k=top_k)
            exact_by_source = (
                {
                    hit.source_id: hit.evidence_event_ids
                    for hit in self._judgment_index.search(
                        query,
                        top_k=max(top_k * 3, top_k),
                    )
                }
                if self._judgment_index is not None
                else {}
            )
            results: list[RuntimeSearchHit] = []
            for hit in lexical_hits:
                context = expand_source_context(
                    self._documents,
                    hit.source_id,
                    max_depth=context_depth,
                )
                context_ids = tuple(
                    item.source_id for item in context if item.source_id != hit.source_id
                )
                results.append(
                    RuntimeSearchHit(
                        source_id=hit.source_id,
                        source_revision=hit.document.source_revision,
                        observed_at=hit.document.observed_at,
                        source_kind=hit.document.source_kind,
                        score=hit.score,
                        preview=_preview(hit.document.text),
                        context_source_ids=context_ids,
                        evidence_event_ids=exact_by_source.get(hit.source_id, ()),
                    )
                )
            return tuple(results)

    def record_feedback(
        self,
        *,
        target_event_id: str,
        action: FeedbackAction,
        observed_at: float,
        context_tags: tuple[str, ...] = (),
        recorded_at: float | None = None,
    ) -> EvidenceEvent:
        """Atomically persist owner feedback without mutating its target event."""
        with self._lock:
            current = self._require_cache()
            trial = EvidenceLedger(current.ledger.events)
            feedback = create_owner_feedback(
                trial,
                target_event_id=target_event_id,
                action=action,
                observed_at=observed_at,
                recorded_at=recorded_at,
                context_tags=context_tags,
            )
            trial.append(feedback)
            snapshot = materialize_evidence_ledger(
                trial,
                dim=current.materializer_dim,
            )
            updated = VaultCache(
                adapter=current.adapter,
                ledger=trial,
                snapshot=snapshot,
                materializer_dim=current.materializer_dim,
                source_revisions=current.source_revisions,
                source_observed_at=current.source_observed_at,
                source_kinds=current.source_kinds,
                semantic_input=current.semantic_input,
                silent_pool=current.silent_pool,
                file_count=current.file_count,
                raw_chars=current.raw_chars,
                cleaned_chars=current.cleaned_chars,
            )
            save_vault_cache(self.cache_path, updated)
            self._install(updated, self._documents)
            return feedback


__all__ = [
    "RuntimeNotLoadedError",
    "RuntimeSearchHit",
    "RuntimeStatus",
    "StaleSourceStateError",
    "VaultRuntime",
]
