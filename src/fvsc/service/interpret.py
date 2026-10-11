"""Application service for lexical retrieval followed by isolated L2/L3 output."""

from __future__ import annotations

import math
import time

from ..interpretation import (
    InterpretationBackend,
    InterpretationProposal,
    InterpretationStore,
    generate_interpretation_proposal,
)
from .runtime import VaultRuntime


class VaultInterpreter:
    """Compose accepted retrieval and proposal contracts without persistence."""

    def __init__(
        self,
        runtime: VaultRuntime,
        backend: InterpretationBackend,
        *,
        store: InterpretationStore | None = None,
    ) -> None:
        self.runtime = runtime
        self.backend = backend
        self.store = store

    def interpret(
        self,
        question: str,
        *,
        top_k: int = 5,
        context_depth: int = 1,
        generated_at: float | None = None,
        conversation_id: str | None = None,
        previous_proposal_ids: tuple[str, ...] = (),
    ) -> InterpretationProposal:
        timestamp = time.time() if generated_at is None else float(generated_at)
        if not math.isfinite(timestamp):
            raise ValueError("generated_at must be finite")
        dialogue = []
        if previous_proposal_ids and (not conversation_id or self.store is None):
            raise ValueError("dialogue requires a conversation and proposal journal")
        if len(previous_proposal_ids) > 6 or len(set(previous_proposal_ids)) != len(previous_proposal_ids):
            raise ValueError("dialogue accepts up to six distinct previous turns")
        for proposal_id in previous_proposal_ids:
            previous = self.store.get_proposal(proposal_id)
            if previous is None or previous.metadata.get("conversation_id") != conversation_id:
                raise ValueError("previous turn does not belong to this conversation")
            if dialogue and previous.generated_at < dialogue[-1].generated_at:
                raise ValueError("previous turns must be chronological")
            dialogue.append(previous)
        # Only user questions expand retrieval. Model answers never become evidence
        # or lexical query terms. The latest question remains the generation target.
        retrieval_query = "\n".join([*(p.question[:2048] for p in dialogue), question])
        documents = self.runtime.source_documents_for_query(
            retrieval_query,
            top_k=top_k,
            context_depth=context_depth,
        )
        if not documents:
            raise ValueError("lexical retrieval found no source context")
        event_ids = {
            document.source_id: self.runtime.exact_event_ids_for_source(
                document.source_id
            )
            for document in documents
        }
        proposal = generate_interpretation_proposal(
            question=question,
            documents=documents,
            backend=self.backend,
            generated_at=timestamp,
            retrieval_method="lexical-char-ngram-v1",
            evidence_event_ids_by_source=event_ids,
            dialogue=tuple(dialogue), conversation_id=conversation_id,
        )
        if self.store is not None:
            self.store.append_proposal(proposal)
        return proposal


__all__ = ["VaultInterpreter"]
