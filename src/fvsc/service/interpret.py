"""Application service for lexical retrieval followed by isolated L2/L3 output."""

from __future__ import annotations

import math
import time

from ..interpretation import (
    InterpretationBackend,
    InterpretationProposal,
    generate_interpretation_proposal,
)
from .runtime import VaultRuntime


class VaultInterpreter:
    """Compose accepted retrieval and proposal contracts without persistence."""

    def __init__(self, runtime: VaultRuntime, backend: InterpretationBackend) -> None:
        self.runtime = runtime
        self.backend = backend

    def interpret(
        self,
        question: str,
        *,
        top_k: int = 5,
        context_depth: int = 1,
        generated_at: float | None = None,
    ) -> InterpretationProposal:
        timestamp = time.time() if generated_at is None else float(generated_at)
        if not math.isfinite(timestamp):
            raise ValueError("generated_at must be finite")
        documents = self.runtime.source_documents_for_query(
            question,
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
        return generate_interpretation_proposal(
            question=question,
            documents=documents,
            backend=self.backend,
            generated_at=timestamp,
            retrieval_method="lexical-char-ngram-v1",
            evidence_event_ids_by_source=event_ids,
        )


__all__ = ["VaultInterpreter"]
