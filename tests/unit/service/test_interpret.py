from __future__ import annotations

import os

import pytest

from fvsc.ingest import ParseConfig
from fvsc.ingest.vault_sync import VaultSyncConfig
from fvsc.interpretation import (
    GeneratedClaim,
    GeneratedInterpretation,
    InterpretationStore,
)
from fvsc.service import VaultInterpreter, VaultRuntime


class _Backend:
    backend_id = "test.backend"
    model = "fake"
    prompt_version = "1"
    interpretation_layer = 3

    def __init__(self) -> None:
        self.sources = ()

    def generate(self, question, sources):
        self.sources = sources
        return GeneratedInterpretation(
            answer="Паразит описывает перенаправление внимания.",
            claims=(
                GeneratedClaim(
                    text="Образ связан с перенаправлением внимания.",
                    source_labels=("S1",),
                ),
            ),
        )


def _runtime(tmp_path) -> VaultRuntime:
    note = tmp_path / "parasites.md"
    note.write_text(
        "Паразиты превращают внимание в чужой ресурс.", encoding="utf-8"
    )
    os.utime(note, (10.0, 10.0))
    runtime = VaultRuntime(
        tmp_path,
        sync_config=VaultSyncConfig(
            parser_config=ParseConfig(min_freq=1, min_token_len=2, max_concepts=None),
            materializer_dim=16,
            enable_russian_judgments=True,
        ),
    )
    runtime.sync(sync_time=20.0)
    return runtime


def test_vault_interpreter_uses_lexical_sources_and_attaches_exact_provenance(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    backend = _Backend()
    store = InterpretationStore(tmp_path / ".fvsc" / "interpretations.json")
    interpreter = VaultInterpreter(runtime, backend, store=store)

    proposal = interpreter.interpret(
        "роль паразитов во внимании",
        top_k=1,
        context_depth=0,
        generated_at=30.0,
    )

    assert backend.sources[0].source_id == "parasites.md"
    assert proposal.retrieval_method == "lexical-char-ngram-v1"
    assert proposal.cited_source_ids == ("parasites.md",)
    assert proposal.citations[0].evidence_event_ids
    assert proposal.interpretation_layer == 3
    assert store.get_proposal(proposal.proposal_id) == proposal


def test_vault_interpreter_abstains_when_lexical_retrieval_has_no_context(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    interpreter = VaultInterpreter(runtime, _Backend())

    with pytest.raises(ValueError, match="no source context"):
        interpreter.interpret("!!!", generated_at=30.0)
